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


def sync_competitions_with_coverage(
    session: Session,
    stage_id: Optional[UUID] = None,
    coverage_id: Optional[UUID] = None,
    feis_id: Optional[UUID] = None
) -> int:
    """
    Sync competition adjudicator/panel assignments based on stage coverage.
    
    Args:
        session: Database session
        stage_id: If provided, sync only competitions on this stage
        coverage_id: If provided, sync only competitions overlapping this specific coverage block
        feis_id: If provided, sync all competitions for this feis
    
    Returns:
        Number of competitions updated
    """
    from backend.scoring_engine.models_platform import Competition
    from datetime import datetime, timedelta
    
    # Build query for competitions to check
    query = select(Competition).where(
        Competition.stage_id.isnot(None),
        Competition.scheduled_time.isnot(None)
    )
    
    if stage_id:
        query = query.where(Competition.stage_id == stage_id)
    elif feis_id:
        query = query.where(Competition.feis_id == feis_id)
    
    competitions = session.exec(query).all()
    updated_count = 0
    
    for comp in competitions:
        if not comp.scheduled_time or not comp.stage_id:
            continue
        
        # Calculate competition end time
        duration_minutes = comp.estimated_duration_minutes or 2
        comp_start = comp.scheduled_time
        comp_end = comp_start + timedelta(minutes=duration_minutes)
        comp_date = comp_start.date()
        comp_start_time = comp_start.time()
        comp_end_time = comp_end.time()
        
        # Find coverage blocks that overlap with this competition
        coverage_query = select(StageJudgeCoverage).where(
            StageJudgeCoverage.stage_id == comp.stage_id,
            StageJudgeCoverage.feis_day == comp_date
        )
        
        if coverage_id:
            coverage_query = coverage_query.where(StageJudgeCoverage.id == coverage_id)
        
        coverage_blocks = session.exec(coverage_query).all()
        
        # Find the best matching coverage (longest overlap)
        best_coverage = None
        best_overlap_minutes = 0
        
        for cov in coverage_blocks:
            # Check if times overlap
            if comp_start_time < cov.end_time and comp_end_time > cov.start_time:
                # Calculate overlap duration
                overlap_start = max(comp_start_time, cov.start_time)
                overlap_end = min(comp_end_time, cov.end_time)
                
                # Convert to minutes for comparison
                overlap_minutes = (
                    datetime.combine(comp_date, overlap_end) - 
                    datetime.combine(comp_date, overlap_start)
                ).total_seconds() / 60
                
                if overlap_minutes > best_overlap_minutes:
                    best_overlap_minutes = overlap_minutes
                    best_coverage = cov
        
        # Update competition with coverage info
        old_adj = comp.adjudicator_id
        old_panel = comp.panel_id
        
        if best_coverage:
            # Assign judge or panel from coverage
            # Important: adjudicator_id on Competition should be the User.id, not FeisAdjudicator.id
            if best_coverage.feis_adjudicator_id:
                feis_adj = session.get(FeisAdjudicator, best_coverage.feis_adjudicator_id)
                comp.adjudicator_id = feis_adj.user_id if feis_adj and feis_adj.user_id else None
            else:
                comp.adjudicator_id = None
            
            comp.panel_id = best_coverage.panel_id
        else:
            # No coverage found - clear assignments
            comp.adjudicator_id = None
            comp.panel_id = None
        
        # Track if we actually changed something
        if old_adj != comp.adjudicator_id or old_panel != comp.panel_id:
            session.add(comp)
            updated_count += 1
    
    if updated_count > 0:
        session.commit()
    
    return updated_count

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
    """Get judge or panel coverage for a stage."""
    from backend.scoring_engine.models_platform import JudgePanel
    
    coverage = session.exec(
        select(StageJudgeCoverage).where(StageJudgeCoverage.stage_id == UUID(stage_id))
    ).all()
    
    results = []
    for cov in coverage:
        stage = session.get(Stage, cov.stage_id)
        
        adj_id = None
        adj_name = None
        panel_id = None
        panel_name = None
        is_panel = False
        
        if cov.feis_adjudicator_id:
            adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
            adj_id = str(cov.feis_adjudicator_id)
            adj_name = adj.name if adj else "Unknown"
        
        if cov.panel_id:
            panel = session.get(JudgePanel, cov.panel_id)
            panel_id = str(cov.panel_id)
            panel_name = panel.name if panel else "Unknown Panel"
            is_panel = True
        
        results.append(StageJudgeCoverageResponse(
            id=str(cov.id),
            stage_id=str(cov.stage_id),
            stage_name=stage.name if stage else "Unknown",
            feis_adjudicator_id=adj_id,
            adjudicator_name=adj_name,
            panel_id=panel_id,
            panel_name=panel_name,
            is_panel=is_panel,
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
    """Add a judge or panel coverage block to a stage."""
    
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only modify stages for your own feis")
    
    # Validate: must have either feis_adjudicator_id OR panel_id (not both, not neither)
    if not coverage_data.feis_adjudicator_id and not coverage_data.panel_id:
        raise HTTPException(status_code=400, detail="Must provide either feis_adjudicator_id or panel_id")
    if coverage_data.feis_adjudicator_id and coverage_data.panel_id:
        raise HTTPException(status_code=400, detail="Cannot assign both a single judge and a panel")
    
    # Verify adjudicator or panel exists
    adj = None
    panel = None
    adj_name = None
    panel_name = None
    
    if coverage_data.feis_adjudicator_id:
        from backend.scoring_engine.models_platform import FeisAdjudicator
        adj = session.get(FeisAdjudicator, UUID(coverage_data.feis_adjudicator_id))
        if not adj or adj.feis_id != feis.id:
            raise HTTPException(status_code=400, detail="Adjudicator not found on this feis roster")
        adj_name = adj.name
    
    if coverage_data.panel_id:
        from backend.scoring_engine.models_platform import JudgePanel
        panel = session.get(JudgePanel, UUID(coverage_data.panel_id))
        if not panel or panel.feis_id != feis.id:
            raise HTTPException(status_code=400, detail="Panel not found for this feis")
        panel_name = panel.name
    
    try:
        # Parse date and time strings
        if isinstance(coverage_data.feis_day, str):
            feis_day_parsed = date.fromisoformat(coverage_data.feis_day)
        else:
            feis_day_parsed = coverage_data.feis_day

        # Handle time format HH:MM or HH:MM:SS manually to avoid any timezone/locale issues
        def parse_time_str(t_str: str) -> time:
            if not isinstance(t_str, str):
                return t_str
            parts = t_str.split(':')
            return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)

        start_time_parsed = parse_time_str(coverage_data.start_time)
        end_time_parsed = parse_time_str(coverage_data.end_time)
        
        print(f"DEBUG: coverage_data.start_time='{coverage_data.start_time}' -> parsed={start_time_parsed}")
             
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date or time format: {str(e)}")

    # Check for overlapping coverage (for single judge only)
    if coverage_data.feis_adjudicator_id:
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
        feis_adjudicator_id=UUID(coverage_data.feis_adjudicator_id) if coverage_data.feis_adjudicator_id else None,
        panel_id=UUID(coverage_data.panel_id) if coverage_data.panel_id else None,
        feis_day=feis_day_parsed,
        start_time=start_time_parsed,
        end_time=end_time_parsed,
        note=coverage_data.note
    )
    session.add(coverage)
    session.commit()
    session.refresh(coverage)
    
    # Auto-sync competitions on this stage with the new coverage
    updated_count = sync_competitions_with_coverage(session, stage_id=stage.id)
    print(f"INFO: Added coverage to {stage.name}, auto-synced {updated_count} competitions")
    
    return StageJudgeCoverageResponse(
        id=str(coverage.id),
        stage_id=str(coverage.stage_id),
        stage_name=stage.name,
        feis_adjudicator_id=str(coverage.feis_adjudicator_id) if coverage.feis_adjudicator_id else None,
        adjudicator_name=adj_name,
        panel_id=str(coverage.panel_id) if coverage.panel_id else None,
        panel_name=panel_name,
        is_panel=coverage.panel_id is not None,
        feis_day=coverage.feis_day.isoformat(),
        # Use input strings to guarantee immediate UI consistency, 
        # avoiding any DB roundtrip formatting quirks for the immediate response
        start_time=coverage_data.start_time, 
        end_time=coverage_data.end_time,
        note=coverage.note
    )


@router.delete("/stage-coverage/{coverage_id}")
async def delete_stage_coverage(
    coverage_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete a judge coverage block and re-sync affected competitions."""
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
    
    # Store stage_id before deleting
    affected_stage_id = coverage.stage_id
    
    session.delete(coverage)
    session.commit()
    
    # Re-sync competitions on this stage (they may now have no coverage or different coverage)
    updated_count = sync_competitions_with_coverage(session, stage_id=affected_stage_id)
    print(f"INFO: Deleted coverage from {stage.name}, re-synced {updated_count} competitions")
    
    return {"message": "Coverage block deleted", "competitions_updated": updated_count}


@router.post("/feis/{feis_id}/sync-judge-coverage")
async def sync_feis_judge_coverage(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Manually sync all competitions in a feis with current judge coverage.
    This is useful when:
    - Competitions were scheduled before judge coverage was added
    - Judge assignments need to be refreshed after bulk changes
    - Fixing any inconsistencies in judge assignments
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only sync your own feis")
    
    # Sync all competitions in this feis
    updated_count = sync_competitions_with_coverage(session, feis_id=feis.id)
    
    return {
        "message": f"Successfully synced {updated_count} competitions with judge coverage",
        "competitions_updated": updated_count
    }


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
