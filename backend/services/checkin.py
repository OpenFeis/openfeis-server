"""
Check-In & Stage Monitor Service for Open Feis.

Manages dancer check-in at the event and provides stage monitor
data for displaying "Now Dancing" and "On Deck" information.
"""

from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from sqlmodel import Session, select, func

from backend.scoring_engine.models_platform import (
    Entry, Competition, Dancer, Feis, Stage, User,
    CheckInStatus
)


@dataclass
class CheckInResult:
    """Result of a check-in operation."""
    success: bool
    entry_id: str
    dancer_name: str
    competitor_number: Optional[int]
    competition_name: str
    status: CheckInStatus
    message: str


@dataclass
class StageMonitorData:
    """Data for the stage monitor display."""
    competition_id: str
    competition_name: str
    stage_name: Optional[str]
    feis_name: str
    total_entries: int
    checked_in_count: int
    scratched_count: int
    not_checked_in_count: int
    current_position: int  # Which entry we're on
    entries: List[dict]


def check_in_entry(
    session: Session,
    entry_id: UUID,
    checked_in_by: UUID
) -> CheckInResult:
    """
    Check in a dancer for their competition.
    """
    entry = session.get(Entry, entry_id)
    
    if not entry:
        return CheckInResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name="Unknown",
            competitor_number=None,
            competition_name="Unknown",
            status=CheckInStatus.NOT_CHECKED_IN,
            message="Entry not found"
        )
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    # Check if already scratched
    if entry.cancelled:
        return CheckInResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competitor_number=entry.competitor_number,
            competition_name=competition.name if competition else "Unknown",
            status=CheckInStatus.SCRATCHED,
            message="Entry has been scratched/cancelled"
        )
    
    # Check if already checked in
    if entry.check_in_status == CheckInStatus.CHECKED_IN:
        return CheckInResult(
            success=True,
            entry_id=str(entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competitor_number=entry.competitor_number,
            competition_name=competition.name if competition else "Unknown",
            status=CheckInStatus.CHECKED_IN,
            message="Already checked in"
        )
    
    # Perform check-in
    entry.check_in_status = CheckInStatus.CHECKED_IN
    entry.checked_in_at = datetime.utcnow()
    entry.checked_in_by = checked_in_by
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return CheckInResult(
        success=True,
        entry_id=str(entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=competition.name if competition else "Unknown",
        status=CheckInStatus.CHECKED_IN,
        message="Successfully checked in"
    )


def check_in_by_number(
    session: Session,
    competition_id: UUID,
    competitor_number: int,
    checked_in_by: UUID
) -> CheckInResult:
    """
    Check in a dancer by their competitor number.
    """
    entry = session.exec(
        select(Entry).where(
            Entry.competition_id == competition_id,
            Entry.competitor_number == competitor_number
        )
    ).first()
    
    if not entry:
        return CheckInResult(
            success=False,
            entry_id="",
            dancer_name="Unknown",
            competitor_number=competitor_number,
            competition_name="Unknown",
            status=CheckInStatus.NOT_CHECKED_IN,
            message=f"No entry found with number {competitor_number}"
        )
    
    return check_in_entry(session, entry.id, checked_in_by)


def bulk_check_in(
    session: Session,
    entry_ids: List[UUID],
    checked_in_by: UUID
) -> List[CheckInResult]:
    """
    Check in multiple dancers at once.
    """
    results = []
    for entry_id in entry_ids:
        result = check_in_entry(session, entry_id, checked_in_by)
        results.append(result)
    return results


def undo_check_in(
    session: Session,
    entry_id: UUID
) -> CheckInResult:
    """
    Undo a check-in (mark as not checked in).
    """
    entry = session.get(Entry, entry_id)
    
    if not entry:
        return CheckInResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name="Unknown",
            competitor_number=None,
            competition_name="Unknown",
            status=CheckInStatus.NOT_CHECKED_IN,
            message="Entry not found"
        )
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    entry.check_in_status = CheckInStatus.NOT_CHECKED_IN
    entry.checked_in_at = None
    entry.checked_in_by = None
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return CheckInResult(
        success=True,
        entry_id=str(entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=competition.name if competition else "Unknown",
        status=CheckInStatus.NOT_CHECKED_IN,
        message="Check-in undone"
    )


def mark_scratched(
    session: Session,
    entry_id: UUID,
    reason: str
) -> CheckInResult:
    """
    Mark a dancer as scratched (no-show / cancelled at event).
    """
    entry = session.get(Entry, entry_id)
    
    if not entry:
        return CheckInResult(
            success=False,
            entry_id=str(entry_id),
            dancer_name="Unknown",
            competitor_number=None,
            competition_name="Unknown",
            status=CheckInStatus.NOT_CHECKED_IN,
            message="Entry not found"
        )
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    entry.check_in_status = CheckInStatus.SCRATCHED
    entry.cancelled = True
    entry.cancelled_at = datetime.utcnow()
    entry.cancellation_reason = reason
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return CheckInResult(
        success=True,
        entry_id=str(entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competitor_number=entry.competitor_number,
        competition_name=competition.name if competition else "Unknown",
        status=CheckInStatus.SCRATCHED,
        message="Marked as scratched"
    )


def get_stage_monitor_data(
    session: Session,
    competition_id: UUID,
    current_position: int = 0
) -> StageMonitorData:
    """
    Get data for the stage monitor display.
    
    current_position indicates which dancer is currently performing (0-indexed).
    """
    competition = session.get(Competition, competition_id)
    if not competition:
        raise ValueError(f"Competition {competition_id} not found")
    
    feis = session.get(Feis, competition.feis_id)
    stage = session.get(Stage, competition.stage_id) if competition.stage_id else None
    
    # Get all entries sorted by competitor number
    entries = session.exec(
        select(Entry)
        .where(Entry.competition_id == competition_id)
        .order_by(Entry.competitor_number)
    ).all()
    
    # Build entry list with dancer info
    entry_data = []
    checked_in_count = 0
    scratched_count = 0
    not_checked_in_count = 0
    
    for i, entry in enumerate(entries):
        dancer = session.get(Dancer, entry.dancer_id)
        school = None
        if dancer and dancer.school_id:
            teacher = session.get(User, dancer.school_id)
            school = teacher.name if teacher else None
        
        status = entry.check_in_status
        if entry.cancelled:
            status = CheckInStatus.SCRATCHED
            scratched_count += 1
        elif status == CheckInStatus.CHECKED_IN:
            checked_in_count += 1
        else:
            not_checked_in_count += 1
        
        entry_data.append({
            "entry_id": str(entry.id),
            "competitor_number": entry.competitor_number,
            "dancer_name": dancer.name if dancer else "Unknown",
            "school_name": school,
            "check_in_status": status.value,
            "is_current": i == current_position,
            "is_on_deck": i == current_position + 1 or i == current_position + 2,
            "position": i
        })
    
    return StageMonitorData(
        competition_id=str(competition_id),
        competition_name=competition.name,
        stage_name=stage.name if stage else None,
        feis_name=feis.name if feis else "Unknown",
        total_entries=len(entries),
        checked_in_count=checked_in_count,
        scratched_count=scratched_count,
        not_checked_in_count=not_checked_in_count,
        current_position=current_position,
        entries=entry_data
    )


def get_competition_check_in_stats(
    session: Session,
    competition_id: UUID
) -> dict:
    """
    Get check-in statistics for a competition.
    """
    total = session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition_id)
    ).one()
    
    checked_in = session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition_id)
        .where(Entry.check_in_status == CheckInStatus.CHECKED_IN)
    ).one()
    
    scratched = session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition_id)
        .where(Entry.cancelled == True)
    ).one()
    
    return {
        "competition_id": str(competition_id),
        "total_entries": total,
        "checked_in": checked_in,
        "scratched": scratched,
        "not_checked_in": total - checked_in - scratched,
        "check_in_percent": round((checked_in / total) * 100, 1) if total > 0 else 0
    }


def get_feis_check_in_summary(
    session: Session,
    feis_id: UUID
) -> dict:
    """
    Get check-in summary for all competitions in a feis.
    """
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis_id)
    ).all()
    
    summary = {
        "feis_id": str(feis_id),
        "total_competitions": len(competitions),
        "total_entries": 0,
        "total_checked_in": 0,
        "total_scratched": 0,
        "competitions": []
    }
    
    for comp in competitions:
        stats = get_competition_check_in_stats(session, comp.id)
        summary["total_entries"] += stats["total_entries"]
        summary["total_checked_in"] += stats["checked_in"]
        summary["total_scratched"] += stats["scratched"]
        summary["competitions"].append({
            "competition_id": str(comp.id),
            "competition_name": comp.name,
            **stats
        })
    
    if summary["total_entries"] > 0:
        summary["overall_check_in_percent"] = round(
            (summary["total_checked_in"] / summary["total_entries"]) * 100, 1
        )
    else:
        summary["overall_check_in_percent"] = 0
    
    return summary


def lookup_entry_by_qr(
    session: Session,
    dancer_id: UUID,
    feis_id: Optional[UUID] = None
) -> List[Entry]:
    """
    Look up entries for a dancer (from QR code scan).
    
    If feis_id is provided, only returns entries for that feis.
    """
    query = select(Entry).where(Entry.dancer_id == dancer_id)
    
    if feis_id:
        query = query.join(Competition).where(Competition.feis_id == feis_id)
    
    return session.exec(query).all()

