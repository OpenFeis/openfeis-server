"""
Waitlist & Cap Enforcement Service for Open Feis.

Manages competition and feis capacity limits with automatic waitlisting.
When spots become available (scratches/cancellations), offers are sent
to the next person in line.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from sqlmodel import Session, select, func

from backend.scoring_engine.models_platform import (
    Feis, Competition, Entry, Dancer, User, FeisSettings,
    WaitlistEntry, WaitlistStatus, CheckInStatus
)


@dataclass
class CapacityInfo:
    """Information about current capacity status."""
    competition_id: Optional[str]
    feis_id: str
    current_count: int
    max_capacity: Optional[int]
    spots_remaining: Optional[int]
    is_full: bool
    waitlist_enabled: bool
    waitlist_count: int


def get_competition_capacity(
    session: Session,
    competition_id: UUID
) -> CapacityInfo:
    """
    Get capacity status for a specific competition.
    """
    competition = session.get(Competition, competition_id)
    if not competition:
        raise ValueError(f"Competition {competition_id} not found")
    
    # Count current entries (not cancelled)
    current_count = session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition_id)
        .where(Entry.cancelled == False)
    ).one()
    
    # Get feis settings for waitlist config
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == competition.feis_id)
    ).first()
    
    waitlist_enabled = settings.enable_waitlist if settings else True
    
    # Count waitlist entries
    waitlist_count = session.exec(
        select(func.count(WaitlistEntry.id))
        .where(WaitlistEntry.competition_id == competition_id)
        .where(WaitlistEntry.status == WaitlistStatus.WAITING)
    ).one()
    
    max_cap = competition.max_entries
    spots_remaining = None
    is_full = False
    
    if max_cap is not None:
        spots_remaining = max(0, max_cap - current_count)
        is_full = spots_remaining == 0
    
    return CapacityInfo(
        competition_id=str(competition_id),
        feis_id=str(competition.feis_id),
        current_count=current_count,
        max_capacity=max_cap,
        spots_remaining=spots_remaining,
        is_full=is_full,
        waitlist_enabled=waitlist_enabled,
        waitlist_count=waitlist_count
    )


def get_feis_capacity(
    session: Session,
    feis_id: UUID
) -> CapacityInfo:
    """
    Get global capacity status for a feis.
    """
    feis = session.get(Feis, feis_id)
    if not feis:
        raise ValueError(f"Feis {feis_id} not found")
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    # Count unique dancers with active entries (not cancelled)
    current_count = session.exec(
        select(func.count(func.distinct(Entry.dancer_id)))
        .join(Competition, Entry.competition_id == Competition.id)
        .where(Competition.feis_id == feis_id)
        .where(Entry.cancelled == False)
    ).one()
    
    waitlist_enabled = settings.enable_waitlist if settings else True
    global_cap = settings.global_dancer_cap if settings else None
    
    # Count global waitlist entries
    waitlist_count = session.exec(
        select(func.count(WaitlistEntry.id))
        .where(WaitlistEntry.feis_id == feis_id)
        .where(WaitlistEntry.competition_id.is_(None))  # Global waitlist
        .where(WaitlistEntry.status == WaitlistStatus.WAITING)
    ).one()
    
    spots_remaining = None
    is_full = False
    
    if global_cap is not None:
        spots_remaining = max(0, global_cap - current_count)
        is_full = spots_remaining == 0
    
    return CapacityInfo(
        competition_id=None,
        feis_id=str(feis_id),
        current_count=current_count,
        max_capacity=global_cap,
        spots_remaining=spots_remaining,
        is_full=is_full,
        waitlist_enabled=waitlist_enabled,
        waitlist_count=waitlist_count
    )


def check_can_register(
    session: Session,
    feis_id: UUID,
    dancer_id: UUID,
    competition_id: Optional[UUID] = None
) -> Tuple[bool, str, Optional[CapacityInfo]]:
    """
    Check if a dancer can register for a competition or feis.
    
    Returns (can_register, message, capacity_info).
    If can_register is False and capacity_info shows is_full,
    the caller may want to offer waitlist registration.
    """
    # Check global feis capacity first
    feis_cap = get_feis_capacity(session, feis_id)
    
    if feis_cap.is_full:
        return False, "Feis has reached maximum capacity", feis_cap
    
    # Check competition-specific capacity if provided
    if competition_id:
        comp_cap = get_competition_capacity(session, competition_id)
        
        if comp_cap.is_full:
            return False, "Competition has reached maximum entries", comp_cap
    
    return True, "Registration available", None


def add_to_waitlist(
    session: Session,
    feis_id: UUID,
    dancer_id: UUID,
    user_id: UUID,
    competition_id: Optional[UUID] = None
) -> WaitlistEntry:
    """
    Add a dancer to the waitlist.
    
    If competition_id is None, adds to the global feis waitlist.
    """
    # Get the next position
    existing_query = select(func.max(WaitlistEntry.position)).where(
        WaitlistEntry.feis_id == feis_id,
        WaitlistEntry.status == WaitlistStatus.WAITING
    )
    
    if competition_id:
        existing_query = existing_query.where(WaitlistEntry.competition_id == competition_id)
    else:
        existing_query = existing_query.where(WaitlistEntry.competition_id.is_(None))
    
    max_position = session.exec(existing_query).one() or 0
    
    # Check if already on waitlist
    check_query = select(WaitlistEntry).where(
        WaitlistEntry.feis_id == feis_id,
        WaitlistEntry.dancer_id == dancer_id,
        WaitlistEntry.status == WaitlistStatus.WAITING
    )
    
    if competition_id:
        check_query = check_query.where(WaitlistEntry.competition_id == competition_id)
    else:
        check_query = check_query.where(WaitlistEntry.competition_id.is_(None))
    
    existing = session.exec(check_query).first()
    if existing:
        return existing  # Already on waitlist
    
    # Create waitlist entry
    entry = WaitlistEntry(
        feis_id=feis_id,
        dancer_id=dancer_id,
        competition_id=competition_id,
        user_id=user_id,
        position=max_position + 1,
        status=WaitlistStatus.WAITING
    )
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return entry


def get_user_waitlist_entries(
    session: Session,
    user_id: UUID,
    feis_id: Optional[UUID] = None
) -> List[WaitlistEntry]:
    """Get all waitlist entries for a user's dancers."""
    # Get all dancer IDs for this user
    dancers = session.exec(
        select(Dancer.id).where(Dancer.parent_id == user_id)
    ).all()
    
    if not dancers:
        return []
    
    query = select(WaitlistEntry).where(
        WaitlistEntry.dancer_id.in_(dancers)
    )
    
    if feis_id:
        query = query.where(WaitlistEntry.feis_id == feis_id)
    
    return session.exec(query.order_by(WaitlistEntry.created_at.desc())).all()


def process_spot_available(
    session: Session,
    feis_id: UUID,
    competition_id: Optional[UUID] = None
) -> Optional[WaitlistEntry]:
    """
    Process when a spot becomes available (e.g., someone scratches).
    
    Finds the next person in line and sends them an offer.
    Returns the waitlist entry that received the offer, or None if no one waiting.
    """
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    offer_hours = settings.waitlist_offer_hours if settings else 48
    
    # Find next in line
    query = select(WaitlistEntry).where(
        WaitlistEntry.feis_id == feis_id,
        WaitlistEntry.status == WaitlistStatus.WAITING
    )
    
    if competition_id:
        query = query.where(WaitlistEntry.competition_id == competition_id)
    else:
        query = query.where(WaitlistEntry.competition_id.is_(None))
    
    query = query.order_by(WaitlistEntry.position)
    
    next_in_line = session.exec(query).first()
    
    if not next_in_line:
        return None
    
    # Send offer (set expiration time)
    next_in_line.offer_sent_at = datetime.utcnow()
    next_in_line.offer_expires_at = datetime.utcnow() + timedelta(hours=offer_hours)
    next_in_line.updated_at = datetime.utcnow()
    
    session.add(next_in_line)
    session.commit()
    session.refresh(next_in_line)
    
    # TODO: Send email notification to the user
    
    return next_in_line


def accept_waitlist_offer(
    session: Session,
    waitlist_id: UUID,
    user_id: UUID
) -> Tuple[bool, str, Optional[Entry]]:
    """
    Accept a waitlist offer and create the entry.
    
    Returns (success, message, created_entry).
    """
    waitlist = session.get(WaitlistEntry, waitlist_id)
    
    if not waitlist:
        return False, "Waitlist entry not found", None
    
    # Verify user owns this waitlist entry
    dancer = session.get(Dancer, waitlist.dancer_id)
    if not dancer or dancer.parent_id != user_id:
        return False, "Not authorized to accept this offer", None
    
    # Check if offer has expired
    if waitlist.offer_expires_at and datetime.utcnow() > waitlist.offer_expires_at:
        waitlist.status = WaitlistStatus.EXPIRED
        session.add(waitlist)
        session.commit()
        return False, "Offer has expired", None
    
    # Check if already accepted
    if waitlist.status != WaitlistStatus.WAITING:
        return False, f"Offer already {waitlist.status.value}", None
    
    # Check capacity again (in case multiple spots were filled)
    if waitlist.competition_id:
        cap = get_competition_capacity(session, waitlist.competition_id)
        if cap.is_full:
            return False, "Competition is now full, offer expired", None
    else:
        cap = get_feis_capacity(session, waitlist.feis_id)
        if cap.is_full:
            return False, "Feis is now full, offer expired", None
    
    # Create the entry (if competition-specific)
    entry = None
    if waitlist.competition_id:
        entry = Entry(
            dancer_id=waitlist.dancer_id,
            competition_id=waitlist.competition_id,
            paid=False,
            pay_later=True  # From waitlist = pay later by default
        )
        session.add(entry)
        session.flush()
        waitlist.promoted_entry_id = entry.id
    
    # Update waitlist status
    waitlist.status = WaitlistStatus.PROMOTED
    waitlist.offer_accepted_at = datetime.utcnow()
    waitlist.updated_at = datetime.utcnow()
    
    session.add(waitlist)
    session.commit()
    
    if entry:
        session.refresh(entry)
    
    return True, "Successfully accepted waitlist offer", entry


def cancel_waitlist_entry(
    session: Session,
    waitlist_id: UUID,
    user_id: UUID
) -> Tuple[bool, str]:
    """
    Cancel a waitlist entry.
    """
    waitlist = session.get(WaitlistEntry, waitlist_id)
    
    if not waitlist:
        return False, "Waitlist entry not found"
    
    # Verify user owns this waitlist entry
    dancer = session.get(Dancer, waitlist.dancer_id)
    if not dancer or dancer.parent_id != user_id:
        return False, "Not authorized to cancel this entry"
    
    waitlist.status = WaitlistStatus.CANCELLED
    waitlist.updated_at = datetime.utcnow()
    
    session.add(waitlist)
    session.commit()
    
    # Reorder positions for remaining entries
    _reorder_waitlist(session, waitlist.feis_id, waitlist.competition_id)
    
    return True, "Waitlist entry cancelled"


def _reorder_waitlist(
    session: Session,
    feis_id: UUID,
    competition_id: Optional[UUID]
):
    """Reorder waitlist positions after a cancellation."""
    query = select(WaitlistEntry).where(
        WaitlistEntry.feis_id == feis_id,
        WaitlistEntry.status == WaitlistStatus.WAITING
    )
    
    if competition_id:
        query = query.where(WaitlistEntry.competition_id == competition_id)
    else:
        query = query.where(WaitlistEntry.competition_id.is_(None))
    
    entries = session.exec(query.order_by(WaitlistEntry.position)).all()
    
    for i, entry in enumerate(entries, start=1):
        if entry.position != i:
            entry.position = i
            session.add(entry)
    
    session.commit()


def expire_stale_offers(session: Session) -> int:
    """
    Expire any waitlist offers that have passed their expiration time.
    Called periodically by a background task.
    
    Returns the number of offers expired.
    """
    now = datetime.utcnow()
    
    stale_offers = session.exec(
        select(WaitlistEntry).where(
            WaitlistEntry.status == WaitlistStatus.WAITING,
            WaitlistEntry.offer_sent_at.isnot(None),
            WaitlistEntry.offer_expires_at < now
        )
    ).all()
    
    for offer in stale_offers:
        offer.status = WaitlistStatus.EXPIRED
        offer.updated_at = now
        session.add(offer)
        
        # Offer the spot to the next person
        process_spot_available(
            session,
            offer.feis_id,
            offer.competition_id
        )
    
    session.commit()
    
    return len(stale_offers)

