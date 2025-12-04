"""
Advancement Rules Engine for Open Feis.

Implements CLRG/NAFC advancement rules to automatically track level progression.
Detects when dancers have "won out" and should advance to the next level.

Rules overview:
- Beginner: 1st place advances to Novice (for ALL dances)
- Novice: 1st place advances to Prizewinner (per dance OR all dances, configurable)
- Prizewinner: 1st place advances to Championship (per dance OR all dances, configurable)
- Championship: No automatic advancement (perpetual level)
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from uuid import UUID
from sqlmodel import Session, select, func

from backend.scoring_engine.models_platform import (
    Dancer, Competition, Entry, Feis, PlacementHistory, AdvancementNotice,
    CompetitionLevel, DanceType
)


@dataclass
class AdvancementRule:
    """Configuration for an advancement rule."""
    level: CompetitionLevel
    wins_required: int
    next_level: CompetitionLevel
    per_dance: bool  # If True, advancement is per-dance (Novice → PW for Reel only)
    description: str


# Default CLRG-style advancement rules
ADVANCEMENT_RULES: Dict[CompetitionLevel, AdvancementRule] = {
    CompetitionLevel.BEGINNER: AdvancementRule(
        level=CompetitionLevel.BEGINNER,
        wins_required=1,
        next_level=CompetitionLevel.NOVICE,
        per_dance=False,  # Winning at Beginner advances for all dances
        description="1st place at Beginner advances to Novice for all dances"
    ),
    CompetitionLevel.NOVICE: AdvancementRule(
        level=CompetitionLevel.NOVICE,
        wins_required=1,
        next_level=CompetitionLevel.PRIZEWINNER,
        per_dance=True,  # Winning at Novice advances for that dance only
        description="1st place at Novice advances to Prizewinner for that dance"
    ),
    CompetitionLevel.PRIZEWINNER: AdvancementRule(
        level=CompetitionLevel.PRIZEWINNER,
        wins_required=1,
        next_level=CompetitionLevel.CHAMPIONSHIP,
        per_dance=True,  # Winning at Prizewinner advances for that dance only
        description="1st place at Prizewinner advances to Championship for that dance"
    ),
    # Championship has no automatic advancement
}


def get_advancement_rules() -> List[AdvancementRule]:
    """Return all advancement rules."""
    return list(ADVANCEMENT_RULES.values())


def get_rule_for_level(level: CompetitionLevel) -> Optional[AdvancementRule]:
    """Get the advancement rule for a specific level."""
    return ADVANCEMENT_RULES.get(level)


def check_advancement(
    session: Session,
    dancer: Dancer
) -> List[AdvancementNotice]:
    """
    Check if a dancer should advance based on their placement history.
    
    Returns a list of any new advancement notices that should be created.
    This does NOT create the notices - that's up to the caller.
    """
    new_notices: List[AdvancementNotice] = []
    
    # Get the rule for the dancer's current level
    rule = get_rule_for_level(dancer.current_level)
    if not rule:
        # Championship or unknown level - no automatic advancement
        return []
    
    # Get existing advancement notices for this dancer
    existing_notices = session.exec(
        select(AdvancementNotice)
        .where(AdvancementNotice.dancer_id == dancer.id)
        .where(AdvancementNotice.from_level == dancer.current_level)
    ).all()
    
    # Get 1st place placements at the dancer's current level
    first_places = session.exec(
        select(PlacementHistory)
        .where(PlacementHistory.dancer_id == dancer.id)
        .where(PlacementHistory.level == dancer.current_level)
        .where(PlacementHistory.rank == 1)
        .order_by(PlacementHistory.competition_date.desc())
    ).all()
    
    if not first_places:
        return []
    
    if rule.per_dance:
        # Per-dance advancement: check each dance type separately
        dance_types_won = set()
        for placement in first_places:
            if placement.dance_type:
                dance_types_won.add(placement.dance_type)
        
        # Check for existing notices for each dance type
        existing_dance_types = set()
        for notice in existing_notices:
            if notice.dance_type:
                existing_dance_types.add(notice.dance_type)
        
        # Create notices for newly won dance types
        for dance_type in dance_types_won:
            if dance_type not in existing_dance_types:
                # Find the triggering placement
                triggering = next(
                    (p for p in first_places if p.dance_type == dance_type),
                    None
                )
                
                notice = AdvancementNotice(
                    dancer_id=dancer.id,
                    from_level=dancer.current_level,
                    to_level=rule.next_level,
                    dance_type=dance_type,
                    triggering_placement_id=triggering.id if triggering else None
                )
                new_notices.append(notice)
    else:
        # All-dances advancement: any 1st place advances for all dances
        # Check if there's already a notice for this level (no dance type)
        has_existing = any(n.dance_type is None for n in existing_notices)
        
        if not has_existing and len(first_places) >= rule.wins_required:
            notice = AdvancementNotice(
                dancer_id=dancer.id,
                from_level=dancer.current_level,
                to_level=rule.next_level,
                dance_type=None,  # All dances
                triggering_placement_id=first_places[0].id
            )
            new_notices.append(notice)
    
    return new_notices


def process_advancement(
    session: Session,
    dancer: Dancer
) -> List[AdvancementNotice]:
    """
    Check and create advancement notices for a dancer.
    
    This is the main entry point - it checks for advancements and
    persists any new notices to the database.
    """
    new_notices = check_advancement(session, dancer)
    
    for notice in new_notices:
        session.add(notice)
    
    if new_notices:
        session.commit()
        for notice in new_notices:
            session.refresh(notice)
    
    return new_notices


def get_pending_advancements(
    session: Session,
    dancer_id: UUID
) -> List[AdvancementNotice]:
    """Get all unacknowledged advancement notices for a dancer."""
    return session.exec(
        select(AdvancementNotice)
        .where(AdvancementNotice.dancer_id == dancer_id)
        .where(AdvancementNotice.acknowledged == False)
        .where(AdvancementNotice.overridden == False)
        .order_by(AdvancementNotice.created_at.desc())
    ).all()


def get_all_advancements(
    session: Session,
    dancer_id: UUID
) -> List[AdvancementNotice]:
    """Get all advancement notices for a dancer (including acknowledged)."""
    return session.exec(
        select(AdvancementNotice)
        .where(AdvancementNotice.dancer_id == dancer_id)
        .order_by(AdvancementNotice.created_at.desc())
    ).all()


def acknowledge_advancement(
    session: Session,
    notice_id: UUID,
    user_id: UUID
) -> AdvancementNotice:
    """Mark an advancement notice as acknowledged."""
    notice = session.get(AdvancementNotice, notice_id)
    if not notice:
        raise ValueError(f"Advancement notice {notice_id} not found")
    
    notice.acknowledged = True
    notice.acknowledged_at = datetime.utcnow()
    notice.acknowledged_by = user_id
    
    session.add(notice)
    session.commit()
    session.refresh(notice)
    
    return notice


def override_advancement(
    session: Session,
    notice_id: UUID,
    user_id: UUID,
    reason: str
) -> AdvancementNotice:
    """
    Override an advancement requirement (admin function).
    
    This allows a dancer to continue competing at their current level
    despite having "won out".
    """
    notice = session.get(AdvancementNotice, notice_id)
    if not notice:
        raise ValueError(f"Advancement notice {notice_id} not found")
    
    notice.overridden = True
    notice.overridden_by = user_id
    notice.override_reason = reason
    
    session.add(notice)
    session.commit()
    session.refresh(notice)
    
    return notice


def get_eligible_levels(
    session: Session,
    dancer: Dancer
) -> Tuple[List[CompetitionLevel], List[str]]:
    """
    Determine which levels a dancer is eligible to compete at.
    
    Returns (eligible_levels, warnings).
    
    A dancer is typically only eligible for their current level, unless:
    - They have pending advancements that haven't been acknowledged
    - An admin has overridden an advancement requirement
    """
    warnings: List[str] = []
    eligible = [dancer.current_level]
    
    # Check for pending advancements
    pending = get_pending_advancements(session, dancer.id)
    
    if pending:
        # Dancer has won out but hasn't been moved up yet
        for notice in pending:
            if notice.dance_type:
                warnings.append(
                    f"Won out at {notice.from_level.value} for {notice.dance_type.value}. "
                    f"Should advance to {notice.to_level.value}."
                )
            else:
                warnings.append(
                    f"Won out at {notice.from_level.value}. "
                    f"Should advance to {notice.to_level.value}."
                )
    
    return eligible, warnings


def check_registration_eligibility(
    session: Session,
    dancer: Dancer,
    competition: Competition
) -> Tuple[bool, str]:
    """
    Check if a dancer is eligible to register for a specific competition.
    
    Returns (is_eligible, message).
    
    This considers:
    - Current level matches competition level
    - No pending advancements that would disqualify
    - Admin overrides
    """
    # Basic level check
    if dancer.current_level != competition.level:
        return False, f"Dancer is {dancer.current_level.value}, competition is {competition.level.value}"
    
    # Check for pending advancements
    pending = get_pending_advancements(session, dancer.id)
    
    for notice in pending:
        if notice.from_level == competition.level:
            if notice.dance_type is None:
                # All-dance advancement - can't compete at this level at all
                return False, (
                    f"Dancer has won out at {competition.level.value} and should advance to "
                    f"{notice.to_level.value}. Contact organizer for override if needed."
                )
            elif notice.dance_type == competition.dance_type:
                # Per-dance advancement - can't compete at this level for this dance
                return False, (
                    f"Dancer has won out at {competition.level.value} for {competition.dance_type.value} "
                    f"and should advance to {notice.to_level.value}."
                )
    
    return True, "Eligible"


def record_placement_and_check_advancement(
    session: Session,
    entry: Entry,
    rank: int,
    irish_points: Optional[float] = None
) -> Tuple[PlacementHistory, List[AdvancementNotice]]:
    """
    Record a placement and check for resulting advancements.
    
    This is the main function called when results are finalized.
    
    Returns (placement_record, new_advancements).
    """
    # Get related objects
    competition = session.get(Competition, entry.competition_id)
    dancer = session.get(Dancer, entry.dancer_id)
    feis = session.get(Feis, competition.feis_id)
    
    # Create placement record
    placement = PlacementHistory(
        dancer_id=dancer.id,
        competition_id=competition.id,
        feis_id=feis.id,
        entry_id=entry.id,
        rank=rank,
        irish_points=irish_points,
        dance_type=competition.dance_type,
        level=competition.level,
        competition_date=feis.date
    )
    
    session.add(placement)
    session.commit()
    session.refresh(placement)
    
    # Check for advancements (only for 1st place)
    new_advancements = []
    if rank == 1:
        new_advancements = process_advancement(session, dancer)
        
        # Mark the placement as having triggered advancement
        if new_advancements:
            placement.triggered_advancement = True
            placement.advancement_processed_at = datetime.utcnow()
            session.add(placement)
            session.commit()
            session.refresh(placement)
    
    return placement, new_advancements


def get_dancer_placement_summary(
    session: Session,
    dancer_id: UUID
) -> Dict:
    """
    Get a summary of a dancer's placement history.
    
    Returns dict with total placements, 1st place count, etc.
    """
    placements = session.exec(
        select(PlacementHistory)
        .where(PlacementHistory.dancer_id == dancer_id)
        .order_by(PlacementHistory.competition_date.desc())
    ).all()
    
    first_places = [p for p in placements if p.rank == 1]
    podiums = [p for p in placements if p.rank <= 3]
    
    # Group by level
    by_level: Dict[str, int] = {}
    for p in placements:
        level_key = p.level.value
        by_level[level_key] = by_level.get(level_key, 0) + 1
    
    # Group by dance type
    by_dance: Dict[str, int] = {}
    for p in first_places:
        if p.dance_type:
            dance_key = p.dance_type.value
            by_dance[dance_key] = by_dance.get(dance_key, 0) + 1
    
    return {
        "dancer_id": str(dancer_id),
        "total_placements": len(placements),
        "first_place_count": len(first_places),
        "podium_count": len(podiums),
        "by_level": by_level,
        "first_places_by_dance": by_dance
    }

