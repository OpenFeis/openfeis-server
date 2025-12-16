from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, date, time
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import User, Stage, StageJudgeCoverage, Feis, FeisAdjudicator, RoleType
from backend.api.schemas import (
    StageCreate, StageUpdate, StageResponse, StageJudgeCoverageCreate, StageJudgeCoverageResponse,
    DurationEstimateRequest, DurationEstimateResponse
)
from backend.services.scheduling import estimate_duration

router = APIRouter()

@router.post("/stages", response_model=StageResponse)
async def create_stage(
    stage_data: StageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create a new stage."""
    feis = session.get(Feis, UUID(stage_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only create stages for your own feis")
    
    stage = Stage(
        feis_id=feis.id,
        name=stage_data.name,
        color=stage_data.color,
        sequence=stage_data.sequence
    )
    session.add(stage)
    session.commit()
    session.refresh(stage)
    
    return StageResponse(
        id=str(stage.id),
        feis_id=str(stage.feis_id),
        name=stage.name,
        color=stage.color,
        sequence=stage.sequence,
        competition_count=0,
        judge_coverage=[]
    )


@router.put("/stages/{stage_id}", response_model=StageResponse)
async def update_stage(
    stage_id: str,
    stage_data: StageUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a stage."""
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if stage_data.name is not None:
        stage.name = stage_data.name
    if stage_data.color is not None:
        stage.color = stage_data.color
    if stage_data.sequence is not None:
        stage.sequence = stage_data.sequence
    
    session.add(stage)
    session.commit()
    session.refresh(stage)
    
    from backend.scoring_engine.models_platform import Competition
    comp_count = session.exec(
        select(func.count(Competition.id)).where(Competition.stage_id == stage.id)
    ).one()
    
    return StageResponse(
        id=str(stage.id),
        feis_id=str(stage.feis_id),
        name=stage.name,
        color=stage.color,
        sequence=stage.sequence,
        competition_count=comp_count,
        judge_coverage=[]
    )


@router.delete("/stages/{stage_id}")
async def delete_stage(
    stage_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete a stage. Competitions assigned to this stage will have their stage_id cleared."""
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete stages for your own feis")
    
    # Clear stage_id from any competitions assigned to this stage
    from backend.scoring_engine.models_platform import Competition
    competitions = session.exec(
        select(Competition).where(Competition.stage_id == stage.id)
    ).all()
    for comp in competitions:
        comp.stage_id = None
        session.add(comp)
    
    # Delete judge coverage blocks for this stage
    coverage_blocks = session.exec(
        select(StageJudgeCoverage).where(StageJudgeCoverage.stage_id == stage.id)
    ).all()
    for block in coverage_blocks:
        session.delete(block)
    
    session.delete(stage)
    session.commit()
    
    return {"message": f"Stage '{stage.name}' deleted"}


@router.get("/stages/{stage_id}/coverage", response_model=List[StageJudgeCoverageResponse])
async def get_stage_coverage(
    stage_id: str,
    session: Session = Depends(get_session)
):
    """Get judge coverage for a stage."""
    coverage = session.exec(
        select(StageJudgeCoverage).where(StageJudgeCoverage.stage_id == UUID(stage_id))
    ).all()
    
    results = []
    for cov in coverage:
        stage = session.get(Stage, cov.stage_id)
        adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
        
        results.append(StageJudgeCoverageResponse(
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
    
    return results


@router.post("/stages/{stage_id}/coverage", response_model=StageJudgeCoverageResponse)
async def create_stage_coverage(
    stage_id: str,
    coverage_data: StageJudgeCoverageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Add a judge coverage block to a stage."""
    
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only modify stages for your own feis")
    
    # Verify adjudicator is on the feis roster
    adj = session.get(FeisAdjudicator, UUID(coverage_data.feis_adjudicator_id))
    if not adj or adj.feis_id != feis.id:
        raise HTTPException(status_code=400, detail="Adjudicator not found on this feis roster")
    
    try:
        # Parse date and time strings
        if isinstance(coverage_data.feis_day, str):
            feis_day_parsed = date.fromisoformat(coverage_data.feis_day)
        else:
            feis_day_parsed = coverage_data.feis_day

        # Handle time format HH:MM or HH:MM:SS
        if isinstance(coverage_data.start_time, str):
            if len(coverage_data.start_time) == 5:
                start_time_parsed = datetime.strptime(coverage_data.start_time, "%H:%M").time()
            else:
                start_time_parsed = time.fromisoformat(coverage_data.start_time)
        else:
            start_time_parsed = coverage_data.start_time
             
        if isinstance(coverage_data.end_time, str):
            if len(coverage_data.end_time) == 5:
                end_time_parsed = datetime.strptime(coverage_data.end_time, "%H:%M").time()
            else:
                end_time_parsed = time.fromisoformat(coverage_data.end_time)
        else:
            end_time_parsed = coverage_data.end_time
             
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date or time format: {str(e)}")

    # Check for overlapping coverage for this judge
    existing_coverage = session.exec(
        select(StageJudgeCoverage)
        .where(StageJudgeCoverage.feis_adjudicator_id == UUID(coverage_data.feis_adjudicator_id))
        .where(StageJudgeCoverage.feis_day == feis_day_parsed)
    ).all()

    for cov in existing_coverage:
        # Check if times overlap
        if (start_time_parsed < cov.end_time and end_time_parsed > cov.start_time):
            conflicting_stage = session.get(Stage, cov.stage_id)
            stage_name = conflicting_stage.name if conflicting_stage else "Unknown Stage"
            raise HTTPException(
                status_code=409, 
                detail=f"Judge {adj.name} is already covering {stage_name} from {cov.start_time.strftime('%H:%M')} to {cov.end_time.strftime('%H:%M')}"
            )
    
    coverage = StageJudgeCoverage(
        stage_id=stage.id,
        feis_adjudicator_id=UUID(coverage_data.feis_adjudicator_id),
        feis_day=feis_day_parsed,
        start_time=start_time_parsed,
        end_time=end_time_parsed,
        note=coverage_data.note
    )
    session.add(coverage)
    session.commit()
    session.refresh(coverage)
    
    return StageJudgeCoverageResponse(
        id=str(coverage.id),
        stage_id=str(coverage.stage_id),
        stage_name=stage.name,
        feis_adjudicator_id=str(coverage.feis_adjudicator_id),
        adjudicator_name=adj.name,
        feis_day=coverage.feis_day.isoformat(),
        start_time=coverage.start_time.strftime("%H:%M"),
        end_time=coverage.end_time.strftime("%H:%M"),
        note=coverage.note
    )


@router.delete("/stage-coverage/{coverage_id}")
async def delete_stage_coverage(
    coverage_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete a judge coverage block."""
    coverage = session.get(StageJudgeCoverage, UUID(coverage_id))
    if not coverage:
        raise HTTPException(status_code=404, detail="Coverage block not found")
    
    stage = session.get(Stage, coverage.stage_id)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only modify stages for your own feis")
    
    session.delete(coverage)
    session.commit()
    
    return {"message": "Coverage block deleted"}


@router.post("/scheduling/estimate-duration", response_model=DurationEstimateResponse)
async def estimate_competition_duration(
    request: DurationEstimateRequest,
    session: Session = Depends(get_session)
):
    """Estimate the duration of a competition."""
    estimated_minutes, rotations, breakdown = estimate_duration(
        entry_count=request.entry_count,
        bars=request.bars,
        tempo_bpm=request.tempo_bpm,
        dancers_per_rotation=request.dancers_per_rotation,
        setup_time_minutes=request.setup_time_minutes
    )
    
    return DurationEstimateResponse(
        estimated_minutes=estimated_minutes,
        rotations=rotations,
        breakdown=breakdown
    )
