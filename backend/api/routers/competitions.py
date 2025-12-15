from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import User, Feis, Competition, Entry, Dancer, RoleType, CheckInStatus
from backend.api.schemas import CompetitionCreate, CompetitionUpdate, CompetitionResponse, StageMonitorResponse, StageMonitorEntry
from backend.utils.competition_codes import generate_competition_code
from backend.services.scheduling import estimate_competition_duration
from backend.services.checkin import get_stage_monitor_data, get_competition_check_in_stats
from backend.services.waitlist import get_competition_capacity

router = APIRouter()

@router.post("/competitions", response_model=CompetitionResponse)
async def create_competition(
    comp_data: CompetitionCreate,
    session: Session = Depends(get_session)
):
    """Create a single competition."""
    feis = session.get(Feis, UUID(comp_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Generate code if not provided
    if not comp_data.code:
        code = generate_competition_code(
            level=comp_data.level.value,
            min_age=comp_data.min_age,
            dance_type=comp_data.dance_type.value if comp_data.dance_type else None
        )
    else:
        code = comp_data.code
    
    competition = Competition(
        feis_id=feis.id,
        name=comp_data.name,
        min_age=comp_data.min_age,
        max_age=comp_data.max_age,
        level=comp_data.level,
        gender=comp_data.gender,
        code=code,
        description=comp_data.description,
        allowed_levels=','.join([l.value for l in comp_data.allowed_levels]) if comp_data.allowed_levels else None,
        category=comp_data.category,
        is_mixed=comp_data.is_mixed,
        dance_type=comp_data.dance_type,
        tempo_bpm=comp_data.tempo_bpm,
        bars=comp_data.bars,
        scoring_method=comp_data.scoring_method,
        price_cents=comp_data.price_cents,
        max_entries=comp_data.max_entries
    )
    session.add(competition)
    session.commit()
    session.refresh(competition)
    
    return CompetitionResponse(
        id=str(competition.id),
        feis_id=str(competition.feis_id),
        name=competition.name,
        min_age=competition.min_age,
        max_age=competition.max_age,
        level=competition.level,
        gender=competition.gender,
        code=competition.code,
        category=competition.category,
        is_mixed=competition.is_mixed,
        entry_count=0,
        dance_type=competition.dance_type,
        tempo_bpm=competition.tempo_bpm,
        bars=competition.bars,
        scoring_method=competition.scoring_method,
        price_cents=competition.price_cents,
        max_entries=competition.max_entries,
        stage_id=None,
        scheduled_time=None,
        estimated_duration_minutes=None,
        adjudicator_id=None,
        description=competition.description,
        allowed_levels=competition.allowed_levels.split(',') if competition.allowed_levels else None
    )


@router.put("/competitions/{comp_id}", response_model=CompetitionResponse)
async def update_competition(
    comp_id: str,
    comp_data: CompetitionUpdate,
    session: Session = Depends(get_session)
):
    """Update a competition."""
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    if comp_data.name is not None:
        competition.name = comp_data.name
    if comp_data.min_age is not None:
        competition.min_age = comp_data.min_age
    if comp_data.max_age is not None:
        competition.max_age = comp_data.max_age
    if comp_data.level is not None:
        competition.level = comp_data.level
    if comp_data.gender is not None:
        competition.gender = comp_data.gender
    if comp_data.code is not None:
        competition.code = comp_data.code
    if comp_data.description is not None:
        competition.description = comp_data.description
    if comp_data.allowed_levels is not None:
        competition.allowed_levels = ','.join([l.value for l in comp_data.allowed_levels])
    if comp_data.category is not None:
        competition.category = comp_data.category
    if comp_data.is_mixed is not None:
        competition.is_mixed = comp_data.is_mixed
    if comp_data.dance_type is not None:
        competition.dance_type = comp_data.dance_type
    if comp_data.tempo_bpm is not None:
        competition.tempo_bpm = comp_data.tempo_bpm
    if comp_data.bars is not None:
        competition.bars = comp_data.bars
    if comp_data.scoring_method is not None:
        competition.scoring_method = comp_data.scoring_method
    if comp_data.price_cents is not None:
        competition.price_cents = comp_data.price_cents
    if comp_data.max_entries is not None:
        competition.max_entries = comp_data.max_entries
    if comp_data.stage_id is not None:
        competition.stage_id = UUID(comp_data.stage_id) if comp_data.stage_id else None
    if comp_data.scheduled_time is not None:
        competition.scheduled_time = comp_data.scheduled_time
    if comp_data.estimated_duration_minutes is not None:
        competition.estimated_duration_minutes = comp_data.estimated_duration_minutes
    if comp_data.adjudicator_id is not None:
        competition.adjudicator_id = UUID(comp_data.adjudicator_id) if comp_data.adjudicator_id else None
    
    session.add(competition)
    session.commit()
    session.refresh(competition)
    
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.competition_id == competition.id)
    ).one()
    
    return CompetitionResponse(
        id=str(competition.id),
        feis_id=str(competition.feis_id),
        name=competition.name,
        min_age=competition.min_age,
        max_age=competition.max_age,
        level=competition.level,
        gender=competition.gender,
        code=competition.code,
        category=competition.category,
        is_mixed=competition.is_mixed,
        entry_count=entry_count,
        dance_type=competition.dance_type,
        tempo_bpm=competition.tempo_bpm,
        bars=competition.bars,
        scoring_method=competition.scoring_method,
        price_cents=competition.price_cents,
        max_entries=competition.max_entries,
        stage_id=str(competition.stage_id) if competition.stage_id else None,
        scheduled_time=competition.scheduled_time,
        estimated_duration_minutes=competition.estimated_duration_minutes,
        adjudicator_id=str(competition.adjudicator_id) if competition.adjudicator_id else None,
        description=competition.description,
        allowed_levels=competition.allowed_levels.split(',') if competition.allowed_levels else None
    )


@router.delete("/competitions/{comp_id}")
async def delete_competition(
    comp_id: str,
    session: Session = Depends(get_session)
):
    """Delete a competition and its entries."""
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Delete all entries first
    entries = session.exec(
        select(Entry).where(Entry.competition_id == competition.id)
    ).all()
    for entry in entries:
        session.delete(entry)
    
    session.delete(competition)
    session.commit()
    
    return {"message": f"Competition '{competition.name}' deleted"}


@router.post("/competitions/{comp_id}/update-duration")
async def update_competition_duration(
    comp_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Recalculate and update the estimated duration for a competition."""
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Count entries
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.competition_id == competition.id)
    ).one()
    
    # Estimate duration
    duration = estimate_competition_duration(competition, entry_count)
    
    competition.estimated_duration_minutes = duration
    session.add(competition)
    session.commit()
    
    return {
        "competition_id": str(competition.id),
        "entry_count": entry_count,
        "estimated_duration_minutes": duration,
        "message": f"Updated duration to {duration} minutes"
    }


# ============= Stage Monitor and Check-in Stats =============

@router.get("/competitions/{competition_id}/stage-monitor", response_model=StageMonitorResponse)
async def get_stage_monitor(
    competition_id: str,
    current_position: int = 0,
    session: Session = Depends(get_session)
):
    """Get stage monitor data for a competition."""
    data = get_stage_monitor_data(session, UUID(competition_id), current_position)
    
    entries = [
        StageMonitorEntry(
            entry_id=e["entry_id"],
            competitor_number=e["competitor_number"],
            dancer_name=e["dancer_name"],
            school_name=e["school_name"],
            check_in_status=CheckInStatus(e["check_in_status"]),
            is_current=e["is_current"],
            is_on_deck=e["is_on_deck"]
        )
        for e in data.entries
    ]
    
    current_dancer = next((e for e in entries if e.is_current), None)
    on_deck = [e for e in entries if e.is_on_deck]
    
    return StageMonitorResponse(
        competition_id=data.competition_id,
        competition_name=data.competition_name,
        stage_name=data.stage_name,
        feis_name=data.feis_name,
        total_entries=data.total_entries,
        checked_in_count=data.checked_in_count,
        scratched_count=data.scratched_count,
        current_dancer=current_dancer,
        on_deck=on_deck,
        all_entries=entries
    )


@router.get("/competitions/{competition_id}/checkin-stats")
async def get_competition_checkin_stats(
    competition_id: str,
    session: Session = Depends(get_session)
):
    """Get check-in statistics for a competition."""
    return get_competition_check_in_stats(session, UUID(competition_id))


@router.get("/competitions/{competition_id}/capacity")
async def get_competition_capacity_status(
    competition_id: str,
    session: Session = Depends(get_session)
):
    """Get capacity status for a competition."""
    comp = session.get(Competition, UUID(competition_id))
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    cap_info = get_competition_capacity(session, UUID(competition_id))
    
    return {
        "competition_id": str(comp.id),
        "competition_name": comp.name,
        "max_entries": cap_info.max_capacity,
        "current_entries": cap_info.current_count,
        "spots_remaining": cap_info.spots_remaining,
        "is_full": cap_info.is_full,
        "waitlist_count": cap_info.waitlist_count
    }


@router.put("/competitions/{comp_id}/schedule")
async def update_competition_schedule(
    comp_id: str,
    schedule_update: dict,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Update competition scheduling details (stage, time, adjudicator).
    Auto-assigns judge based on stage coverage if not explicitly provided.
    """
    from backend.scoring_engine.models_platform import Stage, StageJudgeCoverage, FeisAdjudicator
    from datetime import datetime as dt
    
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Check ownership
    feis = session.get(Feis, competition.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields if provided
    if "stage_id" in schedule_update:
        competition.stage_id = UUID(schedule_update["stage_id"]) if schedule_update["stage_id"] else None
    if "scheduled_time" in schedule_update:
        if schedule_update["scheduled_time"]:
            competition.scheduled_time = dt.fromisoformat(schedule_update["scheduled_time"].replace('Z', '+00:00'))
        else:
            competition.scheduled_time = None
    if "estimated_duration_minutes" in schedule_update:
        competition.estimated_duration_minutes = schedule_update["estimated_duration_minutes"]
    
    # Handle adjudicator assignment
    if "adjudicator_id" in schedule_update:
        # Explicit assignment
        competition.adjudicator_id = UUID(schedule_update["adjudicator_id"]) if schedule_update["adjudicator_id"] else None
    elif competition.stage_id and competition.scheduled_time:
        # Auto-assign based on stage coverage
        comp_start = competition.scheduled_time
        comp_date = comp_start.date()
        comp_time = comp_start.time()
        
        # Find judges with coverage on this stage during this time
        coverages = session.exec(
            select(StageJudgeCoverage)
            .where(StageJudgeCoverage.stage_id == competition.stage_id)
            .where(StageJudgeCoverage.feis_day == comp_date)
        ).all()
        
        # Find a coverage block that includes this time
        for cov in coverages:
            if cov.start_time <= comp_time <= cov.end_time:
                # Get the FeisAdjudicator to find their user_id
                feis_adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
                if feis_adj and feis_adj.user_id:
                    competition.adjudicator_id = feis_adj.user_id
                    break
    
    session.add(competition)
    session.commit()
    session.refresh(competition)
    
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.competition_id == competition.id)
    ).one()
    
    return CompetitionResponse(
        id=str(competition.id),
        feis_id=str(competition.feis_id),
        name=competition.name,
        min_age=competition.min_age,
        max_age=competition.max_age,
        level=competition.level,
        gender=competition.gender,
        code=competition.code,
        category=competition.category,
        is_mixed=competition.is_mixed,
        entry_count=entry_count,
        dance_type=competition.dance_type,
        tempo_bpm=competition.tempo_bpm,
        bars=competition.bars,
        scoring_method=competition.scoring_method,
        price_cents=competition.price_cents,
        max_entries=competition.max_entries,
        stage_id=str(competition.stage_id) if competition.stage_id else None,
        scheduled_time=competition.scheduled_time,
        estimated_duration_minutes=competition.estimated_duration_minutes,
        adjudicator_id=str(competition.adjudicator_id) if competition.adjudicator_id else None,
        description=competition.description,
        allowed_levels=competition.allowed_levels.split(',') if competition.allowed_levels else None
    )
