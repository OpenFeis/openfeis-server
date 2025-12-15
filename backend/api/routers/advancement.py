from fastapi import APIRouter, HTTPException, Depends
from typing import List
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import (
    User, Dancer, Competition, Feis, Entry,
    AdvancementNotice, PlacementHistory, CompetitionLevel, DanceType, RoleType
)
from backend.api.schemas import (
    AdvancementRuleInfo, AdvancementCheckResponse, AdvancementNoticeResponse,
    PlacementHistoryResponse, DancerPlacementHistoryResponse,
    AcknowledgeAdvancementRequest, OverrideAdvancementRequest
)

router = APIRouter()

# Advancement rules (CLRG-based system)
ADVANCEMENT_RULES = {
    CompetitionLevel.BEGINNER_1: {"wins": 3, "next": CompetitionLevel.BEGINNER_2, "per_dance": False},
    CompetitionLevel.BEGINNER_2: {"wins": 3, "next": CompetitionLevel.NOVICE, "per_dance": False},
    CompetitionLevel.NOVICE: {"wins": 3, "next": CompetitionLevel.PRIZEWINNER, "per_dance": True},
    CompetitionLevel.PRIZEWINNER: {"wins": 3, "next": CompetitionLevel.PRELIMINARY_CHAMPIONSHIP, "per_dance": True},
    CompetitionLevel.PRELIMINARY_CHAMPIONSHIP: {"wins": 3, "next": CompetitionLevel.OPEN_CHAMPIONSHIP, "per_dance": True},
}

@router.get("/advancement/rules", response_model=List[AdvancementRuleInfo])
async def get_advancement_rules():
    """Get the advancement rules for all levels."""
    rules = []
    for level, rule in ADVANCEMENT_RULES.items():
        rules.append(AdvancementRuleInfo(
            level=level,
            wins_required=rule["wins"],
            next_level=rule["next"],
            per_dance=rule["per_dance"],
            description=f"Advance from {level.value.replace('_', ' ').title()} to {rule['next'].value.replace('_', ' ').title()} after {rule['wins']} first place wins"
        ))
    
    return rules


@router.get("/dancers/{dancer_id}/placements", response_model=DancerPlacementHistoryResponse)
async def get_dancer_placements(
    dancer_id: str,
    session: Session = Depends(get_session)
):
    """Get all placement history for a dancer."""
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    placements = session.exec(
        select(PlacementHistory)
        .where(PlacementHistory.dancer_id == dancer.id)
        .order_by(PlacementHistory.competition_date.desc())
    ).all()
    
    placement_responses = []
    for p in placements:
        comp = session.get(Competition, p.competition_id)
        feis = session.get(Feis, p.feis_id)
        
        placement_responses.append(PlacementHistoryResponse(
            id=str(p.id),
            dancer_id=str(p.dancer_id),
            dancer_name=dancer.name,
            competition_id=str(p.competition_id),
            competition_name=comp.name if comp else "Unknown",
            feis_id=str(p.feis_id),
            feis_name=feis.name if feis else "Unknown",
            rank=p.rank,
            irish_points=p.irish_points,
            dance_type=p.dance_type,
            level=p.level,
            competition_date=p.competition_date,
            triggered_advancement=p.triggered_advancement,
            created_at=p.created_at
        ))
    
    first_places = len([p for p in placements if p.rank == 1])
    
    return DancerPlacementHistoryResponse(
        dancer_id=str(dancer.id),
        dancer_name=dancer.name,
        total_placements=len(placements),
        first_place_count=first_places,
        placements=placement_responses
    )


@router.post("/placements", response_model=PlacementHistoryResponse)
async def record_placement(
    placement_data,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Record a placement for a dancer."""
    from backend.api.schemas import PlacementHistoryCreate
    
    dancer = session.get(Dancer, UUID(placement_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    competition = session.get(Competition, UUID(placement_data.competition_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, UUID(placement_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    placement = PlacementHistory(
        dancer_id=dancer.id,
        competition_id=competition.id,
        feis_id=feis.id,
        entry_id=UUID(placement_data.entry_id) if placement_data.entry_id else None,
        rank=placement_data.rank,
        irish_points=placement_data.irish_points,
        dance_type=placement_data.dance_type or competition.dance_type,
        level=placement_data.level,
        competition_date=placement_data.competition_date
    )
    
    session.add(placement)
    session.commit()
    session.refresh(placement)
    
    return PlacementHistoryResponse(
        id=str(placement.id),
        dancer_id=str(placement.dancer_id),
        dancer_name=dancer.name,
        competition_id=str(placement.competition_id),
        competition_name=competition.name,
        feis_id=str(placement.feis_id),
        feis_name=feis.name,
        rank=placement.rank,
        irish_points=placement.irish_points,
        dance_type=placement.dance_type,
        level=placement.level,
        competition_date=placement.competition_date,
        triggered_advancement=placement.triggered_advancement,
        created_at=placement.created_at
    )


@router.get("/dancers/{dancer_id}/advancement", response_model=AdvancementCheckResponse)
async def check_dancer_advancement(
    dancer_id: str,
    session: Session = Depends(get_session)
):
    """Check a dancer's advancement status. Returns pending advancements and eligible levels."""
    from backend.services.advancement import get_pending_advancements, get_eligible_levels
    
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    pending = get_pending_advancements(session, dancer.id)
    eligible, warnings = get_eligible_levels(session, dancer)
    
    pending_responses = []
    for n in pending:
        pending_responses.append(AdvancementNoticeResponse(
            id=str(n.id),
            dancer_id=str(n.dancer_id),
            dancer_name=dancer.name,
            from_level=n.from_level,
            to_level=n.to_level,
            dance_type=n.dance_type,
            acknowledged=n.acknowledged,
            acknowledged_at=n.acknowledged_at,
            overridden=n.overridden,
            override_reason=n.override_reason,
            created_at=n.created_at
        ))
    
    return AdvancementCheckResponse(
        dancer_id=str(dancer.id),
        dancer_name=dancer.name,
        current_level=dancer.current_level,
        pending_advancements=pending_responses,
        eligible_levels=eligible,
        warnings=warnings
    )


@router.post("/advancement/{advancement_id}/acknowledge")
async def acknowledge_advancement_notice(
    advancement_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Acknowledge an advancement notice."""
    from backend.services.advancement import acknowledge_advancement
    
    try:
        notice = acknowledge_advancement(
            session, UUID(advancement_id), current_user.id
        )
        return {"success": True, "message": "Advancement acknowledged"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/advancement/{advancement_id}/override")
async def override_advancement_requirement(
    advancement_id: str,
    override_data: OverrideAdvancementRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Override an advancement requirement (admin only). Allows a dancer to continue competing at their current level."""
    from backend.services.advancement import override_advancement
    
    try:
        notice = override_advancement(
            session, UUID(advancement_id), current_user.id, override_data.reason
        )
        return {"success": True, "message": "Advancement requirement overridden"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
