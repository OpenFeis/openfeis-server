"""
Scheduling Service for Open Feis

Provides:
- Duration estimation for competitions
- Conflict detection (sibling, adjudicator, time overlap)
- Scheduling utilities
"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass
from sqlmodel import Session, select

from backend.scoring_engine.models_platform import (
    Competition, Entry, Dancer, Stage, Feis, User, DanceType,
    FeisAdjudicator, AdjudicatorAvailability, AvailabilityType
)


# Standard tempos for each dance type (beats per minute)
DANCE_TEMPOS: Dict[DanceType, int] = {
    DanceType.REEL: 113,
    DanceType.LIGHT_JIG: 115,
    DanceType.SLIP_JIG: 113,
    DanceType.TREBLE_JIG: 73,
    DanceType.HORNPIPE: 138,
    DanceType.TRADITIONAL_SET: 113,  # Varies, use reel tempo
    DanceType.CONTEMPORARY_SET: 113,  # Varies
    DanceType.TREBLE_REEL: 92,
}


def get_default_tempo(dance_type: Optional[DanceType]) -> int:
    """Get the default tempo for a dance type, or 113 (reel) if unknown."""
    if dance_type is None:
        return 113
    return DANCE_TEMPOS.get(dance_type, 113)


def estimate_duration(
    entry_count: int,
    bars: int = 48,
    tempo_bpm: int = 113,
    dancers_per_rotation: int = 2,
    setup_time_minutes: int = 2,
    transition_seconds: int = 15
) -> Tuple[int, int, str]:
    """
    Estimate competition duration in minutes.
    
    Formula: (entries / rotation) * (bars / tempo * 60) + setup
    
    Args:
        entry_count: Number of competitors
        bars: Number of bars danced
        tempo_bpm: Beats per minute
        dancers_per_rotation: How many dance at once (2 for most, 1 for solos)
        setup_time_minutes: Time before competition starts
        transition_seconds: Time between rotations for dancers to swap
    
    Returns:
        Tuple of (total_minutes, rotations, breakdown_string)
    
    Example: 50 dancers, 48 bars, 113bpm, 2 at a time
    - Rotations: 25
    - Time per rotation: 48/113 * 60 = ~25 seconds + transition
    - Total: ~15-20 minutes
    """
    if entry_count == 0:
        return (setup_time_minutes, 0, "No entries")
    
    rotations = math.ceil(entry_count / dancers_per_rotation)
    seconds_per_bar = 60 / tempo_bpm
    dance_time_seconds = bars * seconds_per_bar
    
    # Add transition time between rotations
    total_seconds = rotations * (dance_time_seconds + transition_seconds)
    total_minutes = math.ceil(total_seconds / 60) + setup_time_minutes
    
    # Build breakdown string
    breakdown = (
        f"{entry_count} dancers in {rotations} rotations "
        f"({dancers_per_rotation}/rotation), "
        f"{bars} bars @ {tempo_bpm}bpm = "
        f"~{int(dance_time_seconds)}s per dance"
    )
    
    return (total_minutes, rotations, breakdown)


def estimate_competition_duration(
    competition: Competition,
    entry_count: int
) -> int:
    """
    Estimate duration for a specific competition based on its settings.
    Updates the competition's estimated_duration_minutes field.
    """
    tempo = competition.tempo_bpm or get_default_tempo(competition.dance_type)
    bars = competition.bars or 48
    
    # Championships typically have more setup time and solo dancing
    if competition.scoring_method and competition.scoring_method.value == "championship":
        setup_time = 5
        dancers_per_rotation = 1
    else:
        setup_time = 2
        dancers_per_rotation = 2
    
    duration, _, _ = estimate_duration(
        entry_count=entry_count,
        bars=bars,
        tempo_bpm=tempo,
        dancers_per_rotation=dancers_per_rotation,
        setup_time_minutes=setup_time
    )
    
    return duration


@dataclass
class Conflict:
    """Represents a scheduling conflict."""
    conflict_type: str  # sibling, adjudicator, time_overlap
    severity: str  # warning, error
    message: str
    affected_competition_ids: List[str]
    affected_dancer_ids: List[str]
    affected_stage_ids: List[str]


def detect_sibling_conflicts(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Find cases where siblings (dancers with same parent) are scheduled 
    on different stages at overlapping times.
    
    This helps organizers avoid scheduling conflicts for families.
    """
    conflicts: List[Conflict] = []
    
    # Get all competitions for this feis that have scheduled times
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.scheduled_time.isnot(None))
    ).all()
    
    if not competitions:
        return conflicts
    
    # Build a map of competition -> entries -> parent_id
    comp_to_parents: Dict[UUID, Set[UUID]] = {}
    parent_to_dancers: Dict[UUID, Set[UUID]] = {}
    
    for comp in competitions:
        entries = session.exec(
            select(Entry).where(Entry.competition_id == comp.id)
        ).all()
        
        parent_ids = set()
        for entry in entries:
            dancer = session.get(Dancer, entry.dancer_id)
            if dancer:
                parent_ids.add(dancer.parent_id)
                if dancer.parent_id not in parent_to_dancers:
                    parent_to_dancers[dancer.parent_id] = set()
                parent_to_dancers[dancer.parent_id].add(dancer.id)
        
        comp_to_parents[comp.id] = parent_ids
    
    # Check for overlapping times with same parent
    for i, comp1 in enumerate(competitions):
        for comp2 in competitions[i+1:]:
            # Skip if same stage (no conflict)
            if comp1.stage_id == comp2.stage_id:
                continue
            
            # Check for time overlap
            if not _times_overlap(comp1, comp2):
                continue
            
            # Check for shared parents
            shared_parents = comp_to_parents.get(comp1.id, set()) & comp_to_parents.get(comp2.id, set())
            
            for parent_id in shared_parents:
                # Find the specific dancers involved
                dancers_in_comp1 = set()
                dancers_in_comp2 = set()
                
                entries1 = session.exec(
                    select(Entry).where(Entry.competition_id == comp1.id)
                ).all()
                for e in entries1:
                    dancer = session.get(Dancer, e.dancer_id)
                    if dancer and dancer.parent_id == parent_id:
                        dancers_in_comp1.add(dancer.id)
                
                entries2 = session.exec(
                    select(Entry).where(Entry.competition_id == comp2.id)
                ).all()
                for e in entries2:
                    dancer = session.get(Dancer, e.dancer_id)
                    if dancer and dancer.parent_id == parent_id:
                        dancers_in_comp2.add(dancer.id)
                
                affected_dancers = list(dancers_in_comp1 | dancers_in_comp2)
                
                conflicts.append(Conflict(
                    conflict_type="sibling",
                    severity="warning",
                    message=f"Siblings scheduled at overlapping times on different stages",
                    affected_competition_ids=[str(comp1.id), str(comp2.id)],
                    affected_dancer_ids=[str(d) for d in affected_dancers],
                    affected_stage_ids=[str(comp1.stage_id), str(comp2.stage_id)] if comp1.stage_id and comp2.stage_id else []
                ))
    
    return conflicts


def detect_adjudicator_conflicts(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Find cases where a judge is assigned to a competition containing their own students.
    
    Checks both:
    1. Dancer's school_id matching the adjudicator's user_id
    2. FeisAdjudicator's school_affiliation_id matching dancer's school
    
    This is a blocking conflict that must be resolved.
    """
    conflicts: List[Conflict] = []
    
    # Get all competitions with assigned adjudicators
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.adjudicator_id.isnot(None))
    ).all()
    
    # Build a map of user_id -> school_affiliation_id from FeisAdjudicator roster
    roster = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == feis_id)
    ).all()
    adjudicator_schools: Dict[UUID, Optional[UUID]] = {}
    for adj in roster:
        if adj.user_id:
            adjudicator_schools[adj.user_id] = adj.school_affiliation_id
    
    for comp in competitions:
        adjudicator = session.get(User, comp.adjudicator_id)
        if not adjudicator:
            continue
        
        # Get the adjudicator's school affiliation from the roster
        adj_school_id = adjudicator_schools.get(comp.adjudicator_id)
        
        # Get all entries for this competition
        entries = session.exec(
            select(Entry).where(Entry.competition_id == comp.id)
        ).all()
        
        # Check if any dancer's school_id matches the adjudicator or their school affiliation
        conflicting_dancers = []
        for entry in entries:
            dancer = session.get(Dancer, entry.dancer_id)
            if not dancer:
                continue
            
            # Check direct match (adjudicator IS the teacher)
            if dancer.school_id == comp.adjudicator_id:
                conflicting_dancers.append(dancer.id)
            # Check school affiliation match (adjudicator is affiliated with the school)
            elif adj_school_id and dancer.school_id == adj_school_id:
                conflicting_dancers.append(dancer.id)
        
        if conflicting_dancers:
            conflicts.append(Conflict(
                conflict_type="adjudicator_school",
                severity="error",
                message=f"Judge '{adjudicator.name}' assigned to competition with their own students",
                affected_competition_ids=[str(comp.id)],
                affected_dancer_ids=[str(d) for d in conflicting_dancers],
                affected_stage_ids=[str(comp.stage_id)] if comp.stage_id else []
            ))
    
    return conflicts


def detect_adjudicator_double_booking(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Find cases where the same adjudicator is assigned to overlapping competitions.
    
    This is a blocking conflict - a judge can only be in one place at a time!
    """
    conflicts: List[Conflict] = []
    
    # Get all scheduled competitions with adjudicators
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.adjudicator_id.isnot(None))
        .where(Competition.scheduled_time.isnot(None))
    ).all()
    
    if len(competitions) < 2:
        return conflicts
    
    # Group competitions by adjudicator
    adj_to_comps: Dict[UUID, List[Competition]] = {}
    for comp in competitions:
        if comp.adjudicator_id not in adj_to_comps:
            adj_to_comps[comp.adjudicator_id] = []
        adj_to_comps[comp.adjudicator_id].append(comp)
    
    # Check each adjudicator's competitions for overlaps
    for adj_id, adj_comps in adj_to_comps.items():
        if len(adj_comps) < 2:
            continue
        
        adjudicator = session.get(User, adj_id)
        adj_name = adjudicator.name if adjudicator else "Unknown"
        
        # Sort by scheduled time
        adj_comps.sort(key=lambda c: c.scheduled_time)
        
        for i in range(len(adj_comps) - 1):
            comp1 = adj_comps[i]
            comp2 = adj_comps[i + 1]
            
            if _times_overlap(comp1, comp2):
                conflicts.append(Conflict(
                    conflict_type="adjudicator_double_booked",
                    severity="error",
                    message=f"Judge '{adj_name}' is double-booked for overlapping competitions",
                    affected_competition_ids=[str(comp1.id), str(comp2.id)],
                    affected_dancer_ids=[],
                    affected_stage_ids=[str(comp1.stage_id), str(comp2.stage_id)] if comp1.stage_id and comp2.stage_id else []
                ))
    
    return conflicts


def detect_adjudicator_availability_conflicts(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Find cases where a competition is scheduled outside an adjudicator's availability.
    
    This is a warning - the organizer may need to adjust the schedule or find a different judge.
    """
    conflicts: List[Conflict] = []
    
    # Get all scheduled competitions with adjudicators
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.adjudicator_id.isnot(None))
        .where(Competition.scheduled_time.isnot(None))
    ).all()
    
    # Get the roster to map user_id -> feis_adjudicator_id
    roster = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == feis_id)
    ).all()
    user_to_feis_adj: Dict[UUID, UUID] = {}
    for adj in roster:
        if adj.user_id:
            user_to_feis_adj[adj.user_id] = adj.id
    
    for comp in competitions:
        feis_adj_id = user_to_feis_adj.get(comp.adjudicator_id)
        if not feis_adj_id:
            continue
        
        # Get availability blocks for this adjudicator
        availability = session.exec(
            select(AdjudicatorAvailability)
            .where(AdjudicatorAvailability.feis_adjudicator_id == feis_adj_id)
            .where(AdjudicatorAvailability.availability_type == AvailabilityType.AVAILABLE)
        ).all()
        
        # If no availability set, skip (assume fully available)
        if not availability:
            continue
        
        # Check if competition falls within any availability block
        comp_date = comp.scheduled_time.date()
        comp_time = comp.scheduled_time.time()
        
        # Calculate end time
        # Use 2 minutes as default for short feis events
        duration = comp.estimated_duration_minutes or 2
        comp_end = (comp.scheduled_time + timedelta(minutes=duration)).time()
        
        is_available = False
        for block in availability:
            if block.feis_day == comp_date:
                # Check if competition falls within this block
                if block.start_time <= comp_time and block.end_time >= comp_end:
                    is_available = True
                    break
        
        if not is_available:
            adjudicator = session.get(User, comp.adjudicator_id)
            adj_name = adjudicator.name if adjudicator else "Unknown"
            
            conflicts.append(Conflict(
                conflict_type="adjudicator_unavailable",
                severity="warning",
                message=f"Judge '{adj_name}' may not be available for {comp.name} at the scheduled time",
                affected_competition_ids=[str(comp.id)],
                affected_dancer_ids=[],
                affected_stage_ids=[str(comp.stage_id)] if comp.stage_id else []
            ))
    
    return conflicts


def detect_time_overlap_conflicts(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Find cases where a dancer is registered for competitions that overlap in time.
    """
    conflicts: List[Conflict] = []
    
    # Get all scheduled competitions
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.scheduled_time.isnot(None))
    ).all()
    
    if len(competitions) < 2:
        return conflicts
    
    # Build dancer -> competitions map
    dancer_to_comps: Dict[UUID, List[Competition]] = {}
    
    for comp in competitions:
        entries = session.exec(
            select(Entry).where(Entry.competition_id == comp.id)
        ).all()
        
        for entry in entries:
            if entry.dancer_id not in dancer_to_comps:
                dancer_to_comps[entry.dancer_id] = []
            dancer_to_comps[entry.dancer_id].append(comp)
    
    # Check each dancer's competitions for overlaps
    for dancer_id, dancer_comps in dancer_to_comps.items():
        if len(dancer_comps) < 2:
            continue
        
        # Sort by scheduled time
        dancer_comps.sort(key=lambda c: c.scheduled_time)
        
        for i in range(len(dancer_comps) - 1):
            comp1 = dancer_comps[i]
            comp2 = dancer_comps[i + 1]
            
            if _times_overlap(comp1, comp2):
                dancer = session.get(Dancer, dancer_id)
                dancer_name = dancer.name if dancer else "Unknown"
                
                conflicts.append(Conflict(
                    conflict_type="time_overlap",
                    severity="error",
                    message=f"Dancer '{dancer_name}' registered for overlapping competitions",
                    affected_competition_ids=[str(comp1.id), str(comp2.id)],
                    affected_dancer_ids=[str(dancer_id)],
                    affected_stage_ids=[]
                ))
    
    return conflicts


def detect_all_conflicts(
    feis_id: UUID,
    session: Session
) -> List[Conflict]:
    """
    Run all conflict detection checks for a feis.
    
    Includes:
    - Sibling conflicts (same family on different stages at same time)
    - Adjudicator school conflicts (judge assigned to own students)
    - Adjudicator double-booking (same judge on overlapping competitions)
    - Adjudicator availability conflicts (comp scheduled outside judge's hours)
    - Dancer time overlap conflicts (dancer in multiple overlapping comps)
    """
    conflicts = []
    conflicts.extend(detect_sibling_conflicts(feis_id, session))
    conflicts.extend(detect_adjudicator_conflicts(feis_id, session))
    conflicts.extend(detect_adjudicator_double_booking(feis_id, session))
    conflicts.extend(detect_adjudicator_availability_conflicts(feis_id, session))
    conflicts.extend(detect_time_overlap_conflicts(feis_id, session))
    return conflicts


def _times_overlap(comp1: Competition, comp2: Competition) -> bool:
    """Check if two competitions have overlapping scheduled times."""
    if not comp1.scheduled_time or not comp2.scheduled_time:
        return False
    
    # Get durations (default to 2 minutes for typical short feis events)
    duration1 = comp1.estimated_duration_minutes or 2
    duration2 = comp2.estimated_duration_minutes or 2
    
    end1 = comp1.scheduled_time + timedelta(minutes=duration1)
    end2 = comp2.scheduled_time + timedelta(minutes=duration2)
    
    # Check overlap
    return comp1.scheduled_time < end2 and comp2.scheduled_time < end1


def get_dance_type_from_name(dance_name: str) -> Optional[DanceType]:
    """
    Map a dance name string to a DanceType enum.
    Used by the syllabus generator to set dance_type.
    """
    mapping = {
        # Solo dances
        "reel": DanceType.REEL,
        "light jig": DanceType.LIGHT_JIG,
        "light_jig": DanceType.LIGHT_JIG,
        "slip jig": DanceType.SLIP_JIG,
        "slip_jig": DanceType.SLIP_JIG,
        "single jig": DanceType.SINGLE_JIG,
        "single_jig": DanceType.SINGLE_JIG,
        "treble jig": DanceType.TREBLE_JIG,
        "treble_jig": DanceType.TREBLE_JIG,
        "hornpipe": DanceType.HORNPIPE,
        "traditional set": DanceType.TRADITIONAL_SET,
        "traditional_set": DanceType.TRADITIONAL_SET,
        "set dance": DanceType.TRADITIONAL_SET,
        "contemporary set": DanceType.CONTEMPORARY_SET,
        "contemporary_set": DanceType.CONTEMPORARY_SET,
        "treble reel": DanceType.TREBLE_REEL,
        "treble_reel": DanceType.TREBLE_REEL,
        # Figure/Ceili dances
        "2-hand": DanceType.TWO_HAND,
        "two_hand": DanceType.TWO_HAND,
        "3-hand": DanceType.THREE_HAND,
        "three_hand": DanceType.THREE_HAND,
        "4-hand": DanceType.FOUR_HAND,
        "four_hand": DanceType.FOUR_HAND,
        "6-hand": DanceType.SIX_HAND,
        "six_hand": DanceType.SIX_HAND,
        "8-hand": DanceType.EIGHT_HAND,
        "eight_hand": DanceType.EIGHT_HAND,
    }
    return mapping.get(dance_name.lower())

