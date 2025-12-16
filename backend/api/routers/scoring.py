from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_adjudicator
from backend.scoring_engine.models import JudgeScore, RoundResult, Round
from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Entry, Dancer, RoleType,
    FeisAdjudicator, StageJudgeCoverage
)
from datetime import datetime
from backend.scoring_engine.calculator import IrishPointsCalculator
from backend.api.schemas import (
    ScoreSubmission, ScoreSubmissionResponse,
    CompetitorForScoring, CompetitionForScoring,
    TabulatorResults, TabulatorResultItem, CompetitionWithScores, JudgeScoreDetailSchema,
    FeisResponse
)
from backend.api.websocket import manager as ws_manager
import asyncio

router = APIRouter()
calculator = IrishPointsCalculator()

@router.post("/scores", response_model=JudgeScore)
async def submit_score(
    score: JudgeScore, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """Submit a score. Requires adjudicator role."""
    session.add(score)
    session.commit()
    session.refresh(score)
    
    # Broadcast to connected clients
    asyncio.create_task(ws_manager.broadcast_score_update(score))
    
    return score


@router.post("/scores/batch", response_model=List[JudgeScore])
async def submit_score_batch(
    scores: List[JudgeScore],
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """Submit multiple scores (for sync). Requires adjudicator role."""
    for score in scores:
        if not session.get(JudgeScore, score.id):
            session.add(score)
    session.commit()
    return scores


@router.get("/rounds", response_model=List[Round])
async def get_rounds(session: Session = Depends(get_session)):
    return session.exec(select(Round)).all()

@router.get("/results/{round_id}")
async def get_round_results(round_id: str, session: Session = Depends(get_session)):
    statement = select(JudgeScore).where(JudgeScore.round_id == round_id)
    round_scores = session.exec(statement).all()
    return calculator.calculate_round(round_id, list(round_scores))


@router.get("/judge/competitions", response_model=List[CompetitionForScoring])
async def list_judge_competitions(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    List competitions assigned to the current judge for a feis.
    
    Includes:
    1. Direct assignments (Competition.adjudicator_id)
    2. Coverage assignments (StageJudgeCoverage) - allows for panels/ping-pong judging
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # 1. Get directly assigned competitions
    direct_competitions = session.exec(
        select(Competition)
        .where(Competition.feis_id == feis.id)
        .where(Competition.adjudicator_id == current_user.id)
    ).all()
    
    # 2. Get competitions via stage coverage
    # Find all coverage blocks for this judge on this feis
    # We need to find the FeisAdjudicator record first to get the ID
    feis_adjudicator = session.exec(
        select(FeisAdjudicator)
        .where(FeisAdjudicator.feis_id == feis.id)
        .where(FeisAdjudicator.user_id == current_user.id)
    ).first()

    coverage_competitions = []
    if feis_adjudicator:
        coverages = session.exec(
            select(StageJudgeCoverage)
            .where(StageJudgeCoverage.feis_adjudicator_id == feis_adjudicator.id)
        ).all()
        
        if coverages:
            # For each coverage block, find overlapping competitions
            for cov in coverages:
                # Convert coverage times to full datetimes for comparison if needed, 
                # but Competition.scheduled_time is a datetime.
                # We'll filter by stage and date first.
                
                # Note: We catch competitions that start within the window
                # or strictly overlap.
                stage_comps = session.exec(
                    select(Competition)
                    .where(Competition.feis_id == feis.id)
                    .where(Competition.stage_id == cov.stage_id)
                    .where(Competition.scheduled_time.isnot(None))
                ).all()
                
                for comp in stage_comps:
                    if not comp.scheduled_time:
                        continue
                        
                    comp_date = comp.scheduled_time.date()
                    if comp_date != cov.feis_day:
                        continue
                        
                    comp_start_time = comp.scheduled_time.time()
                    
                    # Simple check: does the competition start within the judge's block?
                    # or is it running during the block?
                    # Let's check if the Start Time is within the window [start, end)
                    if cov.start_time <= comp_start_time < cov.end_time:
                        coverage_competitions.append(comp)

    # Merge and deduplicate
    all_competitions_map = {c.id: c for c in direct_competitions}
    for c in coverage_competitions:
        all_competitions_map[c.id] = c
        
    sorted_competitions = sorted(
        all_competitions_map.values(), 
        key=lambda x: x.scheduled_time if x.scheduled_time else datetime.min
    )
    
    result = []
    for comp in sorted_competitions:
        # Count entries
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        result.append(CompetitionForScoring(
            id=str(comp.id),
            name=comp.name,
            feis_id=str(comp.feis_id),
            feis_name=feis.name,
            level=comp.level,
            competitor_count=entry_count
        ))
    
    return result


@router.get("/judge/competitions/{comp_id}/competitors", response_model=List[CompetitorForScoring])
async def get_competitors_for_scoring(
    comp_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """Get all competitors in a competition ready to be scored."""
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Get entries with assigned numbers
    entries = session.exec(
        select(Entry)
        .where(Entry.competition_id == competition.id)
        .where(Entry.competitor_number.isnot(None))
        .order_by(Entry.competitor_number)
    ).all()
    
    competitors = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        if not dancer:
            continue
        
        # Check for existing score from this judge
        existing_score = session.exec(
            select(JudgeScore)
            .where(JudgeScore.judge_id == current_user.id)
            .where(JudgeScore.competitor_id == entry.id)
            .where(JudgeScore.round_id == competition.id)
        ).first()
        
        school_name = None
        if dancer.school_id:
            school = session.get(User, dancer.school_id)
            school_name = school.name if school else None
        
        competitors.append(CompetitorForScoring(
            entry_id=str(entry.id),
            competitor_number=entry.competitor_number or 0,
            dancer_name=dancer.name,
            dancer_school=school_name,
            existing_score=existing_score.value if existing_score else None,
            existing_notes=existing_score.notes if existing_score else None
        ))
    
    return competitors


@router.post("/judge/scores", response_model=ScoreSubmissionResponse)
async def submit_judge_score(
    score_data: ScoreSubmission,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """Submit or update a score for a competitor."""
    # Validate entry exists
    entry = session.get(Entry, UUID(score_data.entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Validate competition exists
    competition = session.get(Competition, UUID(score_data.competition_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Validate entry belongs to competition
    if str(entry.competition_id) != score_data.competition_id:
        raise HTTPException(status_code=400, detail="Entry does not belong to this competition")
    
    # Validate score range
    if score_data.value < 0 or score_data.value > 100:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 100")
    
    # Check if judge has already scored this competitor
    existing = session.exec(
        select(JudgeScore)
        .where(JudgeScore.judge_id == str(current_user.id))
        .where(JudgeScore.competitor_id == str(entry.id))
        .where(JudgeScore.round_id == score_data.competition_id)
    ).first()
    
    if existing:
        # Update existing score
        existing.value = score_data.value
        existing.notes = score_data.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        score = existing
    else:
        # Create new score
        score = JudgeScore(
            judge_id=current_user.id,
            competitor_id=entry.id,
            round_id=UUID(score_data.competition_id),
            value=score_data.value,
            notes=score_data.notes
        )
        session.add(score)
        session.commit()
        session.refresh(score)
    
    # Broadcast update
    asyncio.create_task(ws_manager.broadcast_score_update(score))
    
    return ScoreSubmissionResponse(
        id=str(score.id),
        entry_id=str(entry.id),
        competition_id=score_data.competition_id,
        value=score.value,
        notes=score.notes,
        timestamp=score.timestamp.isoformat()
    )


@router.get("/tabulator/competitions", response_model=List[CompetitionWithScores])
async def list_tabulator_competitions(
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """List competitions with scores for tabulator."""
    statement = select(Competition)
    if feis_id:
        statement = statement.where(Competition.feis_id == UUID(feis_id))
    
    competitions = session.exec(statement).all()
    
    result = []
    for comp in competitions:
        # Count scores
        score_count = session.exec(
            select(func.count(JudgeScore.id))
            .join(Entry, JudgeScore.competitor_id == Entry.id)
            .where(Entry.competition_id == comp.id)
        ).one()
        
        if score_count > 0:
            feis = session.get(Feis, comp.feis_id)
            entry_count = session.exec(
                select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
            ).one()
            
            result.append(CompetitionWithScores(
                id=str(comp.id),
                name=comp.name,
                feis_id=str(comp.feis_id),
                feis_name=feis.name if feis else "Unknown",
                level=comp.level,
                entry_count=entry_count,
                score_count=score_count
            ))
    
    return result


@router.get("/competitions/{comp_id}/results", response_model=TabulatorResults)
async def get_competition_results(
    comp_id: str,
    session: Session = Depends(get_session)
):
    """
    Get calculated results for a competition with full competitor details.
    This is the main endpoint for the Tabulator Dashboard.
    """
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, competition.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all scores for this competition
    scores = session.exec(
        select(JudgeScore).where(JudgeScore.round_id == str(competition.id))
    ).all()
    
    # Calculate results using the scoring engine
    round_result = calculator.calculate_round(str(competition.id), list(scores))
    
    # Get unique judge count and map to names
    judge_ids = set(s.judge_id for s in scores)
    judge_uuids = [UUID(jid) for jid in judge_ids]
    judges = session.exec(select(User).where(User.id.in_(judge_uuids))).all()
    judge_map = {str(j.id): j.name for j in judges}
    
    # Calculate recall list
    recalled_ids = calculator.calculate_recall(round_result.results)
    recalled_set = set(recalled_ids)
    
    # Build rich results with dancer info
    result_items = []
    for ranked in round_result.results:
        entry = session.get(Entry, UUID(ranked.competitor_id))
        if not entry:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        if not dancer:
            continue
        
        school_name = None
        if dancer.school_id:
            teacher = session.get(User, dancer.school_id)
            school_name = teacher.name if teacher else None
        
        judge_details = []
        for detail in ranked.judge_scores:
            judge_name = judge_map.get(detail.judge_id, "Unknown Judge")
            judge_details.append(JudgeScoreDetailSchema(
                judge_id=detail.judge_id,
                judge_name=judge_name,
                raw_score=detail.raw_score,
                rank=detail.rank,
                irish_points=detail.irish_points
            ))
        
        judge_details.sort(key=lambda x: x.judge_name or "")

        result_items.append(TabulatorResultItem(
            rank=ranked.rank,
            competitor_number=entry.competitor_number,
            dancer_name=dancer.name,
            dancer_school=school_name,
            irish_points=ranked.irish_points,
            is_recalled=ranked.competitor_id in recalled_set,
            judge_scores=judge_details
        ))
    
    total_competitors = session.exec(
        select(func.count(Entry.id))
        .where(Entry.competition_id == competition.id)
        .where(Entry.competitor_number.isnot(None))
    ).one()
    
    return TabulatorResults(
        competition_id=str(competition.id),
        competition_name=competition.name,
        feis_name=feis.name,
        total_competitors=total_competitors,
        total_scores=len(scores),
        judge_count=len(judge_ids),
        results=result_items
    )
