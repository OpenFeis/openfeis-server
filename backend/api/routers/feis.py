"""
Feis Router - Core feis CRUD, organizers, settings, and Stripe integration.

Routes:
- GET/POST /feis - List and create feiseanna
- GET/PUT/DELETE /feis/{feis_id} - Single feis operations
- GET/POST/PUT/DELETE /feis/{feis_id}/organizers - Co-organizer management
- GET /feis/{feis_id}/competitions - List competitions
- DELETE /feis/{feis_id}/competitions/empty - Delete empty competitions
- GET /feis/{feis_id}/stages - List stages
- GET/PUT /feis/{feis_id}/settings - Feis settings
- GET/POST /feis/{feis_id}/fee-items - Fee items
- GET /feis/{feis_id}/registration-status - Registration status
- GET/POST /feis/{feis_id}/stripe-* - Stripe integration
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List
from uuid import UUID
from sqlmodel import Session, select, func
from backend.db.database import get_session
from backend.api.auth import get_current_user, require_organizer_or_admin
from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Entry, RoleType,
    Stage, FeisSettings, FeeItem, StageJudgeCoverage,
    FeisOrganizer, FeisAdjudicator, ScoringMethod
)
from backend.api.schemas import (
    FeisCreate, FeisUpdate, FeisResponse,
    CompetitionResponse,
    StageResponse, StageJudgeCoverageResponse,
    FeisSettingsUpdate, FeisSettingsResponse,
    FeeItemCreate, FeeItemUpdate, FeeItemResponse,
    RegistrationStatusResponse,
    StripeOnboardingRequest, StripeOnboardingResponse, StripeStatusResponse,
    FeisOrganizerCreate, FeisOrganizerUpdate, FeisOrganizerResponse, FeisOrganizerListResponse
)
from backend.services.cart import (
    get_feis_settings as get_cart_feis_settings,
    is_registration_open, is_late_registration
)
from backend.services.stripe import (
    is_stripe_configured, get_stripe_mode, is_organizer_connected,
    create_organizer_onboarding_link, check_onboarding_status
)

router = APIRouter()


# ============= Helper Functions =============

def is_feis_organizer(feis: Feis, user: User, session: Session) -> bool:
    """
    Check if a user is an organizer for a feis (primary or co-organizer).
    
    Returns True if:
    - User is the primary organizer (feis.organizer_id)
    - User is a co-organizer (FeisOrganizer entry)
    - User is a super_admin
    """
    if user.role == RoleType.SUPER_ADMIN:
        return True
    
    if feis.organizer_id == user.id:
        return True
    
    # Check co-organizers
    co_org = session.exec(
        select(FeisOrganizer).where(
            FeisOrganizer.feis_id == feis.id,
            FeisOrganizer.user_id == user.id
        )
    ).first()
    
    return co_org is not None


def get_feis_organizer_permissions(feis: Feis, user: User, session: Session) -> dict:
    """
    Get the permissions for a user on a feis.
    
    Returns a dict with permission flags, or None if not an organizer.
    """
    if user.role == RoleType.SUPER_ADMIN:
        return {
            "is_primary": False,
            "can_edit_feis": True,
            "can_manage_entries": True,
            "can_manage_schedule": True,
            "can_manage_adjudicators": True,
            "can_add_organizers": True,
        }
    
    if feis.organizer_id == user.id:
        return {
            "is_primary": True,
            "can_edit_feis": True,
            "can_manage_entries": True,
            "can_manage_schedule": True,
            "can_manage_adjudicators": True,
            "can_add_organizers": True,
        }
    
    # Check co-organizers
    co_org = session.exec(
        select(FeisOrganizer).where(
            FeisOrganizer.feis_id == feis.id,
            FeisOrganizer.user_id == user.id
        )
    ).first()
    
    if co_org:
        return {
            "is_primary": False,
            "can_edit_feis": co_org.can_edit_feis,
            "can_manage_entries": co_org.can_manage_entries,
            "can_manage_schedule": co_org.can_manage_schedule,
            "can_manage_adjudicators": co_org.can_manage_adjudicators,
            "can_add_organizers": co_org.can_add_organizers,
        }
    
    return None


# ============= Feis CRUD =============

@router.get("/feis", response_model=List[FeisResponse])
async def list_feiseanna(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """List all feiseanna with competition and entry counts."""
    statement = select(Feis).offset(skip).limit(limit)
    feiseanna = session.exec(statement).all()
    
    result = []
    for feis in feiseanna:
        comp_count = session.exec(
            select(func.count(Competition.id)).where(Competition.feis_id == feis.id)
        ).one()
        entry_count = session.exec(
            select(func.count(Entry.id))
            .join(Competition, Entry.competition_id == Competition.id)
            .where(Competition.feis_id == feis.id)
        ).one()
        
        result.append(FeisResponse(
            id=str(feis.id),
            name=feis.name,
            date=feis.date,
            location=feis.location,
            organizer_id=str(feis.organizer_id),
            stripe_account_id=feis.stripe_account_id,
            competition_count=comp_count,
            entry_count=entry_count
        ))
    
    return result


@router.get("/feis/mine", response_model=List[FeisResponse])
async def list_my_feiseanna(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    List feiseanna that the current user can manage.
    
    Returns feiseanna where:
    - User is the primary organizer (feis.organizer_id)
    - User is a co-organizer (FeisOrganizer entry)
    - User is a super_admin (returns all feiseanna)
    """
    if current_user.role == RoleType.SUPER_ADMIN:
        feiseanna = session.exec(select(Feis)).all()
    else:
        primary_feis_ids = session.exec(
            select(Feis.id).where(Feis.organizer_id == current_user.id)
        ).all()
        
        co_org_feis_ids = session.exec(
            select(FeisOrganizer.feis_id).where(FeisOrganizer.user_id == current_user.id)
        ).all()
        
        all_feis_ids = list(set(primary_feis_ids + co_org_feis_ids))
        
        if not all_feis_ids:
            return []
        
        feiseanna = session.exec(
            select(Feis).where(Feis.id.in_(all_feis_ids))
        ).all()
    
    result = []
    for feis in feiseanna:
        comp_count = session.exec(
            select(func.count(Competition.id)).where(Competition.feis_id == feis.id)
        ).one()
        entry_count = session.exec(
            select(func.count(Entry.id))
            .join(Competition, Entry.competition_id == Competition.id)
            .where(Competition.feis_id == feis.id)
        ).one()
        
        result.append(FeisResponse(
            id=str(feis.id),
            name=feis.name,
            date=feis.date,
            location=feis.location,
            organizer_id=str(feis.organizer_id),
            stripe_account_id=feis.stripe_account_id,
            competition_count=comp_count,
            entry_count=entry_count
        ))
    
    return result


@router.post("/feis", response_model=FeisResponse)
async def create_feis(
    feis_data: FeisCreate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create a new feis. Requires organizer or super_admin role."""
    if feis_data.organizer_id:
        organizer_id = UUID(feis_data.organizer_id)
    else:
        organizer_id = current_user.id
    
    feis = Feis(
        name=feis_data.name,
        date=feis_data.date,
        location=feis_data.location,
        organizer_id=organizer_id
    )
    session.add(feis)
    session.commit()
    session.refresh(feis)
    
    return FeisResponse(
        id=str(feis.id),
        name=feis.name,
        date=feis.date,
        location=feis.location,
        organizer_id=str(feis.organizer_id),
        stripe_account_id=feis.stripe_account_id,
        competition_count=0,
        entry_count=0
    )


@router.get("/feis/{feis_id}", response_model=FeisResponse)
async def get_feis(feis_id: str, session: Session = Depends(get_session)):
    """Get a specific feis by ID."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    comp_count = session.exec(
        select(func.count(Competition.id)).where(Competition.feis_id == feis.id)
    ).one()
    entry_count = session.exec(
        select(func.count(Entry.id))
        .join(Competition, Entry.competition_id == Competition.id)
        .where(Competition.feis_id == feis.id)
    ).one()
    
    return FeisResponse(
        id=str(feis.id),
        name=feis.name,
        date=feis.date,
        location=feis.location,
        organizer_id=str(feis.organizer_id),
        stripe_account_id=feis.stripe_account_id,
        competition_count=comp_count,
        entry_count=entry_count
    )


@router.put("/feis/{feis_id}", response_model=FeisResponse)
async def update_feis(
    feis_id: str, 
    feis_data: FeisUpdate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a feis. Requires organizer (owner/co-organizer) or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    perms = get_feis_organizer_permissions(feis, current_user, session)
    if not perms or not perms.get("can_edit_feis"):
        raise HTTPException(status_code=403, detail="You don't have permission to edit this feis")
    
    if feis_data.name is not None:
        feis.name = feis_data.name
    if feis_data.date is not None:
        feis.date = feis_data.date
    if feis_data.location is not None:
        feis.location = feis_data.location
    if feis_data.stripe_account_id is not None:
        feis.stripe_account_id = feis_data.stripe_account_id
    
    session.add(feis)
    session.commit()
    session.refresh(feis)
    
    comp_count = session.exec(
        select(func.count(Competition.id)).where(Competition.feis_id == feis.id)
    ).one()
    entry_count = session.exec(
        select(func.count(Entry.id))
        .join(Competition, Entry.competition_id == Competition.id)
        .where(Competition.feis_id == feis.id)
    ).one()
    
    return FeisResponse(
        id=str(feis.id),
        name=feis.name,
        date=feis.date,
        location=feis.location,
        organizer_id=str(feis.organizer_id),
        stripe_account_id=feis.stripe_account_id,
        competition_count=comp_count,
        entry_count=entry_count
    )


@router.delete("/feis/{feis_id}")
async def delete_feis(
    feis_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete a feis and all its competitions/entries. Requires primary organizer or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the primary organizer can delete a feis")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    for comp in competitions:
        entries = session.exec(
            select(Entry).where(Entry.competition_id == comp.id)
        ).all()
        for entry in entries:
            session.delete(entry)
        session.delete(comp)
    
    co_organizers = session.exec(
        select(FeisOrganizer).where(FeisOrganizer.feis_id == feis.id)
    ).all()
    for co_org in co_organizers:
        session.delete(co_org)
    
    session.delete(feis)
    session.commit()
    
    return {"message": f"Feis '{feis.name}' and all associated data deleted"}


# ============= Feis Co-Organizer Management =============

@router.get("/feis/{feis_id}/organizers", response_model=FeisOrganizerListResponse)
async def list_feis_organizers(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """List all organizers (primary and co-organizers) for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if not is_feis_organizer(feis, current_user, session):
        raise HTTPException(status_code=403, detail="You don't have access to this feis")
    
    primary = session.get(User, feis.organizer_id)
    
    co_organizers = session.exec(
        select(FeisOrganizer).where(FeisOrganizer.feis_id == feis.id)
    ).all()
    
    co_org_responses = []
    for co_org in co_organizers:
        user = session.get(User, co_org.user_id)
        added_by_user = session.get(User, co_org.added_by)
        co_org_responses.append(FeisOrganizerResponse(
            id=str(co_org.id),
            feis_id=str(co_org.feis_id),
            user_id=str(co_org.user_id),
            user_name=user.name if user else "Unknown",
            user_email=user.email if user else "",
            role=co_org.role,
            can_edit_feis=co_org.can_edit_feis,
            can_manage_entries=co_org.can_manage_entries,
            can_manage_schedule=co_org.can_manage_schedule,
            can_manage_adjudicators=co_org.can_manage_adjudicators,
            can_add_organizers=co_org.can_add_organizers,
            added_by=str(co_org.added_by),
            added_by_name=added_by_user.name if added_by_user else "Unknown",
            added_at=co_org.added_at
        ))
    
    return FeisOrganizerListResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        primary_organizer_id=str(feis.organizer_id),
        primary_organizer_name=primary.name if primary else "Unknown",
        co_organizers=co_org_responses,
        total_organizers=1 + len(co_org_responses)
    )


@router.post("/feis/{feis_id}/organizers", response_model=FeisOrganizerResponse)
async def add_feis_organizer(
    feis_id: str,
    organizer_data: FeisOrganizerCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Add a co-organizer to a feis. Requires permission to add organizers."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    perms = get_feis_organizer_permissions(feis, current_user, session)
    if not perms or not perms.get("can_add_organizers"):
        raise HTTPException(status_code=403, detail="You don't have permission to add organizers to this feis")
    
    user_to_add = session.get(User, UUID(organizer_data.user_id))
    if not user_to_add:
        raise HTTPException(status_code=404, detail="User not found")
    
    if feis.organizer_id == user_to_add.id:
        raise HTTPException(status_code=400, detail="User is already the primary organizer")
    
    existing = session.exec(
        select(FeisOrganizer).where(
            FeisOrganizer.feis_id == feis.id,
            FeisOrganizer.user_id == user_to_add.id
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a co-organizer for this feis")
    
    co_organizer = FeisOrganizer(
        feis_id=feis.id,
        user_id=user_to_add.id,
        role=organizer_data.role,
        can_edit_feis=organizer_data.can_edit_feis,
        can_manage_entries=organizer_data.can_manage_entries,
        can_manage_schedule=organizer_data.can_manage_schedule,
        can_manage_adjudicators=organizer_data.can_manage_adjudicators,
        can_add_organizers=organizer_data.can_add_organizers,
        added_by=current_user.id
    )
    session.add(co_organizer)
    session.commit()
    session.refresh(co_organizer)
    
    return FeisOrganizerResponse(
        id=str(co_organizer.id),
        feis_id=str(co_organizer.feis_id),
        user_id=str(co_organizer.user_id),
        user_name=user_to_add.name,
        user_email=user_to_add.email,
        role=co_organizer.role,
        can_edit_feis=co_organizer.can_edit_feis,
        can_manage_entries=co_organizer.can_manage_entries,
        can_manage_schedule=co_organizer.can_manage_schedule,
        can_manage_adjudicators=co_organizer.can_manage_adjudicators,
        can_add_organizers=co_organizer.can_add_organizers,
        added_by=str(co_organizer.added_by),
        added_by_name=current_user.name,
        added_at=co_organizer.added_at
    )


@router.put("/feis/{feis_id}/organizers/{organizer_id}", response_model=FeisOrganizerResponse)
async def update_feis_organizer(
    feis_id: str,
    organizer_id: str,
    organizer_data: FeisOrganizerUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a co-organizer's permissions. Requires permission to add organizers."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    perms = get_feis_organizer_permissions(feis, current_user, session)
    if not perms or not perms.get("can_add_organizers"):
        raise HTTPException(status_code=403, detail="You don't have permission to manage organizers for this feis")
    
    co_organizer = session.get(FeisOrganizer, UUID(organizer_id))
    if not co_organizer or co_organizer.feis_id != feis.id:
        raise HTTPException(status_code=404, detail="Co-organizer not found for this feis")
    
    if organizer_data.role is not None:
        co_organizer.role = organizer_data.role
    if organizer_data.can_edit_feis is not None:
        co_organizer.can_edit_feis = organizer_data.can_edit_feis
    if organizer_data.can_manage_entries is not None:
        co_organizer.can_manage_entries = organizer_data.can_manage_entries
    if organizer_data.can_manage_schedule is not None:
        co_organizer.can_manage_schedule = organizer_data.can_manage_schedule
    if organizer_data.can_manage_adjudicators is not None:
        co_organizer.can_manage_adjudicators = organizer_data.can_manage_adjudicators
    if organizer_data.can_add_organizers is not None:
        co_organizer.can_add_organizers = organizer_data.can_add_organizers
    
    session.add(co_organizer)
    session.commit()
    session.refresh(co_organizer)
    
    user = session.get(User, co_organizer.user_id)
    added_by_user = session.get(User, co_organizer.added_by)
    
    return FeisOrganizerResponse(
        id=str(co_organizer.id),
        feis_id=str(co_organizer.feis_id),
        user_id=str(co_organizer.user_id),
        user_name=user.name if user else "Unknown",
        user_email=user.email if user else "",
        role=co_organizer.role,
        can_edit_feis=co_organizer.can_edit_feis,
        can_manage_entries=co_organizer.can_manage_entries,
        can_manage_schedule=co_organizer.can_manage_schedule,
        can_manage_adjudicators=co_organizer.can_manage_adjudicators,
        can_add_organizers=co_organizer.can_add_organizers,
        added_by=str(co_organizer.added_by),
        added_by_name=added_by_user.name if added_by_user else "Unknown",
        added_at=co_organizer.added_at
    )


@router.delete("/feis/{feis_id}/organizers/{organizer_id}")
async def remove_feis_organizer(
    feis_id: str,
    organizer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Remove a co-organizer from a feis. Requires permission to add organizers."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    perms = get_feis_organizer_permissions(feis, current_user, session)
    if not perms or not perms.get("can_add_organizers"):
        raise HTTPException(status_code=403, detail="You don't have permission to manage organizers for this feis")
    
    co_organizer = session.get(FeisOrganizer, UUID(organizer_id))
    if not co_organizer or co_organizer.feis_id != feis.id:
        raise HTTPException(status_code=404, detail="Co-organizer not found for this feis")
    
    user = session.get(User, co_organizer.user_id)
    user_name = user.name if user else "Unknown"
    
    session.delete(co_organizer)
    session.commit()
    
    return {"message": f"Co-organizer '{user_name}' removed from feis"}


# ============= Feis Competitions and Stages =============

@router.get("/feis/{feis_id}/competitions", response_model=List[CompetitionResponse])
async def list_competitions(feis_id: str, session: Session = Depends(get_session)):
    """List all competitions for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    result = []
    for comp in competitions:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        result.append(CompetitionResponse(
            id=str(comp.id),
            feis_id=str(comp.feis_id),
            name=comp.name,
            min_age=comp.min_age,
            max_age=comp.max_age,
            level=comp.level,
            gender=comp.gender,
            code=comp.code,
            category=comp.category,
            is_mixed=comp.is_mixed,
            entry_count=entry_count,
            dance_type=comp.dance_type,
            tempo_bpm=comp.tempo_bpm,
            bars=comp.bars or 48,
            scoring_method=comp.scoring_method or ScoringMethod.SOLO,
            price_cents=comp.price_cents or 1000,
            max_entries=comp.max_entries,
            stage_id=str(comp.stage_id) if comp.stage_id else None,
            scheduled_time=comp.scheduled_time,
            estimated_duration_minutes=comp.estimated_duration_minutes,
            adjudicator_id=str(comp.adjudicator_id) if comp.adjudicator_id else None,
            description=comp.description,
            allowed_levels=comp.allowed_levels.split(',') if comp.allowed_levels else None
        ))
    
    return result


@router.delete("/feis/{feis_id}/competitions/empty")
async def delete_empty_competitions(
    feis_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete all competitions with zero entries for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage your own feis")
    
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    deleted_count = 0
    for comp in competitions:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        if entry_count == 0:
            session.delete(comp)
            deleted_count += 1
    
    session.commit()
    
    return {
        "deleted_count": deleted_count,
        "message": f"Deleted {deleted_count} empty competitions from {feis.name}"
    }


@router.get("/feis/{feis_id}/stages", response_model=List[StageResponse])
async def list_stages(feis_id: str, session: Session = Depends(get_session)):
    """List all stages for a feis, including judge coverage blocks."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    stages = session.exec(
        select(Stage)
        .where(Stage.feis_id == feis.id)
        .order_by(Stage.sequence)
    ).all()
    
    result = []
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
        
        result.append(StageResponse(
            id=str(stage.id),
            feis_id=str(stage.feis_id),
            name=stage.name,
            color=stage.color,
            sequence=stage.sequence,
            competition_count=comp_count,
            judge_coverage=coverage_responses
        ))
    
    return result


# ============= Feis Settings =============

@router.get("/feis/{feis_id}/settings", response_model=FeisSettingsResponse)
async def get_feis_settings(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get feis settings (pricing, registration windows, etc.)."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    
    if not settings:
        settings = FeisSettings(feis_id=feis.id)
    
    return FeisSettingsResponse(
        id=str(settings.id) if settings.id else "",
        feis_id=str(feis.id),
        base_entry_fee_cents=settings.base_entry_fee_cents,
        per_competition_fee_cents=settings.per_competition_fee_cents,
        family_max_cents=settings.family_max_cents,
        late_fee_cents=settings.late_fee_cents,
        late_fee_date=settings.late_fee_date,
        change_fee_cents=settings.change_fee_cents,
        registration_opens=settings.registration_opens,
        registration_closes=settings.registration_closes,
        stripe_account_id=settings.stripe_account_id,
        stripe_onboarding_complete=settings.stripe_onboarding_complete
    )


@router.put("/feis/{feis_id}/settings", response_model=FeisSettingsResponse)
async def update_feis_settings(
    feis_id: str,
    settings_data: FeisSettingsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update feis settings. Requires organizer (owner) or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update settings for your own feis")
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    
    if not settings:
        settings = FeisSettings(feis_id=feis.id)
        session.add(settings)
    
    if settings_data.base_entry_fee_cents is not None:
        settings.base_entry_fee_cents = settings_data.base_entry_fee_cents
    if settings_data.per_competition_fee_cents is not None:
        settings.per_competition_fee_cents = settings_data.per_competition_fee_cents
    if settings_data.family_max_cents is not None:
        settings.family_max_cents = None if settings_data.family_max_cents == -1 else settings_data.family_max_cents
    if settings_data.late_fee_cents is not None:
        settings.late_fee_cents = settings_data.late_fee_cents
    if settings_data.late_fee_date is not None:
        settings.late_fee_date = settings_data.late_fee_date
    if settings_data.change_fee_cents is not None:
        settings.change_fee_cents = settings_data.change_fee_cents
    if settings_data.registration_opens is not None:
        settings.registration_opens = settings_data.registration_opens
    if settings_data.registration_closes is not None:
        settings.registration_closes = settings_data.registration_closes
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return FeisSettingsResponse(
        id=str(settings.id),
        feis_id=str(feis.id),
        base_entry_fee_cents=settings.base_entry_fee_cents,
        per_competition_fee_cents=settings.per_competition_fee_cents,
        family_max_cents=settings.family_max_cents,
        late_fee_cents=settings.late_fee_cents,
        late_fee_date=settings.late_fee_date,
        change_fee_cents=settings.change_fee_cents,
        registration_opens=settings.registration_opens,
        registration_closes=settings.registration_closes,
        stripe_account_id=settings.stripe_account_id,
        stripe_onboarding_complete=settings.stripe_onboarding_complete
    )


# ============= Fee Items =============

@router.get("/feis/{feis_id}/fee-items", response_model=List[FeeItemResponse])
async def list_fee_items(
    feis_id: str,
    session: Session = Depends(get_session),
    active_only: bool = True
):
    """List fee items for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    statement = select(FeeItem).where(FeeItem.feis_id == feis.id)
    if active_only:
        statement = statement.where(FeeItem.active == True)
    
    items = session.exec(statement).all()
    
    return [
        FeeItemResponse(
            id=str(item.id),
            feis_id=str(item.feis_id),
            name=item.name,
            description=item.description,
            amount_cents=item.amount_cents,
            category=item.category,
            required=item.required,
            max_quantity=item.max_quantity,
            active=item.active
        )
        for item in items
    ]


@router.post("/feis/{feis_id}/fee-items", response_model=FeeItemResponse)
async def create_fee_item(
    feis_id: str,
    item_data: FeeItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create a fee item. Requires organizer (owner) or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only create fee items for your own feis")
    
    item = FeeItem(
        feis_id=feis.id,
        name=item_data.name,
        description=item_data.description,
        amount_cents=item_data.amount_cents,
        category=item_data.category,
        required=item_data.required,
        max_quantity=item_data.max_quantity
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return FeeItemResponse(
        id=str(item.id),
        feis_id=str(item.feis_id),
        name=item.name,
        description=item.description,
        amount_cents=item.amount_cents,
        category=item.category,
        required=item.required,
        max_quantity=item.max_quantity,
        active=item.active
    )


@router.put("/fee-items/{item_id}", response_model=FeeItemResponse)
async def update_fee_item(
    item_id: str,
    item_data: FeeItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a fee item."""
    item = session.get(FeeItem, UUID(item_id))
    if not item:
        raise HTTPException(status_code=404, detail="Fee item not found")
    
    feis = session.get(Feis, item.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update fee items for your own feis")
    
    if item_data.name is not None:
        item.name = item_data.name
    if item_data.description is not None:
        item.description = item_data.description
    if item_data.amount_cents is not None:
        item.amount_cents = item_data.amount_cents
    if item_data.category is not None:
        item.category = item_data.category
    if item_data.required is not None:
        item.required = item_data.required
    if item_data.max_quantity is not None:
        item.max_quantity = item_data.max_quantity
    if item_data.active is not None:
        item.active = item_data.active
    
    session.add(item)
    session.commit()
    session.refresh(item)
    
    return FeeItemResponse(
        id=str(item.id),
        feis_id=str(item.feis_id),
        name=item.name,
        description=item.description,
        amount_cents=item.amount_cents,
        category=item.category,
        required=item.required,
        max_quantity=item.max_quantity,
        active=item.active
    )


@router.delete("/fee-items/{item_id}")
async def delete_fee_item(
    item_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete (soft-delete by deactivating) a fee item."""
    item = session.get(FeeItem, UUID(item_id))
    if not item:
        raise HTTPException(status_code=404, detail="Fee item not found")
    
    feis = session.get(Feis, item.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete fee items for your own feis")
    
    item.active = False
    session.add(item)
    session.commit()
    
    return {"message": f"Fee item '{item.name}' deactivated"}


# ============= Registration Status =============

@router.get("/feis/{feis_id}/registration-status", response_model=RegistrationStatusResponse)
async def get_registration_status(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get registration status for a feis (open/closed, late fees, payment methods)."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    settings = get_cart_feis_settings(session, feis.id)
    is_open, message = is_registration_open(settings)
    is_late = is_late_registration(settings)
    
    stripe_connected, _ = is_organizer_connected(feis, session)
    stripe_enabled = is_stripe_configured() and stripe_connected
    
    payment_methods = ["pay_at_door"]
    if stripe_enabled:
        payment_methods.insert(0, "stripe")
    
    return RegistrationStatusResponse(
        is_open=is_open,
        message=message,
        opens_at=settings.registration_opens,
        closes_at=settings.registration_closes,
        is_late=is_late,
        late_fee_cents=settings.late_fee_cents if is_late else 0,
        stripe_enabled=stripe_enabled,
        payment_methods=payment_methods
    )


# ============= Stripe Integration =============

@router.get("/feis/{feis_id}/stripe-status", response_model=StripeStatusResponse)
async def get_stripe_status(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get Stripe configuration status for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    stripe_configured = is_stripe_configured()
    stripe_mode = get_stripe_mode()
    feis_connected, _ = is_organizer_connected(feis, session)
    
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    onboarding_complete = settings.stripe_onboarding_complete if settings else False
    
    if not stripe_configured:
        message = "Stripe is not configured. Online payments are disabled. Use 'Pay at Door' option."
    elif not feis_connected:
        message = "This feis has not connected a Stripe account yet."
    elif not onboarding_complete:
        message = "Stripe onboarding is in progress."
    else:
        message = f"Stripe is ready to accept payments ({stripe_mode} mode)."
    
    return StripeStatusResponse(
        stripe_configured=stripe_configured,
        stripe_mode=stripe_mode,
        feis_connected=feis_connected,
        onboarding_complete=onboarding_complete,
        message=message
    )


@router.post("/feis/{feis_id}/stripe-onboarding", response_model=StripeOnboardingResponse)
async def start_stripe_onboarding(
    feis_id: str,
    onboarding_data: StripeOnboardingRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Start Stripe Connect onboarding for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only configure Stripe for your own feis")
    
    result = create_organizer_onboarding_link(
        session=session,
        feis_id=feis.id,
        return_url=onboarding_data.return_url,
        refresh_url=onboarding_data.refresh_url
    )
    
    return StripeOnboardingResponse(
        success=result.success,
        onboarding_url=result.onboarding_url,
        is_test_mode=result.is_test_mode,
        error=result.error
    )


@router.post("/feis/{feis_id}/stripe-onboarding/complete")
async def complete_stripe_onboarding(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Check and mark Stripe onboarding as complete.
    
    Called after returning from Stripe onboarding flow.
    In test mode, this immediately marks onboarding as complete.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only configure Stripe for your own feis")
    
    if not is_stripe_configured():
        settings = session.exec(
            select(FeisSettings).where(FeisSettings.feis_id == feis.id)
        ).first()
        
        if not settings:
            settings = FeisSettings(feis_id=feis.id)
        
        settings.stripe_account_id = f"test_acct_{feis.id}"
        settings.stripe_onboarding_complete = True
        session.add(settings)
        session.commit()
        
        return {
            "success": True,
            "message": "Test mode: Stripe onboarding marked as complete",
            "is_test_mode": True
        }
    
    is_complete, message = check_onboarding_status(session, feis.id)
    
    return {
        "success": is_complete,
        "message": message,
        "is_test_mode": False
    }
