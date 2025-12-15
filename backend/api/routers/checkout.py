from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import User, Feis, Order, Entry, FeeItem, RoleType, PaymentStatus
from backend.api.schemas import (
    CartCalculationRequest, CartCalculationResponse, CartLineItemResponse,
    CheckoutRequest, CheckoutResponse,
    OrderResponse,
    FeeItemCreate, FeeItemUpdate, FeeItemResponse,
    RefundRequest, RefundResponse, RefundLogResponse, OrderRefundSummary
)
from backend.services.cart import calculate_cart, create_order
from backend.services.stripe import create_checkout_session, handle_checkout_success
from backend.services.email import get_site_settings
from backend.services.refund import process_full_refund, process_partial_refund, get_order_refund_summary

router = APIRouter()

def get_cart_feis_settings(session, feis_id):
    from backend.scoring_engine.models_platform import FeisSettings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    if not settings:
        settings = FeisSettings(feis_id=feis_id)
        session.add(settings)
        session.commit()
    return settings

def is_registration_open(settings):
    from datetime import datetime
    now = datetime.utcnow()
    if settings.registration_opens and now < settings.registration_opens:
        return False, "Registration has not opened yet"
    if settings.registration_closes and now > settings.registration_closes:
        return False, "Registration is closed"
    return True, "Registration is open"

def is_late_registration(settings):
    from datetime import datetime
    if not settings.late_fee_date:
        return False
    return datetime.utcnow() > settings.late_fee_date

def is_organizer_connected(feis, session):
    return bool(feis.stripe_account_id), None

def is_stripe_configured():
    import os
    return bool(os.getenv("STRIPE_SECRET_KEY"))

@router.post("/cart/calculate", response_model=CartCalculationResponse)
async def calculate_cart_totals(
    cart_data: CartCalculationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Calculate cart totals."""
    competition_ids = [UUID(item.competition_id) for item in cart_data.items]
    dancer_ids = [UUID(item.dancer_id) for item in cart_data.items]
    
    try:
        cart_totals = calculate_cart(
            session=session,
            feis_id=UUID(cart_data.feis_id),
            user_id=current_user.id,
            competition_ids=competition_ids,
            dancer_ids=dancer_ids,
            fee_item_quantities=cart_data.fee_items
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return CartCalculationResponse(
        line_items=[
            CartLineItemResponse(
                id=li.id,
                type=li.type,
                name=li.name,
                description=li.description,
                dancer_id=li.dancer_id,
                dancer_name=li.dancer_name,
                unit_price_cents=li.unit_price_cents,
                quantity=li.quantity,
                total_cents=li.total_cents,
                category=li.category
            )
            for li in cart_totals.line_items
        ],
        qualifying_subtotal_cents=cart_totals.qualifying_subtotal_cents,
        non_qualifying_subtotal_cents=cart_totals.non_qualifying_subtotal_cents,
        subtotal_cents=cart_totals.subtotal_cents,
        family_discount_cents=cart_totals.family_discount_cents,
        family_cap_applied=cart_totals.family_cap_applied,
        family_cap_cents=cart_totals.family_cap_cents,
        late_fee_cents=cart_totals.late_fee_cents,
        late_fee_applied=cart_totals.late_fee_applied,
        late_fee_date=cart_totals.late_fee_date,
        total_cents=cart_totals.total_cents,
        dancer_count=cart_totals.dancer_count,
        competition_count=cart_totals.competition_count,
        savings_percent=cart_totals.savings_percent
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    checkout_data: CheckoutRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Start checkout process."""
    from backend.scoring_engine.models_platform import Dancer
    
    feis = session.get(Feis, UUID(checkout_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check registration is open
    settings = get_cart_feis_settings(session, feis.id)
    is_open, message = is_registration_open(settings)
    if not is_open:
        raise HTTPException(status_code=400, detail=message)
    
    # Validate dancers belong to current user
    competition_ids = [UUID(item.competition_id) for item in checkout_data.items]
    dancer_ids = [UUID(item.dancer_id) for item in checkout_data.items]
    
    for dancer_id in set(dancer_ids):
        dancer = session.get(Dancer, dancer_id)
        if not dancer:
            raise HTTPException(status_code=404, detail=f"Dancer not found")
        if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    # Calculate cart
    try:
        cart_totals = calculate_cart(
            session=session,
            feis_id=feis.id,
            user_id=current_user.id,
            competition_ids=competition_ids,
            dancer_ids=dancer_ids,
            fee_item_quantities=checkout_data.fee_items
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create order
    order = create_order(
        session=session,
        feis_id=feis.id,
        user_id=current_user.id,
        cart_totals=cart_totals,
        pay_at_door=checkout_data.pay_at_door
    )
    
    if checkout_data.pay_at_door:
        return CheckoutResponse(
            success=True,
            order_id=str(order.id),
            checkout_url=None,
            is_test_mode=False,
            message=f"Registration complete! Please pay ${order.total_cents / 100:.2f} at check-in."
        )
    
    # Online payment - create Stripe checkout session
    site_settings = get_site_settings(session)
    base_url = site_settings.site_url
    
    success_url = f"{base_url}/registration/success"
    cancel_url = f"{base_url}/registration/cancel"
    
    result = create_checkout_session(
        session=session,
        order=order,
        cart_totals=cart_totals,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    if not result.success:
        return CheckoutResponse(
            success=False,
            order_id=str(order.id),
            checkout_url=None,
            is_test_mode=result.is_test_mode,
            message=result.error or "Failed to create checkout session"
        )
    
    return CheckoutResponse(
        success=True,
        order_id=str(order.id),
        checkout_url=result.checkout_url,
        is_test_mode=result.is_test_mode,
        message="Redirecting to payment..." if not result.is_test_mode else "Test mode: Simulating successful payment"
    )


@router.get("/checkout/success")
async def checkout_success(
    session_id: str,
    test_mode: bool = False,
    session: Session = Depends(get_session)
):
    """Handle successful checkout return."""
    success, order, error = handle_checkout_success(
        session=session,
        checkout_session_id=session_id,
        is_test_mode=test_mode
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=error or "Payment verification failed")
    
    return {
        "success": True,
        "order_id": str(order.id),
        "message": "Payment successful! Your registration is confirmed."
    }


@router.get("/orders", response_model=List[OrderResponse])
async def list_my_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    feis_id: Optional[str] = None
):
    """List orders for the current user."""
    statement = select(Order).where(Order.user_id == current_user.id)
    
    if feis_id:
        statement = statement.where(Order.feis_id == UUID(feis_id))
    
    statement = statement.order_by(Order.created_at.desc())
    orders = session.exec(statement).all()
    
    result = []
    for order in orders:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.order_id == order.id)
        ).one()
        
        result.append(OrderResponse(
            id=str(order.id),
            feis_id=str(order.feis_id),
            user_id=str(order.user_id),
            subtotal_cents=order.subtotal_cents,
            qualifying_subtotal_cents=order.qualifying_subtotal_cents,
            non_qualifying_subtotal_cents=order.non_qualifying_subtotal_cents,
            family_discount_cents=order.family_discount_cents,
            late_fee_cents=order.late_fee_cents,
            total_cents=order.total_cents,
            status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            entry_count=entry_count
        ))
    
    return result


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check ownership
    if order.user_id != current_user.id and current_user.role not in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.order_id == order.id)
    ).one()
    
    return OrderResponse(
        id=str(order.id),
        feis_id=str(order.feis_id),
        user_id=str(order.user_id),
        subtotal_cents=order.subtotal_cents,
        qualifying_subtotal_cents=order.qualifying_subtotal_cents,
        non_qualifying_subtotal_cents=order.non_qualifying_subtotal_cents,
        family_discount_cents=order.family_discount_cents,
        late_fee_cents=order.late_fee_cents,
        total_cents=order.total_cents,
        status=order.status,
        created_at=order.created_at,
        paid_at=order.paid_at,
        entry_count=entry_count
    )


# ============= Refund Routes =============

@router.post("/orders/{order_id}/refund", response_model=RefundResponse)
async def refund_order(
    order_id: str,
    request: RefundRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Process a refund for an order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if request.entry_ids:
        # Partial refund
        entry_uuids = [UUID(eid) for eid in request.entry_ids]
        result = process_partial_refund(
            session, UUID(order_id), entry_uuids, current_user.id,
            request.reason, request.refund_amount_cents
        )
    else:
        # Full refund
        result = process_full_refund(
            session, UUID(order_id), current_user.id, request.reason
        )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return RefundResponse(
        order_id=result.order_id,
        refund_amount_cents=result.refund_amount_cents,
        refund_type=result.refund_type,
        stripe_refund_id=result.stripe_refund_id,
        entries_refunded=result.entries_affected,
        message=result.message
    )


@router.get("/orders/{order_id}/refunds", response_model=OrderRefundSummary)
async def get_order_refunds(
    order_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get refund summary for an order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify user owns this order or is admin
    is_owner = order.user_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    
    summary = get_order_refund_summary(session, UUID(order_id))
    
    logs = [
        RefundLogResponse(
            id=log["id"],
            order_id=order_id,
            entry_id=log.get("entry_name"),
            amount_cents=log["amount_cents"],
            reason=log["reason"],
            refund_type=log["refund_type"],
            processed_by_name=log["processed_by_name"],
            created_at=datetime.fromisoformat(log["created_at"])
        )
        for log in summary["refund_logs"]
    ]
    
    return OrderRefundSummary(
        order_id=order_id,
        original_total_cents=summary["original_total_cents"],
        refund_total_cents=summary["refund_total_cents"],
        remaining_cents=summary["remaining_cents"],
        status=PaymentStatus(summary["status"]),
        refund_logs=logs
    )
