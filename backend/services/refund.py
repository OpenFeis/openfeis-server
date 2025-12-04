"""
Refund & Scratch Processing Service for Open Feis.

Handles:
- Full refunds (entire order)
- Partial refunds (specific entries)
- Scratch processing (cancellation with refund)
- Refund policy enforcement
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from sqlmodel import Session, select

from backend.scoring_engine.models_platform import (
    Entry, Competition, Dancer, Feis, Order, User, FeisSettings,
    PaymentStatus, RefundLog, CheckInStatus
)
from backend.services.waitlist import process_spot_available


@dataclass
class RefundResult:
    """Result of a refund operation."""
    success: bool
    order_id: str
    refund_amount_cents: int
    refund_type: str  # "full", "partial", "scratch"
    entries_affected: int
    stripe_refund_id: Optional[str]
    message: str


@dataclass
class ScratchResult:
    """Result of scratching an entry."""
    success: bool
    entry_id: str
    dancer_name: str
    competition_name: str
    refund_amount_cents: int
    refund_percent: int
    message: str


def get_refund_policy(
    session: Session,
    feis_id: UUID
) -> dict:
    """
    Get the refund policy for a feis.
    """
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    if not settings:
        # Default policy
        return {
            "allow_scratches": True,
            "scratch_refund_percent": 50,
            "scratch_deadline": None,
            "can_scratch": True,
            "refund_message": "50% refund available"
        }
    
    can_scratch = settings.allow_scratches
    refund_percent = settings.scratch_refund_percent
    deadline = settings.scratch_deadline
    
    # Check if past deadline
    if deadline and datetime.utcnow() > deadline:
        can_scratch = settings.allow_scratches  # Still allowed, but 0% refund
        refund_percent = 0
        message = "Past scratch deadline - no refund available"
    elif not can_scratch:
        message = "Scratches are not allowed for this feis"
    else:
        message = f"{refund_percent}% refund available"
    
    return {
        "allow_scratches": settings.allow_scratches,
        "scratch_refund_percent": refund_percent,
        "scratch_deadline": deadline,
        "can_scratch": can_scratch,
        "refund_message": message
    }


def calculate_entry_refund(
    session: Session,
    entry: Entry,
    refund_percent: int
) -> int:
    """
    Calculate the refund amount for a single entry.
    
    Returns the refund amount in cents.
    """
    competition = session.get(Competition, entry.competition_id)
    if not competition:
        return 0
    
    # Use competition's price
    entry_price = competition.price_cents or 1000  # Default $10
    
    # Calculate refund based on percentage
    refund = int(entry_price * (refund_percent / 100))
    
    return refund


def scratch_entry(
    session: Session,
    entry_id: UUID,
    user_id: UUID,
    reason: str
) -> ScratchResult:
    """
    Scratch (cancel) a single entry with refund processing.
    """
    entry = session.get(Entry, entry_id)
    
    if not entry:
        return ScratchResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name="Unknown",
            competition_name="Unknown",
            refund_amount_cents=0,
            refund_percent=0,
            message="Entry not found"
        )
    
    # Check if already cancelled
    if entry.cancelled:
        return ScratchResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name="Unknown",
            competition_name="Unknown",
            refund_amount_cents=0,
            refund_percent=0,
            message="Entry already cancelled"
        )
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    if not competition:
        return ScratchResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_name="Unknown",
            refund_amount_cents=0,
            refund_percent=0,
            message="Competition not found"
        )
    
    # Get refund policy
    policy = get_refund_policy(session, competition.feis_id)
    
    if not policy["allow_scratches"]:
        return ScratchResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_name=competition.name,
            refund_amount_cents=0,
            refund_percent=0,
            message="Scratches are not allowed for this feis"
        )
    
    refund_percent = policy["scratch_refund_percent"]
    refund_amount = calculate_entry_refund(session, entry, refund_percent)
    
    # Cancel the entry
    entry.cancelled = True
    entry.cancelled_at = datetime.utcnow()
    entry.cancellation_reason = reason
    entry.refund_amount_cents = refund_amount
    entry.check_in_status = CheckInStatus.SCRATCHED
    
    session.add(entry)
    
    # Update order if exists
    if entry.order_id:
        order = session.get(Order, entry.order_id)
        if order:
            order.refund_total_cents += refund_amount
            if order.status == PaymentStatus.COMPLETED:
                # Check if all entries are cancelled
                remaining = session.exec(
                    select(Entry).where(
                        Entry.order_id == order.id,
                        Entry.cancelled == False
                    )
                ).first()
                
                if not remaining:
                    order.status = PaymentStatus.REFUNDED
                else:
                    order.status = PaymentStatus.PARTIAL_REFUND
                
                order.refunded_at = datetime.utcnow()
                order.refund_reason = reason
            
            session.add(order)
            
            # Create refund log
            log = RefundLog(
                order_id=order.id,
                entry_id=entry.id,
                amount_cents=refund_amount,
                reason=reason,
                refund_type="scratch",
                processed_by=user_id
            )
            session.add(log)
    
    session.commit()
    
    # Process waitlist - offer spot to next in line
    process_spot_available(session, competition.feis_id, competition.id)
    
    return ScratchResult(
        success=True,
        entry_id=str(entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competition_name=competition.name,
        refund_amount_cents=refund_amount,
        refund_percent=refund_percent,
        message=f"Entry scratched. ${refund_amount/100:.2f} refund ({refund_percent}%)"
    )


def process_full_refund(
    session: Session,
    order_id: UUID,
    user_id: UUID,
    reason: str
) -> RefundResult:
    """
    Process a full refund for an entire order.
    
    Cancels all entries and refunds the full amount.
    """
    order = session.get(Order, order_id)
    
    if not order:
        return RefundResult(
            success=False,
            order_id=str(order_id),
            refund_amount_cents=0,
            refund_type="full",
            entries_affected=0,
            stripe_refund_id=None,
            message="Order not found"
        )
    
    # Check if already fully refunded
    if order.status == PaymentStatus.REFUNDED:
        return RefundResult(
            success=False,
            order_id=str(order_id),
            refund_amount_cents=0,
            refund_type="full",
            entries_affected=0,
            stripe_refund_id=None,
            message="Order already fully refunded"
        )
    
    # Get all non-cancelled entries
    entries = session.exec(
        select(Entry).where(
            Entry.order_id == order_id,
            Entry.cancelled == False
        )
    ).all()
    
    if not entries:
        return RefundResult(
            success=False,
            order_id=str(order_id),
            refund_amount_cents=0,
            refund_type="full",
            entries_affected=0,
            stripe_refund_id=None,
            message="No entries to refund"
        )
    
    # Calculate refund amount (what's left after previous refunds)
    refund_amount = order.total_cents - order.refund_total_cents
    
    # Cancel all entries
    for entry in entries:
        entry.cancelled = True
        entry.cancelled_at = datetime.utcnow()
        entry.cancellation_reason = reason
        entry.check_in_status = CheckInStatus.SCRATCHED
        session.add(entry)
        
        # Process waitlist for each competition
        competition = session.get(Competition, entry.competition_id)
        if competition:
            process_spot_available(session, competition.feis_id, competition.id)
    
    # Update order
    order.status = PaymentStatus.REFUNDED
    order.refund_total_cents = order.total_cents
    order.refunded_at = datetime.utcnow()
    order.refund_reason = reason
    
    # TODO: Process Stripe refund if stripe_payment_intent_id exists
    stripe_refund_id = None
    # if order.stripe_payment_intent_id:
    #     stripe_refund_id = process_stripe_refund(order.stripe_payment_intent_id, refund_amount)
    
    order.stripe_refund_id = stripe_refund_id
    
    session.add(order)
    
    # Create refund log
    log = RefundLog(
        order_id=order.id,
        entry_id=None,  # Full order refund
        amount_cents=refund_amount,
        reason=reason,
        refund_type="full",
        processed_by=user_id,
        stripe_refund_id=stripe_refund_id
    )
    session.add(log)
    
    session.commit()
    
    return RefundResult(
        success=True,
        order_id=str(order_id),
        refund_amount_cents=refund_amount,
        refund_type="full",
        entries_affected=len(entries),
        stripe_refund_id=stripe_refund_id,
        message=f"Full refund of ${refund_amount/100:.2f} processed for {len(entries)} entries"
    )


def process_partial_refund(
    session: Session,
    order_id: UUID,
    entry_ids: List[UUID],
    user_id: UUID,
    reason: str,
    custom_amount_cents: Optional[int] = None
) -> RefundResult:
    """
    Process a partial refund for specific entries.
    """
    order = session.get(Order, order_id)
    
    if not order:
        return RefundResult(
            success=False,
            order_id=str(order_id),
            refund_amount_cents=0,
            refund_type="partial",
            entries_affected=0,
            stripe_refund_id=None,
            message="Order not found"
        )
    
    # Get the specified entries
    entries = session.exec(
        select(Entry).where(
            Entry.id.in_(entry_ids),
            Entry.order_id == order_id,
            Entry.cancelled == False
        )
    ).all()
    
    if not entries:
        return RefundResult(
            success=False,
            order_id=str(order_id),
            refund_amount_cents=0,
            refund_type="partial",
            entries_affected=0,
            stripe_refund_id=None,
            message="No valid entries to refund"
        )
    
    # Calculate refund amount
    if custom_amount_cents is not None:
        refund_amount = custom_amount_cents
    else:
        # Calculate based on entry prices
        refund_amount = 0
        for entry in entries:
            competition = session.get(Competition, entry.competition_id)
            if competition:
                refund_amount += competition.price_cents or 1000
    
    # Ensure we don't refund more than remaining
    max_refund = order.total_cents - order.refund_total_cents
    refund_amount = min(refund_amount, max_refund)
    
    # Cancel entries
    for entry in entries:
        entry.cancelled = True
        entry.cancelled_at = datetime.utcnow()
        entry.cancellation_reason = reason
        entry.refund_amount_cents = refund_amount // len(entries)  # Distribute evenly
        entry.check_in_status = CheckInStatus.SCRATCHED
        session.add(entry)
        
        # Process waitlist
        competition = session.get(Competition, entry.competition_id)
        if competition:
            process_spot_available(session, competition.feis_id, competition.id)
    
    # Update order
    order.refund_total_cents += refund_amount
    
    # Check if all entries are now cancelled
    remaining = session.exec(
        select(Entry).where(
            Entry.order_id == order_id,
            Entry.cancelled == False
        )
    ).first()
    
    if not remaining:
        order.status = PaymentStatus.REFUNDED
    else:
        order.status = PaymentStatus.PARTIAL_REFUND
    
    order.refunded_at = datetime.utcnow()
    order.refund_reason = reason
    
    # TODO: Process Stripe refund
    stripe_refund_id = None
    
    session.add(order)
    
    # Create refund log
    log = RefundLog(
        order_id=order.id,
        entry_id=entries[0].id if len(entries) == 1 else None,
        amount_cents=refund_amount,
        reason=reason,
        refund_type="partial",
        processed_by=user_id,
        stripe_refund_id=stripe_refund_id
    )
    session.add(log)
    
    session.commit()
    
    return RefundResult(
        success=True,
        order_id=str(order_id),
        refund_amount_cents=refund_amount,
        refund_type="partial",
        entries_affected=len(entries),
        stripe_refund_id=stripe_refund_id,
        message=f"Partial refund of ${refund_amount/100:.2f} processed for {len(entries)} entries"
    )


def get_order_refund_summary(
    session: Session,
    order_id: UUID
) -> dict:
    """
    Get a summary of all refunds for an order.
    """
    order = session.get(Order, order_id)
    
    if not order:
        return {"error": "Order not found"}
    
    # Get refund logs
    logs = session.exec(
        select(RefundLog).where(RefundLog.order_id == order_id)
        .order_by(RefundLog.created_at.desc())
    ).all()
    
    log_data = []
    for log in logs:
        processor = session.get(User, log.processed_by)
        entry = session.get(Entry, log.entry_id) if log.entry_id else None
        
        log_data.append({
            "id": str(log.id),
            "amount_cents": log.amount_cents,
            "reason": log.reason,
            "refund_type": log.refund_type,
            "processed_by_name": processor.name if processor else "System",
            "entry_name": f"Entry #{entry.competitor_number}" if entry and entry.competitor_number else None,
            "created_at": log.created_at.isoformat(),
            "stripe_refund_id": log.stripe_refund_id
        })
    
    return {
        "order_id": str(order_id),
        "original_total_cents": order.total_cents,
        "refund_total_cents": order.refund_total_cents,
        "remaining_cents": order.total_cents - order.refund_total_cents,
        "status": order.status.value,
        "refund_logs": log_data
    }


def get_feis_refund_stats(
    session: Session,
    feis_id: UUID
) -> dict:
    """
    Get refund statistics for a feis.
    """
    orders = session.exec(
        select(Order).where(Order.feis_id == feis_id)
    ).all()
    
    total_orders = len(orders)
    total_revenue = sum(o.total_cents for o in orders)
    total_refunded = sum(o.refund_total_cents for o in orders)
    fully_refunded = sum(1 for o in orders if o.status == PaymentStatus.REFUNDED)
    partially_refunded = sum(1 for o in orders if o.status == PaymentStatus.PARTIAL_REFUND)
    
    return {
        "feis_id": str(feis_id),
        "total_orders": total_orders,
        "total_revenue_cents": total_revenue,
        "total_refunded_cents": total_refunded,
        "net_revenue_cents": total_revenue - total_refunded,
        "fully_refunded_orders": fully_refunded,
        "partially_refunded_orders": partially_refunded,
        "refund_rate_percent": round((total_refunded / total_revenue) * 100, 1) if total_revenue > 0 else 0
    }

