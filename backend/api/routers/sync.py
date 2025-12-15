from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select, func
from backend.scoring_engine.models import JudgeScore
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_adjudicator
from backend.scoring_engine.models_platform import User
from backend.api.websocket import manager as ws_manager
import asyncio

# Define schemas inline since they might not exist in schemas.py yet
from pydantic import BaseModel
from typing import List as TypeList

class SyncScoreItem(BaseModel):
    id: str
    judge_id: str
    competitor_id: str
    round_id: str
    value: float
    timestamp: str

class SyncScoresRequest(BaseModel):
    scores: List[SyncScoreItem]

class SyncConflict(BaseModel):
    score_id: str
    entry_id: str
    competition_id: str
    local_value: float
    server_value: float
    local_timestamp: str
    server_timestamp: str

class SyncScoresResponse(BaseModel):
    uploaded: int
    failed: int
    conflicts: List[SyncConflict]
    successful_ids: List[str]
    message: str

class ConflictResolutionRequest(BaseModel):
    score_id: str
    resolution: str  # 'use_local' or 'use_server'
    local_value: float
    local_timestamp: str

router = APIRouter()

@router.post("/sync/scores", response_model=SyncScoresResponse)
async def sync_scores_batch(
    sync_data: SyncScoresRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    Batch sync scores from local device to cloud.
    
    Used after running a feis in local/offline mode to upload
    all accumulated scores to the cloud server.
    
    Handles conflicts where a score already exists with different data.
    """
    uploaded = 0
    failed = 0
    conflicts: TypeList[SyncConflict] = []
    successful_ids: TypeList[str] = []
    
    for score_item in sync_data.scores:
        try:
            # Parse the timestamp
            try:
                score_timestamp = datetime.fromisoformat(score_item.timestamp.replace('Z', '+00:00'))
            except ValueError:
                score_timestamp = datetime.utcnow()
            
            # Check for existing score
            existing_score = session.exec(
                select(JudgeScore)
                .where(JudgeScore.judge_id == score_item.judge_id)
                .where(JudgeScore.competitor_id == score_item.competitor_id)
                .where(JudgeScore.round_id == score_item.round_id)
            ).first()
            
            if existing_score:
                # Check if it's a conflict (different values)
                if existing_score.value != score_item.value:
                    conflicts.append(SyncConflict(
                        score_id=score_item.id,
                        entry_id=score_item.competitor_id,
                        competition_id=score_item.round_id,
                        local_value=score_item.value,
                        server_value=existing_score.value,
                        local_timestamp=score_item.timestamp,
                        server_timestamp=existing_score.timestamp.isoformat()
                    ))
                else:
                    # Same value, consider it successful
                    successful_ids.append(score_item.id)
                    uploaded += 1
            else:
                # Create new score
                new_score = JudgeScore(
                    id=UUID(score_item.id) if score_item.id else None,
                    judge_id=score_item.judge_id,
                    competitor_id=score_item.competitor_id,
                    round_id=score_item.round_id,
                    value=score_item.value,
                    timestamp=score_timestamp
                )
                session.add(new_score)
                successful_ids.append(score_item.id)
                uploaded += 1
        
        except Exception as e:
            print(f"Failed to sync score {score_item.id}: {e}")
            failed += 1
    
    session.commit()
    
    # Broadcast that results may have been updated
    for round_id in set(s.round_id for s in sync_data.scores):
        asyncio.create_task(ws_manager.broadcast_results_updated(round_id))
    
    message = f"Synced {uploaded} scores"
    if failed > 0:
        message += f", {failed} failed"
    if len(conflicts) > 0:
        message += f", {len(conflicts)} conflicts detected"
    
    return SyncScoresResponse(
        uploaded=uploaded,
        failed=failed,
        conflicts=conflicts,
        successful_ids=successful_ids,
        message=message
    )


@router.post("/sync/resolve")
async def resolve_sync_conflict(
    resolution: ConflictResolutionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    Resolve a sync conflict by choosing either local or server value.
    """
    # Find the existing score
    existing_score = session.exec(
        select(JudgeScore).where(JudgeScore.id == UUID(resolution.score_id))
    ).first()
    
    if not existing_score:
        raise HTTPException(status_code=404, detail="Score not found")
    
    if resolution.resolution == 'use_local':
        # Update server with local value
        existing_score.value = resolution.local_value
        try:
            existing_score.timestamp = datetime.fromisoformat(
                resolution.local_timestamp.replace('Z', '+00:00')
            )
        except ValueError:
            existing_score.timestamp = datetime.utcnow()
        
        session.add(existing_score)
        session.commit()
        
        return {"message": "Conflict resolved: using local value", "value": resolution.local_value}
    
    elif resolution.resolution == 'use_server':
        # Keep server value - nothing to change
        return {"message": "Conflict resolved: keeping server value", "value": existing_score.value}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid resolution type")


@router.get("/sync/status")
async def get_sync_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current sync status including pending data counts.
    Used by the frontend to show sync indicators.
    """
    # Count all scores (for display purposes)
    total_scores = session.exec(
        select(func.count(JudgeScore.id))
    ).one()
    
    # Get unique judges
    judge_count = session.exec(
        select(func.count(func.distinct(JudgeScore.judge_id)))
    ).one()
    
    # Get unique competitions with scores
    competition_count = session.exec(
        select(func.count(func.distinct(JudgeScore.round_id)))
    ).one()
    
    return {
        "total_scores": total_scores,
        "judge_count": judge_count,
        "competition_count": competition_count,
        "server_time": datetime.utcnow().isoformat()
    }
