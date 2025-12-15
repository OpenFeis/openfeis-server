"""
Adjudicators Router - Individual adjudicator management, availability, invites, and PIN access.

Routes:
- GET/PUT/DELETE /adjudicators/{adjudicator_id} - Individual adjudicator CRUD
- GET/POST /adjudicators/{adjudicator_id}/availability - Availability management
- POST /adjudicators/{adjudicator_id}/availability/bulk - Bulk availability
- PUT/DELETE /adjudicator-availability/{block_id} - Availability block operations
- POST /adjudicators/{adjudicator_id}/invite - Send invite
- POST /adjudicator-invite/accept - Accept invite
- POST /adjudicators/{adjudicator_id}/generate-pin - Generate day-of PIN
- POST /adjudicator-login/pin - PIN login
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlmodel import Session, select
from backend.db.database import get_session
from backend.api.auth import (
    get_current_user, get_optional_user, require_organizer_or_admin,
    hash_password, verify_password, create_access_token
)
from backend.scoring_engine.models_platform import (
    User, Feis, Competition, RoleType,
    FeisAdjudicator, AdjudicatorAvailability, AdjudicatorStatus
)
from backend.api.schemas import (
    AdjudicatorUpdate, AdjudicatorResponse,
    AvailabilityBlockCreate, AvailabilityBlockUpdate, AvailabilityBlockResponse,
    AdjudicatorAvailabilityResponse, BulkAvailabilityCreate,
    AdjudicatorInviteRequest, AdjudicatorInviteResponse,
    AdjudicatorAcceptInviteRequest, AdjudicatorAcceptInviteResponse,
    GeneratePinResponse, PinLoginRequest, PinLoginResponse,
    UserResponse
)
from backend.services.email import get_site_settings
import secrets
import random

router = APIRouter()


# ============= Adjudicator CRUD =============

@router.get("/adjudicators/{adjudicator_id}", response_model=AdjudicatorResponse)
async def get_adjudicator(
    adjudicator_id: str,
    session: Session = Depends(get_session)
):
    """Get a specific adjudicator by ID."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
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


@router.put("/adjudicators/{adjudicator_id}", response_model=AdjudicatorResponse)
async def update_adjudicator(
    adjudicator_id: str,
    update_data: AdjudicatorUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update an adjudicator's details. Requires organizer or admin role."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can update adjudicators")
    
    if update_data.name is not None:
        adjudicator.name = update_data.name
    if update_data.email is not None:
        adjudicator.email = update_data.email
    if update_data.phone is not None:
        adjudicator.phone = update_data.phone
    if update_data.credential is not None:
        adjudicator.credential = update_data.credential
    if update_data.organization is not None:
        adjudicator.organization = update_data.organization
    if update_data.school_affiliation_id is not None:
        adjudicator.school_affiliation_id = UUID(update_data.school_affiliation_id) if update_data.school_affiliation_id else None
    if update_data.status is not None:
        adjudicator.status = update_data.status
        if update_data.status == AdjudicatorStatus.CONFIRMED and not adjudicator.confirmed_at:
            adjudicator.confirmed_at = datetime.utcnow()
    if update_data.user_id is not None:
        adjudicator.user_id = UUID(update_data.user_id) if update_data.user_id else None
    
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


@router.delete("/adjudicators/{adjudicator_id}")
async def delete_adjudicator(
    adjudicator_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Remove an adjudicator from the feis roster. Requires organizer or admin role."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can remove adjudicators")
    
    assigned_comps = session.exec(
        select(Competition).where(Competition.adjudicator_id == adjudicator.user_id)
    ).all() if adjudicator.user_id else []
    
    if assigned_comps:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot remove adjudicator who is assigned to {len(assigned_comps)} competition(s). Unassign them first."
        )
    
    for block in session.exec(select(AdjudicatorAvailability).where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))).all():
        session.delete(block)
    
    session.delete(adjudicator)
    session.commit()
    
    return {"message": "Adjudicator removed from roster", "adjudicator_id": adjudicator_id}


# ============= Adjudicator Availability =============

@router.get("/adjudicators/{adjudicator_id}/availability", response_model=AdjudicatorAvailabilityResponse)
async def get_adjudicator_availability(
    adjudicator_id: str,
    session: Session = Depends(get_session)
):
    """Get all availability blocks for an adjudicator."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    
    blocks = session.exec(
        select(AdjudicatorAvailability)
        .where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))
        .order_by(AdjudicatorAvailability.feis_day, AdjudicatorAvailability.start_time)
    ).all()
    
    feis_dates = [feis.date]
    
    block_responses = [
        AvailabilityBlockResponse(
            id=str(block.id),
            feis_adjudicator_id=str(block.feis_adjudicator_id),
            feis_day=block.feis_day,
            start_time=block.start_time,
            end_time=block.end_time,
            availability_type=block.availability_type,
            note=block.note,
            created_at=block.created_at
        )
        for block in blocks
    ]
    
    return AdjudicatorAvailabilityResponse(
        adjudicator_id=adjudicator_id,
        adjudicator_name=adjudicator.name,
        feis_id=str(adjudicator.feis_id),
        feis_dates=feis_dates,
        availability_blocks=block_responses
    )


@router.post("/adjudicators/{adjudicator_id}/availability", response_model=AvailabilityBlockResponse)
async def create_availability_block(
    adjudicator_id: str,
    block_data: AvailabilityBlockCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create an availability block for an adjudicator. Requires organizer or admin role."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    if block_data.start_time >= block_data.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    block = AdjudicatorAvailability(
        feis_adjudicator_id=UUID(adjudicator_id),
        feis_day=block_data.feis_day,
        start_time=block_data.start_time,
        end_time=block_data.end_time,
        availability_type=block_data.availability_type,
        note=block_data.note
    )
    
    session.add(block)
    session.commit()
    session.refresh(block)
    
    return AvailabilityBlockResponse(
        id=str(block.id),
        feis_adjudicator_id=str(block.feis_adjudicator_id),
        feis_day=block.feis_day,
        start_time=block.start_time,
        end_time=block.end_time,
        availability_type=block.availability_type,
        note=block.note,
        created_at=block.created_at
    )


@router.post("/adjudicators/{adjudicator_id}/availability/bulk", response_model=List[AvailabilityBlockResponse])
async def create_bulk_availability(
    adjudicator_id: str,
    bulk_data: BulkAvailabilityCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create multiple availability blocks at once. Requires organizer or admin role."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    if bulk_data.replace_existing:
        days_to_replace = set(block.feis_day for block in bulk_data.blocks)
        for day in days_to_replace:
            existing = session.exec(
                select(AdjudicatorAvailability)
                .where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))
                .where(AdjudicatorAvailability.feis_day == day)
            ).all()
            for existing_block in existing:
                session.delete(existing_block)
    
    created_blocks = []
    for block_data in bulk_data.blocks:
        if block_data.start_time >= block_data.end_time:
            raise HTTPException(status_code=400, detail=f"End time must be after start time for day {block_data.feis_day}")
        
        block = AdjudicatorAvailability(
            feis_adjudicator_id=UUID(adjudicator_id),
            feis_day=block_data.feis_day,
            start_time=block_data.start_time,
            end_time=block_data.end_time,
            availability_type=block_data.availability_type,
            note=block_data.note
        )
        session.add(block)
        created_blocks.append(block)
    
    session.commit()
    
    responses = []
    for block in created_blocks:
        session.refresh(block)
        responses.append(AvailabilityBlockResponse(
            id=str(block.id),
            feis_adjudicator_id=str(block.feis_adjudicator_id),
            feis_day=block.feis_day,
            start_time=block.start_time,
            end_time=block.end_time,
            availability_type=block.availability_type,
            note=block.note,
            created_at=block.created_at
        ))
    
    return responses


@router.put("/adjudicator-availability/{block_id}", response_model=AvailabilityBlockResponse)
async def update_availability_block(
    block_id: str,
    update_data: AvailabilityBlockUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update an availability block. Requires organizer or admin role."""
    block = session.get(AdjudicatorAvailability, UUID(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Availability block not found")
    
    adjudicator = session.get(FeisAdjudicator, block.feis_adjudicator_id)
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    if update_data.feis_day is not None:
        block.feis_day = update_data.feis_day
    if update_data.start_time is not None:
        block.start_time = update_data.start_time
    if update_data.end_time is not None:
        block.end_time = update_data.end_time
    if update_data.availability_type is not None:
        block.availability_type = update_data.availability_type
    if update_data.note is not None:
        block.note = update_data.note
    
    if block.start_time >= block.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    session.add(block)
    session.commit()
    session.refresh(block)
    
    return AvailabilityBlockResponse(
        id=str(block.id),
        feis_adjudicator_id=str(block.feis_adjudicator_id),
        feis_day=block.feis_day,
        start_time=block.start_time,
        end_time=block.end_time,
        availability_type=block.availability_type,
        note=block.note,
        created_at=block.created_at
    )


@router.delete("/adjudicator-availability/{block_id}")
async def delete_availability_block(
    block_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Delete an availability block. Requires organizer or admin role."""
    block = session.get(AdjudicatorAvailability, UUID(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Availability block not found")
    
    adjudicator = session.get(FeisAdjudicator, block.feis_adjudicator_id)
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    session.delete(block)
    session.commit()
    
    return {"message": "Availability block deleted", "block_id": block_id}


# ============= Adjudicator Invite Flow =============

@router.post("/adjudicators/{adjudicator_id}/invite", response_model=AdjudicatorInviteResponse)
async def send_adjudicator_invite(
    adjudicator_id: str,
    request: AdjudicatorInviteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Send or resend an invitation to an adjudicator. Requires organizer or admin role."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can send invites")
    
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    adjudicator.invite_token = invite_token
    adjudicator.invite_sent_at = datetime.utcnow()
    adjudicator.invite_expires_at = expires_at
    adjudicator.status = AdjudicatorStatus.INVITED
    
    session.add(adjudicator)
    session.commit()
    session.refresh(adjudicator)
    
    settings = get_site_settings(session)
    site_url = settings.site_url if settings else "http://localhost:5173"
    invite_link = f"{site_url}/adjudicator-invite?token={invite_token}"
    
    return AdjudicatorInviteResponse(
        success=True,
        adjudicator_id=adjudicator_id,
        invite_link=invite_link,
        expires_at=expires_at,
        message=f"Invite generated for {adjudicator.name}. Share the link with them to accept."
    )


@router.post("/adjudicator-invite/accept", response_model=AdjudicatorAcceptInviteResponse)
async def accept_adjudicator_invite(
    request: AdjudicatorAcceptInviteRequest,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Accept an adjudicator invitation via magic link."""
    adjudicator = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.invite_token == request.token)
    ).first()
    
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")
    
    if adjudicator.invite_expires_at and adjudicator.invite_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite token has expired. Please request a new invite.")
    
    feis = session.get(Feis, adjudicator.feis_id)
    
    if current_user:
        adjudicator.user_id = current_user.id
        adjudicator.status = AdjudicatorStatus.CONFIRMED
        adjudicator.confirmed_at = datetime.utcnow()
        adjudicator.invite_token = None
        
        if current_user.role == RoleType.PARENT:
            current_user.role = RoleType.ADJUDICATOR
            session.add(current_user)
        
        session.add(adjudicator)
        session.commit()
        session.refresh(adjudicator)
        
        return AdjudicatorAcceptInviteResponse(
            success=True,
            feis_id=str(feis.id),
            feis_name=feis.name,
            adjudicator_name=adjudicator.name,
            message=f"Successfully confirmed as adjudicator for {feis.name}",
            access_token=None,
            user=UserResponse(
                id=str(current_user.id),
                email=current_user.email,
                name=current_user.name,
                role=current_user.role,
                email_verified=current_user.email_verified
            )
        )
    else:
        return AdjudicatorAcceptInviteResponse(
            success=True,
            feis_id=str(feis.id),
            feis_name=feis.name,
            adjudicator_name=adjudicator.name,
            message="Please log in or create an account to confirm your position as adjudicator",
            access_token=None,
            user=None
        )


# ============= Day-of PIN Access =============

@router.post("/adjudicators/{adjudicator_id}/generate-pin", response_model=GeneratePinResponse)
async def generate_adjudicator_pin(
    adjudicator_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Generate a 6-digit PIN for day-of access. The PIN is only shown once."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can generate PINs")
    
    pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    adjudicator.access_pin_hash = hash_password(pin)
    adjudicator.pin_generated_at = datetime.utcnow()
    
    session.add(adjudicator)
    session.commit()
    
    return GeneratePinResponse(
        success=True,
        adjudicator_id=adjudicator_id,
        adjudicator_name=adjudicator.name,
        pin=pin,
        message=f"PIN generated for {adjudicator.name}. Write it down - it cannot be shown again."
    )


@router.post("/adjudicator-login/pin", response_model=PinLoginResponse)
async def login_with_pin(
    request: PinLoginRequest,
    session: Session = Depends(get_session)
):
    """Login as an adjudicator using a day-of PIN."""
    adjudicators = session.exec(
        select(FeisAdjudicator)
        .where(FeisAdjudicator.feis_id == UUID(request.feis_id))
        .where(FeisAdjudicator.access_pin_hash.isnot(None))
    ).all()
    
    matched_adjudicator = None
    for adj in adjudicators:
        if verify_password(request.pin, adj.access_pin_hash):
            matched_adjudicator = adj
            break
    
    if not matched_adjudicator:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    feis = session.get(Feis, UUID(request.feis_id))
    
    matched_adjudicator.status = AdjudicatorStatus.ACTIVE
    session.add(matched_adjudicator)
    
    if matched_adjudicator.user_id:
        user = session.get(User, matched_adjudicator.user_id)
        access_token = create_access_token(user.id, user.role)
    else:
        if matched_adjudicator.email:
            existing_user = session.exec(
                select(User).where(User.email == matched_adjudicator.email)
            ).first()
            if existing_user:
                matched_adjudicator.user_id = existing_user.id
                session.add(matched_adjudicator)
                access_token = create_access_token(existing_user.id, existing_user.role)
            else:
                temp_user = User(
                    email=matched_adjudicator.email or f"adj_{matched_adjudicator.id}@temp.openfeis.local",
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    name=matched_adjudicator.name,
                    role=RoleType.ADJUDICATOR,
                    email_verified=True
                )
                session.add(temp_user)
                session.commit()
                session.refresh(temp_user)
                matched_adjudicator.user_id = temp_user.id
                session.add(matched_adjudicator)
                access_token = create_access_token(temp_user.id, temp_user.role)
        else:
            temp_user = User(
                email=f"adj_{matched_adjudicator.id}@pin.openfeis.local",
                password_hash=hash_password(secrets.token_urlsafe(32)),
                name=matched_adjudicator.name,
                role=RoleType.ADJUDICATOR,
                email_verified=True
            )
            session.add(temp_user)
            session.commit()
            session.refresh(temp_user)
            matched_adjudicator.user_id = temp_user.id
            session.add(matched_adjudicator)
            access_token = create_access_token(temp_user.id, temp_user.role)
    
    session.commit()
    
    return PinLoginResponse(
        success=True,
        access_token=access_token,
        feis_id=request.feis_id,
        feis_name=feis.name,
        adjudicator_name=matched_adjudicator.name,
        message=f"Welcome, {matched_adjudicator.name}! You can now score competitions."
    )
