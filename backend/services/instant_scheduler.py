"""
Instant Scheduler Service for Open Feis

Provides one-click schedule generation using heuristic algorithms:
- Competition normalization (merge small comps, split large comps)
- Stage plan construction based on judge coverage constraints
- Greedy placement with load balancing
- Automatic lunch break insertion
- Conflict detection integration
"""

import math
from datetime import datetime, timedelta, date, time
from typing import List, Dict, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum
from sqlmodel import Session, select, func

from backend.scoring_engine.models_platform import (
    Competition, Entry, Dancer, Stage, Feis, FeisSettings,
    FeisAdjudicator, StageJudgeCoverage, DanceType, ScoringMethod,
    CompetitionLevel, Gender
)
from backend.services.scheduling import (
    estimate_competition_duration,
    detect_all_conflicts,
    Conflict
)


# ============= Enums and Constants =============

class MergeReason(str, Enum):
    """Reason for merging competitions."""
    MIN_COMP_SIZE = "min_comp_size"
    ORGANIZER_REQUESTED = "organizer_requested"


class SplitReason(str, Enum):
    """Reason for splitting competitions."""
    MAX_COMP_SIZE = "max_comp_size"
    ORGANIZER_REQUESTED = "organizer_requested"


class WarningCode(str, Enum):
    """Warning codes for scheduler output."""
    SMALL_COMP_EXHIBITION_RISK = "small_comp_exhibition_risk"
    INSUFFICIENT_CHAMP_PANEL_CAPACITY = "insufficient_champ_panel_capacity"
    INSUFFICIENT_STAGE_COVERAGE = "insufficient_stage_coverage"
    LUNCH_PLACEMENT_FORCED = "lunch_placement_forced"
    SCHEDULE_EXCEEDS_VENUE_HOURS = "schedule_exceeds_venue_hours"
    NO_JUDGE_COVERAGE = "no_judge_coverage"
    LOAD_IMBALANCE = "load_imbalance"


# Level ordering for scheduling (lower number = scheduled earlier)
LEVEL_ORDER: Dict[CompetitionLevel, int] = {
    CompetitionLevel.FIRST_FEIS: 1,
    CompetitionLevel.BEGINNER_1: 2,
    CompetitionLevel.BEGINNER_2: 3,
    CompetitionLevel.NOVICE: 4,
    CompetitionLevel.PRIZEWINNER: 5,
    CompetitionLevel.PRELIMINARY_CHAMPIONSHIP: 6,
    CompetitionLevel.OPEN_CHAMPIONSHIP: 7,
}


# ============= Data Classes =============

@dataclass
class InstantSchedulerConfig:
    """Configuration options for the instant scheduler."""
    min_comp_size: int = 5
    max_comp_size: int = 25
    lunch_window_start: time = field(default_factory=lambda: time(11, 0))
    lunch_window_end: time = field(default_factory=lambda: time(12, 0))
    lunch_duration_minutes: int = 30
    allow_two_year_merge_up: bool = True
    strict_no_exhibition: bool = False
    feis_start_time: time = field(default_factory=lambda: time(8, 0))
    feis_end_time: time = field(default_factory=lambda: time(17, 0))
    # Minimum duration floors (used when entry count is 0 or very low)
    min_grade_duration_minutes: int = 10
    min_champ_duration_minutes: int = 20
    # Default duration when no entries exist (more realistic for planning)
    default_grade_duration_minutes: int = 15
    default_champ_duration_minutes: int = 30


@dataclass
class CompetitionFamily:
    """Groups competitions by their defining characteristics."""
    dance_type: Optional[DanceType]
    level: CompetitionLevel
    gender: Optional[Gender]
    competitions: List[Competition] = field(default_factory=list)
    
    @property
    def key(self) -> str:
        """Unique key for this family."""
        return f"{self.dance_type}_{self.level}_{self.gender}"


@dataclass
class MergeAction:
    """Records a merge action."""
    source_competition_id: UUID
    target_competition_id: UUID
    source_age_range: str  # e.g., "U8"
    target_age_range: str  # e.g., "U9"
    dancers_moved: int
    reason: MergeReason
    rationale: str


@dataclass
class SplitAction:
    """Records a split action."""
    original_competition_id: UUID
    new_competition_id: UUID
    original_size: int
    group_a_size: int
    group_b_size: int
    reason: SplitReason
    assignment_method: str  # "random" or "birth_month"


@dataclass
class SchedulerWarning:
    """A warning generated during scheduling."""
    code: WarningCode
    message: str
    competition_ids: List[UUID] = field(default_factory=list)
    stage_ids: List[UUID] = field(default_factory=list)
    severity: str = "warning"  # "warning" or "critical"


@dataclass
class NormalizationResult:
    """Result of competition normalization."""
    merges: List[MergeAction] = field(default_factory=list)
    splits: List[SplitAction] = field(default_factory=list)
    warnings: List[SchedulerWarning] = field(default_factory=list)
    final_competition_count: int = 0


@dataclass
class StagePlan:
    """Plan for stages based on judge coverage."""
    stage_id: UUID
    stage_name: str
    coverage_blocks: List[StageJudgeCoverage] = field(default_factory=list)
    is_championship_capable: bool = False  # Has 3+ judges in a block
    track: str = "grades"  # "grades" or "championships"


@dataclass
class SchedulePlacement:
    """A scheduled competition placement."""
    competition_id: UUID
    stage_id: UUID
    scheduled_start: datetime
    scheduled_end: datetime
    duration_minutes: int
    source: str = "INSTANT_SCHEDULER"


@dataclass
class LunchHold:
    """A lunch break hold on a stage."""
    stage_id: UUID
    start_time: datetime
    end_time: datetime
    duration_minutes: int


@dataclass
class InstantSchedulerResult:
    """Full result from the instant scheduler."""
    normalized: NormalizationResult
    stage_plan: List[StagePlan]
    placements: List[SchedulePlacement]
    lunch_holds: List[LunchHold]
    warnings: List[SchedulerWarning]
    conflicts: List[Conflict]
    
    # Summary stats
    total_competitions_scheduled: int = 0
    total_competitions_unscheduled: int = 0
    grade_competitions: int = 0
    championship_competitions: int = 0


# ============= Competition Normalization =============

def get_age_group_key(min_age: int, max_age: int) -> str:
    """Convert age range to display key like 'U8' or '8-9'."""
    if min_age == max_age:
        return f"U{max_age}" if max_age < 18 else f"{min_age}+"
    return f"{min_age}-{max_age}"


def get_entry_count(competition: Competition, session: Session) -> int:
    """Get the number of entries for a competition."""
    return session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition.id)
    ).one()


def group_competitions_by_family(
    competitions: List[Competition],
    session: Session
) -> Dict[str, CompetitionFamily]:
    """
    Group competitions by dance type, level, and gender.
    Returns a dict keyed by family identifier.
    """
    families: Dict[str, CompetitionFamily] = {}
    
    for comp in competitions:
        family_key = f"{comp.dance_type}_{comp.level}_{comp.gender}"
        
        if family_key not in families:
            families[family_key] = CompetitionFamily(
                dance_type=comp.dance_type,
                level=comp.level,
                gender=comp.gender
            )
        
        families[family_key].competitions.append(comp)
    
    return families


def find_merge_target(
    source_comp: Competition,
    family_comps: List[Competition],
    config: InstantSchedulerConfig,
    session: Session
) -> Optional[Competition]:
    """
    Find a valid merge target for a small competition.
    
    Rules:
    - Only merge UP (younger into older)
    - Within same family (dance type, level, gender)
    - 1-year merge first, then 2-year if allowed
    """
    source_max_age = source_comp.max_age
    
    # Sort by age to find next older competition
    age_sorted = sorted(
        [c for c in family_comps if c.id != source_comp.id],
        key=lambda c: c.min_age
    )
    
    # Look for 1-year merge up
    for target in age_sorted:
        if target.min_age == source_max_age + 1 or target.min_age == source_max_age:
            # This is the next age bracket up
            return target
    
    # Look for 2-year merge up if allowed
    if config.allow_two_year_merge_up:
        for target in age_sorted:
            if target.min_age <= source_max_age + 2:
                return target
    
    return None


def normalize_competitions(
    feis_id: UUID,
    session: Session,
    config: InstantSchedulerConfig
) -> NormalizationResult:
    """
    Normalize competitions by merging small ones and splitting large ones.
    
    Merge rules:
    - Only merge UP (younger dancers compete with older)
    - Never move older dancers down
    - Try 1-year merge first, then 2-year if allowed
    
    Split rules:
    - Split competitions exceeding max_comp_size into A/B groups
    - Random assignment by default
    """
    result = NormalizationResult()
    
    # Get all competitions for this feis (excluding championships for merge logic)
    all_competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
    ).all()
    
    # Separate grades and championships
    grade_comps = [c for c in all_competitions if c.scoring_method == ScoringMethod.SOLO]
    champ_comps = [c for c in all_competitions if c.scoring_method == ScoringMethod.CHAMPIONSHIP]
    
    # Group grades by family (dance type, level, gender)
    families = group_competitions_by_family(grade_comps, session)
    
    # Track which competitions have been merged into others
    merged_into: Dict[UUID, UUID] = {}
    
    # Process each family for merges
    for family_key, family in families.items():
        # Sort by min_age (youngest first)
        family.competitions.sort(key=lambda c: c.min_age)
        
        for comp in family.competitions:
            if comp.id in merged_into:
                continue
            
            entry_count = get_entry_count(comp, session)
            
            if entry_count < config.min_comp_size:
                # Try to find a merge target
                target = find_merge_target(comp, family.competitions, config, session)
                
                if target and target.id not in merged_into:
                    # Record the merge
                    merge_action = MergeAction(
                        source_competition_id=comp.id,
                        target_competition_id=target.id,
                        source_age_range=get_age_group_key(comp.min_age, comp.max_age),
                        target_age_range=get_age_group_key(target.min_age, target.max_age),
                        dancers_moved=entry_count,
                        reason=MergeReason.MIN_COMP_SIZE,
                        rationale=f"Competition size ({entry_count}) below minimum ({config.min_comp_size})"
                    )
                    result.merges.append(merge_action)
                    merged_into[comp.id] = target.id
                else:
                    # No valid merge target - warn about exhibition risk
                    result.warnings.append(SchedulerWarning(
                        code=WarningCode.SMALL_COMP_EXHIBITION_RISK,
                        message=f"Competition '{comp.name}' has only {entry_count} entries and cannot be merged up",
                        competition_ids=[comp.id],
                        severity="warning"
                    ))
    
    # Process for splits (both grades and championships)
    for comp in all_competitions:
        if comp.id in merged_into:
            continue
        
        entry_count = get_entry_count(comp, session)
        
        if entry_count > config.max_comp_size:
            # Need to split
            # Note: In a real implementation, we'd create a new competition record
            # For now, we just record the intent
            group_a_size = entry_count // 2
            group_b_size = entry_count - group_a_size
            
            result.splits.append(SplitAction(
                original_competition_id=comp.id,
                new_competition_id=comp.id,  # Placeholder - would be new UUID
                original_size=entry_count,
                group_a_size=group_a_size,
                group_b_size=group_b_size,
                reason=SplitReason.MAX_COMP_SIZE,
                assignment_method="random"
            ))
    
    result.final_competition_count = len(all_competitions) - len(merged_into) + len(result.splits)
    
    return result


# ============= Stage Plan Construction =============

def build_stage_plan(
    feis_id: UUID,
    feis_date: date,
    session: Session,
    config: InstantSchedulerConfig
) -> Tuple[List[StagePlan], List[SchedulerWarning]]:
    """
    Build a stage plan based on judge coverage constraints.
    
    A stage block is schedulable only if an adjudicator (or panel) is assigned
    to that stage for that time window.
    """
    warnings: List[SchedulerWarning] = []
    plans: List[StagePlan] = []
    
    # Get all stages for this feis
    stages = session.exec(
        select(Stage).where(Stage.feis_id == feis_id)
    ).all()
    
    if not stages:
        warnings.append(SchedulerWarning(
            code=WarningCode.NO_JUDGE_COVERAGE,
            message="No stages defined for this feis",
            severity="critical"
        ))
        return plans, warnings
    
    # Get all coverage blocks for the feis date
    for stage in stages:
        coverage = session.exec(
            select(StageJudgeCoverage)
            .where(StageJudgeCoverage.stage_id == stage.id)
            .where(StageJudgeCoverage.feis_day == feis_date)
        ).all()
        
        if not coverage:
            warnings.append(SchedulerWarning(
                code=WarningCode.NO_JUDGE_COVERAGE,
                message=f"Stage '{stage.name}' has no judge coverage assigned for {feis_date}",
                stage_ids=[stage.id],
                severity="warning"
            ))
        
        # Check if this stage can handle championships (3+ judges in any block)
        is_champ_capable = False
        for block in coverage:
            # Count judges in overlapping time blocks for this stage
            # For now, assume single judge per coverage block unless we have panel info
            # In a full implementation, we'd check for multiple coverage blocks at same time
            pass
        
        plans.append(StagePlan(
            stage_id=stage.id,
            stage_name=stage.name,
            coverage_blocks=list(coverage),
            is_championship_capable=is_champ_capable,
            track="grades"  # Default to grades; championships get assigned based on panel requirements
        ))
    
    return plans, warnings


def get_available_time_slots(
    stage_plan: StagePlan,
    feis_date: date,
    existing_placements: List[SchedulePlacement],
    lunch_holds: List[LunchHold],
    config: InstantSchedulerConfig
) -> List[Tuple[datetime, datetime]]:
    """
    Get available time slots for a stage based on coverage and existing placements.
    """
    available_slots: List[Tuple[datetime, datetime]] = []
    
    if not stage_plan.coverage_blocks:
        # No coverage - use full feis day
        start_dt = datetime.combine(feis_date, config.feis_start_time)
        end_dt = datetime.combine(feis_date, config.feis_end_time)
        available_slots.append((start_dt, end_dt))
    else:
        # Use coverage blocks as available times
        for block in stage_plan.coverage_blocks:
            start_dt = datetime.combine(block.feis_day, block.start_time)
            end_dt = datetime.combine(block.feis_day, block.end_time)
            available_slots.append((start_dt, end_dt))
    
    # Remove times already taken by placements
    stage_placements = [p for p in existing_placements if p.stage_id == stage_plan.stage_id]
    stage_lunches = [l for l in lunch_holds if l.stage_id == stage_plan.stage_id]
    
    # Simple approach: find gaps in existing placements
    occupied_times: List[Tuple[datetime, datetime]] = []
    for p in stage_placements:
        occupied_times.append((p.scheduled_start, p.scheduled_end))
    for l in stage_lunches:
        occupied_times.append((l.start_time, l.end_time))
    
    # Sort occupied times
    occupied_times.sort(key=lambda x: x[0])
    
    # Calculate free slots
    free_slots: List[Tuple[datetime, datetime]] = []
    
    for slot_start, slot_end in available_slots:
        current_start = slot_start
        
        for occ_start, occ_end in occupied_times:
            if occ_start <= current_start < occ_end:
                # Current start is inside an occupied block
                current_start = occ_end
            elif current_start < occ_start < slot_end:
                # There's a gap before this occupied block
                if occ_start > current_start:
                    free_slots.append((current_start, occ_start))
                current_start = occ_end
        
        # Add remaining time after last occupied block
        if current_start < slot_end:
            free_slots.append((current_start, slot_end))
    
    return free_slots


# ============= Placement Heuristics =============

def get_competition_priority(comp: Competition, entry_count: int) -> Tuple[int, int, int]:
    """
    Calculate priority for scheduling a competition.
    Lower values = scheduled earlier.
    
    Returns (level_priority, age_priority, size_priority)
    """
    level_priority = LEVEL_ORDER.get(comp.level, 99)
    age_priority = comp.min_age  # Younger ages earlier
    size_priority = -entry_count  # Larger competitions slightly later (negative = earlier in sort)
    
    return (level_priority, age_priority, size_priority)


def place_competitions_greedy(
    feis_id: UUID,
    feis_date: date,
    stage_plans: List[StagePlan],
    session: Session,
    config: InstantSchedulerConfig,
    normalization: NormalizationResult
) -> Tuple[List[SchedulePlacement], List[LunchHold], List[SchedulerWarning]]:
    """
    Place competitions on stages using greedy bin-packing algorithm.
    
    Algorithm:
    1. Separate grades and championships
    2. Sort grades by level (lower first), then age (younger first)
    3. For each competition, find the first available slot
    4. Insert lunch breaks in the lunch window
    """
    placements: List[SchedulePlacement] = []
    lunch_holds: List[LunchHold] = []
    warnings: List[SchedulerWarning] = []
    
    # Get competitions that weren't merged away
    merged_comp_ids = {m.source_competition_id for m in normalization.merges}
    
    all_comps = session.exec(
        select(Competition).where(Competition.feis_id == feis_id)
    ).all()
    
    schedulable_comps = [c for c in all_comps if c.id not in merged_comp_ids]
    
    # Separate by type
    grade_comps = [c for c in schedulable_comps if c.scoring_method == ScoringMethod.SOLO]
    champ_comps = [c for c in schedulable_comps if c.scoring_method == ScoringMethod.CHAMPIONSHIP]
    
    # Get entry counts
    comp_entry_counts: Dict[UUID, int] = {}
    for comp in schedulable_comps:
        # Account for merged entries
        entry_count = get_entry_count(comp, session)
        # Add entries from competitions merged into this one
        for merge in normalization.merges:
            if merge.target_competition_id == comp.id:
                entry_count += merge.dancers_moved
        comp_entry_counts[comp.id] = entry_count
    
    # Sort grades by priority
    grade_comps.sort(key=lambda c: get_competition_priority(c, comp_entry_counts.get(c.id, 0)))
    
    # Sort championships similarly
    champ_comps.sort(key=lambda c: get_competition_priority(c, comp_entry_counts.get(c.id, 0)))
    
    # Identify grade stages (those without championship capability or dedicated to grades)
    grade_stages = [p for p in stage_plans]  # For now, all stages handle grades
    
    # Track current time position per stage
    stage_current_time: Dict[UUID, datetime] = {}
    for plan in stage_plans:
        stage_current_time[plan.stage_id] = datetime.combine(feis_date, config.feis_start_time)
    
    # Track if lunch has been scheduled per stage
    stage_lunch_scheduled: Dict[UUID, bool] = {p.stage_id: False for p in stage_plans}
    
    # Place grade competitions
    for comp in grade_comps:
        entry_count = comp_entry_counts.get(comp.id, 0)
        
        # Use existing duration if set, otherwise estimate
        if comp.estimated_duration_minutes and comp.estimated_duration_minutes > 0:
            duration = comp.estimated_duration_minutes
        elif entry_count == 0:
            # No entries yet - use default planning duration
            duration = config.default_grade_duration_minutes
        else:
            duration = estimate_competition_duration(comp, entry_count)
        
        # Ensure minimum duration floor
        duration = max(duration, config.min_grade_duration_minutes)
        
        # Find best stage (one with earliest available time)
        best_stage: Optional[StagePlan] = None
        best_start_time: Optional[datetime] = None
        
        for plan in grade_stages:
            current_time = stage_current_time[plan.stage_id]
            
            # Check if we need to insert lunch before this competition
            if not stage_lunch_scheduled[plan.stage_id]:
                lunch_start = datetime.combine(feis_date, config.lunch_window_start)
                lunch_end = datetime.combine(feis_date, config.lunch_window_end)
                
                if current_time >= lunch_start and current_time < lunch_end:
                    # Insert lunch now
                    lunch_hold = LunchHold(
                        stage_id=plan.stage_id,
                        start_time=current_time,
                        end_time=current_time + timedelta(minutes=config.lunch_duration_minutes),
                        duration_minutes=config.lunch_duration_minutes
                    )
                    lunch_holds.append(lunch_hold)
                    stage_lunch_scheduled[plan.stage_id] = True
                    current_time = lunch_hold.end_time
                    stage_current_time[plan.stage_id] = current_time
            
            if best_start_time is None or current_time < best_start_time:
                best_start_time = current_time
                best_stage = plan
        
        if best_stage and best_start_time:
            # Place the competition
            placement = SchedulePlacement(
                competition_id=comp.id,
                stage_id=best_stage.stage_id,
                scheduled_start=best_start_time,
                scheduled_end=best_start_time + timedelta(minutes=duration),
                duration_minutes=duration,
                source="INSTANT_SCHEDULER"
            )
            placements.append(placement)
            
            # Update stage current time
            stage_current_time[best_stage.stage_id] = placement.scheduled_end
    
    # Place championship competitions (similar logic but check for panel capability)
    for comp in champ_comps:
        entry_count = comp_entry_counts.get(comp.id, 0)
        
        # Use existing duration if set, otherwise estimate
        if comp.estimated_duration_minutes and comp.estimated_duration_minutes > 0:
            duration = comp.estimated_duration_minutes
        elif entry_count == 0:
            # No entries yet - use default planning duration
            duration = config.default_champ_duration_minutes
        else:
            duration = estimate_competition_duration(comp, entry_count)
        
        # Ensure minimum duration floor
        duration = max(duration, config.min_champ_duration_minutes)
        
        # Championships need stages with adequate panel coverage
        # For simplicity, use any stage for now
        best_stage: Optional[StagePlan] = None
        best_start_time: Optional[datetime] = None
        
        for plan in stage_plans:
            current_time = stage_current_time[plan.stage_id]
            
            if best_start_time is None or current_time < best_start_time:
                best_start_time = current_time
                best_stage = plan
        
        if best_stage and best_start_time:
            placement = SchedulePlacement(
                competition_id=comp.id,
                stage_id=best_stage.stage_id,
                scheduled_start=best_start_time,
                scheduled_end=best_start_time + timedelta(minutes=duration),
                duration_minutes=duration,
                source="INSTANT_SCHEDULER"
            )
            placements.append(placement)
            stage_current_time[best_stage.stage_id] = placement.scheduled_end
        else:
            warnings.append(SchedulerWarning(
                code=WarningCode.INSUFFICIENT_CHAMP_PANEL_CAPACITY,
                message=f"Could not schedule championship '{comp.name}' - no suitable stage found",
                competition_ids=[comp.id],
                severity="critical"
            ))
    
    # Check for schedule exceeding venue hours
    for stage_id, end_time in stage_current_time.items():
        venue_end = datetime.combine(feis_date, config.feis_end_time)
        if end_time > venue_end:
            stage_name = next((p.stage_name for p in stage_plans if p.stage_id == stage_id), "Unknown")
            warnings.append(SchedulerWarning(
                code=WarningCode.SCHEDULE_EXCEEDS_VENUE_HOURS,
                message=f"Stage '{stage_name}' schedule extends past venue hours ({end_time.strftime('%H:%M')} > {config.feis_end_time.strftime('%H:%M')})",
                stage_ids=[stage_id],
                severity="warning"
            ))
    
    # Check for load imbalance
    end_times = list(stage_current_time.values())
    if len(end_times) >= 2:
        earliest_end = min(end_times)
        latest_end = max(end_times)
        diff_minutes = (latest_end - earliest_end).total_seconds() / 60
        
        if diff_minutes > 60:
            warnings.append(SchedulerWarning(
                code=WarningCode.LOAD_IMBALANCE,
                message=f"Stages are imbalanced by {int(diff_minutes)} minutes. Consider moving competitions to balance load.",
                severity="warning"
            ))
    
    return placements, lunch_holds, warnings


# ============= Main Entry Point =============

def run_instant_scheduler(
    feis_id: UUID,
    session: Session,
    config: Optional[InstantSchedulerConfig] = None
) -> InstantSchedulerResult:
    """
    Run the instant scheduler for a feis.
    
    Steps:
    1. Normalize competitions (merge/split)
    2. Build stage plan from judge coverage
    3. Place competitions using greedy algorithm
    4. Insert lunch breaks
    5. Run conflict detection
    6. Return result with warnings
    """
    if config is None:
        config = InstantSchedulerConfig()
    
    # Load feis to get date
    feis = session.get(Feis, feis_id)
    if not feis:
        raise ValueError(f"Feis {feis_id} not found")
    
    feis_date = feis.date
    
    # Load feis settings for scheduling defaults
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis_id)
    ).first()
    
    if settings:
        if settings.lunch_duration_minutes:
            config.lunch_duration_minutes = settings.lunch_duration_minutes
        if settings.lunch_window_start:
            config.lunch_window_start = settings.lunch_window_start
        if settings.lunch_window_end:
            config.lunch_window_end = settings.lunch_window_end
    
    all_warnings: List[SchedulerWarning] = []
    
    # Step 1: Normalize competitions
    normalization = normalize_competitions(feis_id, session, config)
    all_warnings.extend(normalization.warnings)
    
    # Step 2: Build stage plan
    stage_plans, stage_warnings = build_stage_plan(feis_id, feis_date, session, config)
    all_warnings.extend(stage_warnings)
    
    # Step 3 & 4: Place competitions and lunch breaks
    placements, lunch_holds, placement_warnings = place_competitions_greedy(
        feis_id, feis_date, stage_plans, session, config, normalization
    )
    all_warnings.extend(placement_warnings)
    
    # Apply placements to database
    for placement in placements:
        comp = session.get(Competition, placement.competition_id)
        if comp:
            comp.stage_id = placement.stage_id
            comp.scheduled_time = placement.scheduled_start
            comp.estimated_duration_minutes = placement.duration_minutes
            session.add(comp)
    
    session.commit()
    
    # Step 5: Run conflict detection
    conflicts = detect_all_conflicts(feis_id, session)
    
    # Build result
    grade_count = len([p for p in placements if session.get(Competition, p.competition_id).scoring_method == ScoringMethod.SOLO])
    champ_count = len([p for p in placements if session.get(Competition, p.competition_id).scoring_method == ScoringMethod.CHAMPIONSHIP])
    
    result = InstantSchedulerResult(
        normalized=normalization,
        stage_plan=stage_plans,
        placements=placements,
        lunch_holds=lunch_holds,
        warnings=all_warnings,
        conflicts=conflicts,
        total_competitions_scheduled=len(placements),
        total_competitions_unscheduled=normalization.final_competition_count - len(placements),
        grade_competitions=grade_count,
        championship_competitions=champ_count
    )
    
    return result


def clear_schedule(feis_id: UUID, session: Session) -> int:
    """
    Clear all scheduling data for a feis (stage assignments and times).
    Returns the number of competitions cleared.
    """
    competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis_id)
        .where(Competition.scheduled_time.isnot(None))
    ).all()
    
    count = 0
    for comp in competitions:
        comp.stage_id = None
        comp.scheduled_time = None
        session.add(comp)
        count += 1
    
    session.commit()
    return count
