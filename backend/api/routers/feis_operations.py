"""
Feis Operations Router - Scheduling, entries, check-in, number cards, adjudicator roster.

Routes:
- GET /judge/feiseanna - Judge's feiseanna list
- GET/POST /feis/{feis_id}/schedule/* - Scheduling operations
- GET /feis/{feis_id}/entries - Entry list
- POST /feis/{feis_id}/assign-numbers - Bulk number assignment
- GET /feis/{feis_id}/number-cards - PDF generation
- GET /feis/{feis_id}/flags - Flagged entries
- GET /feis/{feis_id}/capacity - Capacity status
- GET /feis/{feis_id}/waitlist - Waitlist status
- GET /feis/{feis_id}/checkin-summary - Check-in summary
- GET /feis/{feis_id}/refund-* - Refund policy and stats
- GET/POST /feis/{feis_id}/adjudicators - Adjudicator roster
- GET/PUT /feis/{feis_id}/scheduling-defaults - Scheduling configuration
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import (
    get_current_user, require_organizer_or_admin, require_adjudicator
)
from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Dancer, Entry, RoleType,
    Stage, FeisSettings, StageJudgeCoverage, EntryFlag,
    FeisAdjudicator, AdjudicatorStatus, WaitlistEntry, WaitlistStatus
)
from backend.api.schemas import (
    FeisResponse, CompetitionResponse, EntryResponse,
    StageResponse, StageJudgeCoverageResponse,
    BulkNumberAssignment, BulkNumberAssignmentResponse,
    ScheduleConflict, ConflictCheckResponse, ScheduledCompetition, SchedulerViewResponse,
    BulkScheduleRequest, BulkScheduleResponse,
    InstantSchedulerRequest, InstantSchedulerResponse,
    MergeActionResponse, SplitActionResponse, SchedulerWarningResponse,
    NormalizationResponse, StagePlanResponse, PlacementResponse, LunchHoldResponse,
    AdjudicatorCreate, AdjudicatorResponse, AdjudicatorListResponse,
    AdjudicatorCapacityResponse,
    SchedulingDefaultsUpdate, SchedulingDefaultsResponse,
    FlaggedEntriesResponse, EntryFlagResponse,
    FeisCapacityStatus, WaitlistStatusResponse, WaitlistEntryResponse
)
from backend.services.scheduling import (
    estimate_competition_duration, detect_all_conflicts
)
from backend.services.number_cards import NumberCardData, generate_number_cards_pdf
from backend.services.waitlist import get_feis_capacity, get_user_waitlist_entries
from backend.services.checkin import get_feis_check_in_summary
from backend.services.refund import get_refund_policy, get_feis_refund_stats

router = APIRouter()


# ============= Helper Functions =============

def calculate_competition_age(dob: date, feis_date: date) -> int:
    """
    Calculate competition age using the January 1st rule.
    A dancer's competition age is their age as of January 1st of the feis year.
    """
    jan_1 = date(feis_date.year, 1, 1)
    age = jan_1.year - dob.year
    if (jan_1.month, jan_1.day) < (dob.month, dob.day):
        age -= 1
    return age


def get_school_name(session: Session, school_id: Optional[UUID]) -> Optional[str]:
    """Look up school name from school_id (which references a User/Teacher)."""
    if not school_id:
        return None
    teacher = session.get(User, school_id)
    return teacher.name if teacher else None


# ============= Judge Feiseanna =============

@router.get("/judge/feiseanna", response_model=List[FeisResponse])
async def get_judge_feiseanna(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    Get all feiseanna the current user is authorized to judge.
    Includes feiseanna where they are an adjudicator, organizer, or if they are super_admin.
    """
    if current_user.role == RoleType.SUPER_ADMIN:
        feiseanna = session.exec(select(Feis)).all()
        return [FeisResponse.model_validate(f) for f in feiseanna]
    
    organizer_feiseanna = session.exec(
        select(Feis).where(Feis.organizer_id == current_user.id)
    ).all()
    
    adjudicator_feiseanna = session.exec(
        select(Feis)
        .join(FeisAdjudicator)
        .where(FeisAdjudicator.user_id == current_user.id)
    ).all()
    
    all_feiseanna = {f.id: f for f in organizer_feiseanna + adjudicator_feiseanna}
    return [FeisResponse.model_validate(f) for f in all_feiseanna.values()]


# ============= Scheduling Endpoints =============

@router.get("/feis/{feis_id}/judge-schedule", response_model=List[StageJudgeCoverageResponse])
async def get_feis_judge_schedule(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get all judge coverage blocks for a feis (cross-stage view for judges)."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    stages = session.exec(select(Stage).where(Stage.feis_id == feis.id)).all()
    stage_ids = [s.id for s in stages]
    stage_map = {s.id: s for s in stages}
    
    if not stage_ids:
        return []
    
    coverage_blocks = session.exec(
        select(StageJudgeCoverage)
        .where(StageJudgeCoverage.stage_id.in_(stage_ids))
        .order_by(StageJudgeCoverage.feis_day, StageJudgeCoverage.start_time)
    ).all()
    
    result = []
    for cov in coverage_blocks:
        adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
        stage = stage_map.get(cov.stage_id)
        result.append(StageJudgeCoverageResponse(
            id=str(cov.id),
            stage_id=str(cov.stage_id),
            stage_name=stage.name if stage else "Unknown",
            feis_adjudicator_id=str(cov.feis_adjudicator_id),
            adjudicator_name=adj.name if adj else "Unknown",
            feis_day=cov.feis_day.isoformat(),
            start_time=cov.start_time.strftime("%H:%M"),
            end_time=cov.end_time.strftime("%H:%M"),
            note=cov.note
        ))
    
    return result


@router.get("/feis/{feis_id}/scheduler", response_model=SchedulerViewResponse)
async def get_scheduler_view(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get all data needed for the scheduler view."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    stages = session.exec(
        select(Stage)
        .where(Stage.feis_id == feis.id)
        .order_by(Stage.sequence)
    ).all()
    
    stage_responses = []
    for stage in stages:
        comp_count = session.exec(
            select(func.count(Competition.id)).where(Competition.stage_id == stage.id)
        ).one()
        
        coverage_blocks = session.exec(
            select(StageJudgeCoverage)
            .where(StageJudgeCoverage.stage_id == stage.id)
            .order_by(StageJudgeCoverage.feis_day, StageJudgeCoverage.start_time)
        ).all()
        
        coverage_responses = []
        for cov in coverage_blocks:
            adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
            coverage_responses.append(StageJudgeCoverageResponse(
                id=str(cov.id),
                stage_id=str(cov.stage_id),
                stage_name=stage.name,
                feis_adjudicator_id=str(cov.feis_adjudicator_id),
                adjudicator_name=adj.name if adj else "Unknown",
                feis_day=cov.feis_day.isoformat(),
                start_time=cov.start_time.strftime("%H:%M"),
                end_time=cov.end_time.strftime("%H:%M"),
                note=cov.note
            ))
        
        stage_responses.append(StageResponse(
            id=str(stage.id),
            feis_id=str(stage.feis_id),
            name=stage.name,
            color=stage.color,
            sequence=stage.sequence,
            competition_count=comp_count,
            judge_coverage=coverage_responses
        ))
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    conflicts = detect_all_conflicts(feis.id, session)
    conflict_comp_ids = set()
    for conflict in conflicts:
        conflict_comp_ids.update(conflict.affected_competition_ids)
    
    comp_responses = []
    for comp in competitions:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        stage_name = None
        if comp.stage_id:
            stage = session.get(Stage, comp.stage_id)
            stage_name = stage.name if stage else None
        
        estimated_duration = comp.estimated_duration_minutes
        if estimated_duration is None:
            estimated_duration = estimate_competition_duration(comp, entry_count)
        
        comp_responses.append(ScheduledCompetition(
            id=str(comp.id),
            name=comp.name,
            stage_id=str(comp.stage_id) if comp.stage_id else None,
            stage_name=stage_name,
            scheduled_time=comp.scheduled_time,
            estimated_duration_minutes=estimated_duration,
            entry_count=entry_count,
            level=comp.level,
            dance_type=comp.dance_type,
            has_conflicts=str(comp.id) in conflict_comp_ids,
            adjudicator_id=str(comp.adjudicator_id) if comp.adjudicator_id else None
        ))
    
    conflict_responses = [
        ScheduleConflict(
            conflict_type=c.conflict_type,
            severity=c.severity,
            message=c.message,
            affected_competition_ids=c.affected_competition_ids,
            affected_dancer_ids=c.affected_dancer_ids,
            affected_stage_ids=c.affected_stage_ids
        )
        for c in conflicts
    ]
    
    return SchedulerViewResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        feis_date=feis.date,
        stages=stage_responses,
        competitions=comp_responses,
        conflicts=conflict_responses
    )


@router.post("/feis/{feis_id}/schedule/bulk", response_model=BulkScheduleResponse)
async def bulk_schedule_competitions(
    feis_id: str,
    request: BulkScheduleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Schedule multiple competitions at once with auto-judge assignment."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only schedule competitions for your own feis")
    
    scheduled_count = 0
    for schedule in request.schedules:
        comp = session.get(Competition, UUID(schedule.competition_id))
        if comp and comp.feis_id == feis.id:
            comp.stage_id = UUID(schedule.stage_id) if schedule.stage_id else None
            comp.scheduled_time = schedule.scheduled_time
            
            # Auto-assign judge based on stage coverage
            if comp.stage_id and comp.scheduled_time:
                comp_start = comp.scheduled_time
                comp_date = comp_start.date()
                comp_time = comp_start.time()
                
                # Find judges with coverage on this stage during this time
                coverages = session.exec(
                    select(StageJudgeCoverage)
                    .where(StageJudgeCoverage.stage_id == comp.stage_id)
                    .where(StageJudgeCoverage.feis_day == comp_date)
                ).all()
                
                # Find a coverage block that includes this time
                for cov in coverages:
                    if cov.start_time <= comp_time <= cov.end_time:
                        # Get the FeisAdjudicator to find their user_id
                        feis_adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
                        if feis_adj and feis_adj.user_id:
                            comp.adjudicator_id = feis_adj.user_id
                            break
            
            session.add(comp)
            scheduled_count += 1
    
    session.commit()
    
    conflicts = detect_all_conflicts(feis.id, session)
    conflict_responses = [
        ScheduleConflict(
            conflict_type=c.conflict_type,
            severity=c.severity,
            message=c.message,
            affected_competition_ids=c.affected_competition_ids,
            affected_dancer_ids=c.affected_dancer_ids,
            affected_stage_ids=c.affected_stage_ids
        )
        for c in conflicts
    ]
    
    return BulkScheduleResponse(
        scheduled_count=scheduled_count,
        conflicts=conflict_responses,
        message=f"Scheduled {scheduled_count} competitions. {len(conflicts)} conflicts detected."
    )


@router.post("/feis/{feis_id}/schedule/instant", response_model=InstantSchedulerResponse)
async def instant_schedule(
    feis_id: str,
    request: InstantSchedulerRequest = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Generate an instant schedule for a feis using algorithmic heuristics."""
    from backend.services.instant_scheduler import (
        run_instant_scheduler, clear_schedule, InstantSchedulerConfig
    )
    from datetime import time as dt_time
    
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only schedule competitions for your own feis")
    
    if request is None:
        request = InstantSchedulerRequest()
    
    def parse_time(time_str: str) -> dt_time:
        parts = time_str.split(":")
        return dt_time(int(parts[0]), int(parts[1]))
    
    config = InstantSchedulerConfig(
        min_comp_size=request.min_comp_size,
        max_comp_size=request.max_comp_size,
        lunch_window_start=parse_time(request.lunch_window_start) if request.lunch_window_start else dt_time(11, 0),
        lunch_window_end=parse_time(request.lunch_window_end) if request.lunch_window_end else dt_time(12, 0),
        lunch_duration_minutes=request.lunch_duration_minutes,
        allow_two_year_merge_up=request.allow_two_year_merge_up,
        strict_no_exhibition=request.strict_no_exhibition,
        feis_start_time=parse_time(request.feis_start_time) if request.feis_start_time else dt_time(8, 0),
        feis_end_time=parse_time(request.feis_end_time) if request.feis_end_time else dt_time(17, 0),
        default_grade_duration_minutes=request.default_grade_duration_minutes,
        default_champ_duration_minutes=request.default_champ_duration_minutes
    )
    
    if request.clear_existing:
        clear_schedule(feis.id, session)
    
    try:
        result = run_instant_scheduler(feis.id, session, config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduler error: {str(e)}")
    
    stages = session.exec(select(Stage).where(Stage.feis_id == feis.id)).all()
    stage_names = {s.id: s.name for s in stages}
    
    competitions = session.exec(select(Competition).where(Competition.feis_id == feis.id)).all()
    comp_names = {c.id: c.name for c in competitions}
    comp_entry_counts = {}
    for c in competitions:
        count = session.exec(select(func.count(Entry.id)).where(Entry.competition_id == c.id)).one()
        comp_entry_counts[c.id] = count
    
    merge_responses = [
        MergeActionResponse(
            source_competition_id=str(m.source_competition_id),
            target_competition_id=str(m.target_competition_id),
            source_competition_name=comp_names.get(m.source_competition_id, "Unknown"),
            target_competition_name=comp_names.get(m.target_competition_id, "Unknown"),
            source_age_range=m.source_age_range,
            target_age_range=m.target_age_range,
            dancers_moved=m.dancers_moved,
            reason=m.reason.value,
            rationale=m.rationale
        )
        for m in result.normalized.merges
    ]
    
    split_responses = [
        SplitActionResponse(
            original_competition_id=str(s.original_competition_id),
            new_competition_id=str(s.new_competition_id),
            competition_name=comp_names.get(s.original_competition_id, "Unknown"),
            original_size=s.original_size,
            group_a_size=s.group_a_size,
            group_b_size=s.group_b_size,
            reason=s.reason.value,
            assignment_method=s.assignment_method
        )
        for s in result.normalized.splits
    ]
    
    warning_responses = [
        SchedulerWarningResponse(
            code=w.code.value,
            message=w.message,
            competition_ids=[str(c) for c in w.competition_ids],
            stage_ids=[str(s) for s in w.stage_ids],
            severity=w.severity
        )
        for w in result.warnings
    ]
    
    stage_plan_responses = [
        StagePlanResponse(
            stage_id=str(sp.stage_id),
            stage_name=sp.stage_name,
            coverage_block_count=len(sp.coverage_blocks),
            is_championship_capable=sp.is_championship_capable,
            track=sp.track
        )
        for sp in result.stage_plan
    ]
    
    placement_responses = [
        PlacementResponse(
            competition_id=str(p.competition_id),
            competition_name=comp_names.get(p.competition_id, "Unknown"),
            stage_id=str(p.stage_id),
            stage_name=stage_names.get(p.stage_id, "Unknown"),
            scheduled_start=p.scheduled_start,
            scheduled_end=p.scheduled_end,
            duration_minutes=p.duration_minutes,
            entry_count=comp_entry_counts.get(p.competition_id, 0)
        )
        for p in result.placements
    ]
    
    lunch_responses = [
        LunchHoldResponse(
            stage_id=str(l.stage_id),
            stage_name=stage_names.get(l.stage_id, "Unknown"),
            start_time=l.start_time,
            end_time=l.end_time,
            duration_minutes=l.duration_minutes
        )
        for l in result.lunch_holds
    ]
    
    conflict_responses = [
        ScheduleConflict(
            conflict_type=c.conflict_type,
            severity=c.severity,
            message=c.message,
            affected_competition_ids=c.affected_competition_ids,
            affected_dancer_ids=c.affected_dancer_ids,
            affected_stage_ids=c.affected_stage_ids
        )
        for c in result.conflicts
    ]
    
    return InstantSchedulerResponse(
        success=True,
        message=f"Generated schedule with {result.total_competitions_scheduled} competitions across {len(result.stage_plan)} stages.",
        normalized=NormalizationResponse(
            merges=merge_responses,
            splits=split_responses,
            warnings=[w for w in warning_responses if w.code in ["small_comp_exhibition_risk"]],
            final_competition_count=result.normalized.final_competition_count
        ),
        stage_plan=stage_plan_responses,
        placements=placement_responses,
        lunch_holds=lunch_responses,
        warnings=warning_responses,
        conflicts=conflict_responses,
        total_competitions_scheduled=result.total_competitions_scheduled,
        total_competitions_unscheduled=result.total_competitions_unscheduled,
        merge_count=len(result.normalized.merges),
        split_count=len(result.normalized.splits),
        grade_competitions=result.grade_competitions,
        championship_competitions=result.championship_competitions
    )


@router.get("/feis/{feis_id}/conflicts", response_model=ConflictCheckResponse)
async def check_conflicts(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Check for scheduling conflicts in a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    conflicts = detect_all_conflicts(feis.id, session)
    
    warning_count = sum(1 for c in conflicts if c.severity == "warning")
    error_count = sum(1 for c in conflicts if c.severity == "error")
    
    conflict_responses = [
        ScheduleConflict(
            conflict_type=c.conflict_type,
            severity=c.severity,
            message=c.message,
            affected_competition_ids=c.affected_competition_ids,
            affected_dancer_ids=c.affected_dancer_ids,
            affected_stage_ids=c.affected_stage_ids
        )
        for c in conflicts
    ]
    
    return ConflictCheckResponse(
        has_conflicts=len(conflicts) > 0,
        warning_count=warning_count,
        error_count=error_count,
        conflicts=conflict_responses
    )


# ============= Entry Management =============

@router.get("/feis/{feis_id}/entries", response_model=List[EntryResponse])
async def list_entries(
    feis_id: str, 
    session: Session = Depends(get_session),
    paid: Optional[bool] = None,
    has_number: Optional[bool] = None
):
    """List all entries for a feis with optional filters."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in competitions]
    comp_map = {c.id: c for c in competitions}
    
    if not comp_ids:
        return []
    
    statement = select(Entry).where(Entry.competition_id.in_(comp_ids))
    
    if paid is not None:
        statement = statement.where(Entry.paid == paid)
    if has_number is not None:
        if has_number:
            statement = statement.where(Entry.competitor_number.isnot(None))
        else:
            statement = statement.where(Entry.competitor_number.is_(None))
    
    entries = session.exec(statement).all()
    
    result = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        comp = comp_map.get(entry.competition_id)
        if dancer and comp:
            result.append(EntryResponse(
                id=str(entry.id),
                dancer_id=str(entry.dancer_id),
                dancer_name=dancer.name,
                dancer_school=None,
                competition_id=str(entry.competition_id),
                competition_name=comp.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result


@router.post("/feis/{feis_id}/assign-numbers", response_model=BulkNumberAssignmentResponse)
async def bulk_assign_numbers(feis_id: str, data: BulkNumberAssignment, session: Session = Depends(get_session)):
    """Bulk assign competitor numbers to all entries without numbers."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in competitions]
    
    if not comp_ids:
        return BulkNumberAssignmentResponse(assigned_count=0, message="No competitions found")
    
    entries = session.exec(
        select(Entry)
        .where(Entry.competition_id.in_(comp_ids))
        .where(Entry.competitor_number.is_(None))
    ).all()
    
    dancer_ids = list(set(e.dancer_id for e in entries))
    
    current_number = data.start_number
    dancer_numbers = {}
    
    for dancer_id in dancer_ids:
        dancer_numbers[dancer_id] = current_number
        current_number += 1
    
    for entry in entries:
        entry.competitor_number = dancer_numbers[entry.dancer_id]
        session.add(entry)
    
    session.commit()
    
    return BulkNumberAssignmentResponse(
        assigned_count=len(dancer_ids),
        message=f"Assigned numbers {data.start_number} to {current_number - 1} to {len(dancer_ids)} dancers"
    )


# ============= Number Cards =============

@router.get("/feis/{feis_id}/number-cards")
async def generate_feis_number_cards(
    feis_id: str,
    session: Session = Depends(get_session),
    base_url: str = Query("https://openfeis.com", description="Base URL for QR code check-in links"),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Generate a PDF of all number cards for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only generate cards for your own feis")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    if not competitions:
        raise HTTPException(status_code=400, detail="No competitions found for this feis")
    
    comp_ids = [c.id for c in competitions]
    comp_map = {c.id: c for c in competitions}
    
    entries = session.exec(
        select(Entry)
        .where(Entry.competition_id.in_(comp_ids))
        .where(Entry.competitor_number.isnot(None))
    ).all()
    
    if not entries:
        raise HTTPException(
            status_code=400, 
            detail="No entries with assigned competitor numbers found. Please assign numbers first."
        )
    
    dancer_entries: dict[UUID, list[Entry]] = {}
    for entry in entries:
        if entry.dancer_id not in dancer_entries:
            dancer_entries[entry.dancer_id] = []
        dancer_entries[entry.dancer_id].append(entry)
    
    cards: List[NumberCardData] = []
    
    for dancer_id, dancer_entry_list in dancer_entries.items():
        dancer = session.get(Dancer, dancer_id)
        if not dancer:
            continue
        
        competitor_number = dancer_entry_list[0].competitor_number
        school_name = get_school_name(session, dancer.school_id)
        comp_age = calculate_competition_age(dancer.dob, feis.date)
        age_group = f"U{comp_age}"
        level = dancer.current_level.value.title()
        
        competition_codes = []
        for entry in dancer_entry_list:
            comp = comp_map.get(entry.competition_id)
            if comp:
                competition_codes.append(comp.name[:20])
        
        cards.append(NumberCardData(
            dancer_id=str(dancer_id),
            dancer_name=dancer.name,
            school_name=school_name,
            competitor_number=competitor_number,
            age_group=age_group,
            level=level,
            competition_codes=competition_codes,
            feis_name=feis.name,
            feis_date=feis.date
        ))
    
    if not cards:
        raise HTTPException(status_code=400, detail="No valid card data found")
    
    pdf_buffer = generate_number_cards_pdf(cards, base_url=base_url)
    
    safe_feis_name = "".join(c for c in feis.name if c.isalnum() or c in " -_").strip()
    filename = f"{safe_feis_name}_NumberCards.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


# ============= Flags =============

@router.get("/feis/{feis_id}/flags", response_model=FlaggedEntriesResponse)
async def get_feis_flags(
    feis_id: str,
    include_resolved: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Get all flagged entries for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    entry_ids = session.exec(
        select(Entry.id)
        .join(Competition)
        .where(Competition.feis_id == feis.id)
    ).all()
    
    query = select(EntryFlag).where(EntryFlag.entry_id.in_(entry_ids))
    if not include_resolved:
        query = query.where(EntryFlag.resolved == False)
    
    flags = session.exec(query.order_by(EntryFlag.created_at.desc())).all()
    
    flag_responses = []
    for flag in flags:
        entry = session.get(Entry, flag.entry_id)
        dancer = session.get(Dancer, entry.dancer_id) if entry else None
        competition = session.get(Competition, entry.competition_id) if entry else None
        flagged_by_user = session.get(User, flag.flagged_by)
        resolved_by_user = session.get(User, flag.resolved_by) if flag.resolved_by else None
        
        flag_responses.append(EntryFlagResponse(
            id=str(flag.id),
            entry_id=str(flag.entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_name=competition.name if competition else "Unknown",
            flagged_by=str(flag.flagged_by),
            flagged_by_name=flagged_by_user.name if flagged_by_user else "Unknown",
            reason=flag.reason,
            flag_type=flag.flag_type,
            resolved=flag.resolved,
            resolved_by=str(flag.resolved_by) if flag.resolved_by else None,
            resolved_by_name=resolved_by_user.name if resolved_by_user else None,
            resolved_at=flag.resolved_at,
            resolution_note=flag.resolution_note,
            created_at=flag.created_at
        ))
    
    unresolved = len([f for f in flag_responses if not f.resolved])
    
    return FlaggedEntriesResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        total_flags=len(flag_responses),
        unresolved_count=unresolved,
        flags=flag_responses
    )


# ============= Capacity & Waitlist =============

@router.get("/feis/{feis_id}/capacity", response_model=FeisCapacityStatus)
async def get_feis_capacity_status(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get capacity status for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    cap_info = get_feis_capacity(session, UUID(feis_id))
    
    return FeisCapacityStatus(
        feis_id=str(feis.id),
        feis_name=feis.name,
        global_cap=cap_info.max_capacity,
        current_dancer_count=cap_info.current_count,
        spots_remaining=cap_info.spots_remaining,
        is_full=cap_info.is_full,
        waitlist_enabled=cap_info.waitlist_enabled,
        waitlist_count=cap_info.waitlist_count
    )


@router.get("/feis/{feis_id}/waitlist", response_model=WaitlistStatusResponse)
async def get_feis_waitlist_status(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get waitlist status for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    global_count = session.exec(
        select(func.count(WaitlistEntry.id))
        .where(WaitlistEntry.feis_id == UUID(feis_id))
        .where(WaitlistEntry.competition_id.is_(None))
        .where(WaitlistEntry.status == WaitlistStatus.WAITING)
    ).one()
    
    comp_waitlists = {}
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == UUID(feis_id))
    ).all()
    
    for comp in competitions:
        count = session.exec(
            select(func.count(WaitlistEntry.id))
            .where(WaitlistEntry.competition_id == comp.id)
            .where(WaitlistEntry.status == WaitlistStatus.WAITING)
        ).one()
        if count > 0:
            comp_waitlists[str(comp.id)] = count
    
    total = global_count + sum(comp_waitlists.values())
    
    user_entries = get_user_waitlist_entries(session, current_user.id, UUID(feis_id))
    user_entry_responses = []
    for entry in user_entries:
        dancer = session.get(Dancer, entry.dancer_id)
        comp = session.get(Competition, entry.competition_id) if entry.competition_id else None
        user_entry_responses.append(WaitlistEntryResponse(
            id=str(entry.id),
            feis_id=str(entry.feis_id),
            feis_name=feis.name,
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id) if entry.competition_id else None,
            competition_name=comp.name if comp else None,
            position=entry.position,
            status=entry.status,
            offer_sent_at=entry.offer_sent_at,
            offer_expires_at=entry.offer_expires_at,
            created_at=entry.created_at
        ))
    
    return WaitlistStatusResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        total_waiting=total,
        competition_waitlists=comp_waitlists,
        global_waitlist_count=global_count,
        user_waitlist_entries=user_entry_responses
    )


# ============= Check-in & Refunds =============

@router.get("/feis/{feis_id}/checkin-summary")
async def get_feis_checkin_summary(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get check-in summary for all competitions in a feis."""
    return get_feis_check_in_summary(session, UUID(feis_id))


@router.get("/feis/{feis_id}/refund-policy")
async def get_feis_refund_policy(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get the refund policy for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    policy = get_refund_policy(session, UUID(feis_id))
    return {
        "feis_id": feis_id,
        "feis_name": feis.name,
        **policy
    }


@router.get("/feis/{feis_id}/refund-stats")
async def get_feis_refund_statistics(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Get refund statistics for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    return get_feis_refund_stats(session, UUID(feis_id))


# ============= Adjudicator Roster =============

@router.get("/feis/{feis_id}/adjudicators", response_model=AdjudicatorListResponse)
async def list_feis_adjudicators(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get all adjudicators on the roster for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    adjudicators = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == UUID(feis_id))
    ).all()
    
    adjudicator_responses = []
    confirmed_count = 0
    invited_count = 0
    active_count = 0
    
    for adj in adjudicators:
        school_name = None
        if adj.school_affiliation_id:
            school = session.get(User, adj.school_affiliation_id)
            if school:
                school_name = school.name
        
        if adj.status == AdjudicatorStatus.CONFIRMED:
            confirmed_count += 1
        elif adj.status == AdjudicatorStatus.INVITED:
            invited_count += 1
        elif adj.status == AdjudicatorStatus.ACTIVE:
            active_count += 1
        
        adjudicator_responses.append(AdjudicatorResponse(
            id=str(adj.id),
            feis_id=str(adj.feis_id),
            user_id=str(adj.user_id) if adj.user_id else None,
            name=adj.name,
            email=adj.email,
            phone=adj.phone,
            credential=adj.credential,
            organization=adj.organization,
            school_affiliation_id=str(adj.school_affiliation_id) if adj.school_affiliation_id else None,
            school_affiliation_name=school_name,
            status=adj.status,
            invite_sent_at=adj.invite_sent_at,
            invite_expires_at=adj.invite_expires_at,
            has_access_pin=adj.access_pin_hash is not None,
            created_at=adj.created_at,
            confirmed_at=adj.confirmed_at
        ))
    
    return AdjudicatorListResponse(
        feis_id=feis_id,
        feis_name=feis.name,
        total_adjudicators=len(adjudicators),
        confirmed_count=confirmed_count,
        invited_count=invited_count,
        active_count=active_count,
        adjudicators=adjudicator_responses
    )


@router.post("/feis/{feis_id}/adjudicators", response_model=AdjudicatorResponse)
async def add_feis_adjudicator(
    feis_id: str,
    adjudicator_data: AdjudicatorCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Add an adjudicator to the feis roster."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can add adjudicators")
    
    existing = None
    if adjudicator_data.email:
        existing = session.exec(
            select(FeisAdjudicator)
            .where(FeisAdjudicator.feis_id == UUID(feis_id))
            .where(FeisAdjudicator.email == adjudicator_data.email)
        ).first()
    
    if not existing and adjudicator_data.user_id:
        existing = session.exec(
            select(FeisAdjudicator)
            .where(FeisAdjudicator.feis_id == UUID(feis_id))
            .where(FeisAdjudicator.user_id == UUID(adjudicator_data.user_id))
        ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="This adjudicator is already on the roster")
    
    adjudicator = FeisAdjudicator(
        feis_id=UUID(feis_id),
        user_id=UUID(adjudicator_data.user_id) if adjudicator_data.user_id else None,
        name=adjudicator_data.name,
        email=adjudicator_data.email,
        phone=adjudicator_data.phone,
        credential=adjudicator_data.credential,
        organization=adjudicator_data.organization,
        school_affiliation_id=UUID(adjudicator_data.school_affiliation_id) if adjudicator_data.school_affiliation_id else None,
        status=AdjudicatorStatus.CONFIRMED if adjudicator_data.user_id else AdjudicatorStatus.INVITED
    )
    
    session.add(adjudicator)
    session.commit()
    session.refresh(adjudicator)
    
    school_name = None
    if adjudicator.school_affiliation_id:
        school = session.get(User, adjudicator.school_affiliation_id)
        if school:
            school_name = school.name
    
    return AdjudicatorResponse(
        id=str(adjudicator.id),
        feis_id=str(adjudicator.feis_id),
        user_id=str(adjudicator.user_id) if adjudicator.user_id else None,
        name=adjudicator.name,
        email=adjudicator.email,
        phone=adjudicator.phone,
        credential=adjudicator.credential,
        organization=adjudicator.organization,
        school_affiliation_id=str(adjudicator.school_affiliation_id) if adjudicator.school_affiliation_id else None,
        school_affiliation_name=school_name,
        status=adjudicator.status,
        invite_sent_at=adjudicator.invite_sent_at,
        invite_expires_at=adjudicator.invite_expires_at,
        has_access_pin=adjudicator.access_pin_hash is not None,
        created_at=adjudicator.created_at,
        confirmed_at=adjudicator.confirmed_at
    )


# ============= Adjudicator Capacity & Scheduling Defaults =============

@router.get("/feis/{feis_id}/adjudicator-capacity", response_model=AdjudicatorCapacityResponse)
async def get_adjudicator_capacity(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get derived scheduling capacity metrics based on the adjudicator roster."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    adjudicators = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == UUID(feis_id))
    ).all()
    
    total = len(adjudicators)
    confirmed = len([a for a in adjudicators if a.status == AdjudicatorStatus.CONFIRMED])
    active = len([a for a in adjudicators if a.status == AdjudicatorStatus.ACTIVE])
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    grades_per_stage = getattr(settings, 'grades_judges_per_stage', None) or 1
    champs_per_panel = getattr(settings, 'champs_judges_per_panel', None) or 3
    
    available_judges = confirmed + active
    
    max_grade_stages = available_judges // grades_per_stage if grades_per_stage > 0 else 0
    max_champs_panels = available_judges // champs_per_panel if champs_per_panel > 0 else 0
    
    if available_judges == 0:
        recommendation = "No confirmed adjudicators yet. Add adjudicators to your roster to enable scheduling."
    elif available_judges < champs_per_panel:
        recommendation = f"With {available_judges} adjudicator(s), you can run up to {max_grade_stages} single-judge stage(s). You need at least {champs_per_panel} judges for championship panels."
    else:
        remaining_after_one_panel = available_judges - champs_per_panel
        grades_with_one_panel = remaining_after_one_panel // grades_per_stage
        
        recommendation = (
            f"With {available_judges} confirmed adjudicator(s), you can run:\n"
            f"- Up to {max_grade_stages} single-judge grade stages, OR\n"
            f"- Up to {max_champs_panels} championship panel(s) ({champs_per_panel} judges each), OR\n"
            f"- 1 championship panel + {grades_with_one_panel} grade stage(s)"
        )
    
    return AdjudicatorCapacityResponse(
        feis_id=feis_id,
        feis_name=feis.name,
        total_adjudicators=total,
        confirmed_count=confirmed,
        active_count=active,
        grades_judges_per_stage=grades_per_stage,
        champs_judges_per_panel=champs_per_panel,
        max_grade_stages=max_grade_stages,
        max_champs_panels=max_champs_panels,
        recommendation=recommendation
    )


@router.get("/feis/{feis_id}/scheduling-defaults", response_model=SchedulingDefaultsResponse)
async def get_scheduling_defaults(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get scheduling defaults for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    if not settings:
        return SchedulingDefaultsResponse(
            feis_id=feis_id,
            grades_judges_per_stage=1,
            champs_judges_per_panel=3,
            lunch_duration_minutes=30,
            lunch_window_start=None,
            lunch_window_end=None
        )
    
    return SchedulingDefaultsResponse(
        feis_id=feis_id,
        grades_judges_per_stage=settings.grades_judges_per_stage,
        champs_judges_per_panel=settings.champs_judges_per_panel,
        lunch_duration_minutes=settings.lunch_duration_minutes,
        lunch_window_start=settings.lunch_window_start,
        lunch_window_end=settings.lunch_window_end
    )


@router.put("/feis/{feis_id}/scheduling-defaults", response_model=SchedulingDefaultsResponse)
async def update_scheduling_defaults(
    feis_id: str,
    update_data: SchedulingDefaultsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update scheduling defaults for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can update scheduling defaults")
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    if not settings:
        settings = FeisSettings(feis_id=UUID(feis_id))
        session.add(settings)
    
    if update_data.grades_judges_per_stage is not None:
        settings.grades_judges_per_stage = update_data.grades_judges_per_stage
    if update_data.champs_judges_per_panel is not None:
        settings.champs_judges_per_panel = update_data.champs_judges_per_panel
    if update_data.lunch_duration_minutes is not None:
        settings.lunch_duration_minutes = update_data.lunch_duration_minutes
    if update_data.lunch_window_start is not None:
        from datetime import time as time_type
        settings.lunch_window_start = time_type.fromisoformat(update_data.lunch_window_start) if isinstance(update_data.lunch_window_start, str) else update_data.lunch_window_start
    if update_data.lunch_window_end is not None:
        from datetime import time as time_type
        settings.lunch_window_end = time_type.fromisoformat(update_data.lunch_window_end) if isinstance(update_data.lunch_window_end, str) else update_data.lunch_window_end
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return SchedulingDefaultsResponse(
        feis_id=feis_id,
        grades_judges_per_stage=settings.grades_judges_per_stage,
        champs_judges_per_panel=settings.champs_judges_per_panel,
        lunch_duration_minutes=settings.lunch_duration_minutes,
        lunch_window_start=settings.lunch_window_start,
        lunch_window_end=settings.lunch_window_end
    )
