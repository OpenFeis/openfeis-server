from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Session, select, func
from backend.scoring_engine.models import JudgeScore, RoundResult, Round
from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry, CompetitionLevel, RoleType, SiteSettings
from backend.scoring_engine.calculator import IrishPointsCalculator
from backend.db.database import get_session
from backend.api.schemas import (
    SyllabusGenerationRequest, SyllabusGenerationResponse,
    FeisCreate, FeisUpdate, FeisResponse,
    CompetitionCreate, CompetitionUpdate, CompetitionResponse,
    EntryCreate, BulkEntryCreate, BulkEntryResponse,
    EntryUpdate, EntryResponse, BulkNumberAssignment, BulkNumberAssignmentResponse,
    DancerCreate, DancerUpdate, DancerResponse, UserUpdate, UserResponse,
    ProfileUpdate, PasswordChangeRequest,
    LoginRequest, RegisterRequest, AuthResponse,
    VerifyEmailRequest, ResendVerificationRequest, VerificationResponse,
    SiteSettingsUpdate, SiteSettingsResponse,
    CompetitorForScoring, CompetitionForScoring, ScoreSubmission, ScoreSubmissionResponse,
    TabulatorResultItem, TabulatorResults, CompetitionWithScores
)
from backend.api.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_optional_user, require_role,
    require_admin, require_organizer_or_admin, require_adjudicator
)
from backend.services.number_cards import (
    NumberCardData,
    generate_number_cards_pdf,
    generate_single_card_pdf
)
from backend.services.email import (
    send_verification_email,
    verify_email_token,
    can_resend_verification,
    get_site_settings,
    is_email_configured
)
from backend.api.websocket import manager as ws_manager
import asyncio

router = APIRouter()
calculator = IrishPointsCalculator()

# ============= Authentication Endpoints =============

@router.post("/auth/login", response_model=AuthResponse)
async def login(
    credentials: LoginRequest,
    session: Session = Depends(get_session)
):
    """
    Authenticate user and return JWT token.
    """
    # Find user by email
    statement = select(User).where(User.email == credentials.email)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(user.id, user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        )
    )

@router.post("/auth/login/form", response_model=AuthResponse)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """
    OAuth2 compatible login endpoint (for Swagger UI).
    Uses form data instead of JSON body.
    """
    # Find user by email (username field in OAuth2)
    statement = select(User).where(User.email == form_data.username)
    user = session.exec(statement).first()
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )
    
    # Create access token
    access_token = create_access_token(user.id, user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        )
    )

@router.post("/auth/register", response_model=AuthResponse)
async def register(
    registration: RegisterRequest,
    session: Session = Depends(get_session)
):
    """
    Register a new user account. Default role is 'parent'.
    Auto-logs in the user after registration.
    Sends verification email if email is configured.
    """
    # Check if email already exists
    statement = select(User).where(User.email == registration.email)
    existing_user = session.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user with hashed password
    user = User(
        email=registration.email,
        password_hash=hash_password(registration.password),
        name=registration.name,
        role=RoleType.PARENT,  # Default role
        email_verified=False
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Send verification email (will be skipped if not configured)
    send_verification_email(session, user)
    
    # Create access token for auto-login
    access_token = create_access_token(user.id, user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        )
    )

@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current authenticated user's information.
    """
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        email_verified=current_user.email_verified
    )


# ============= Email Verification Endpoints =============

@router.post("/auth/verify-email", response_model=VerificationResponse)
async def verify_email(
    request: VerifyEmailRequest,
    session: Session = Depends(get_session)
):
    """
    Verify a user's email address using the token from the verification email.
    """
    user = verify_email_token(session, request.token)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    return VerificationResponse(
        success=True,
        message="Email verified successfully! You can now access all features."
    )


@router.post("/auth/resend-verification", response_model=VerificationResponse)
async def resend_verification(
    request: ResendVerificationRequest,
    session: Session = Depends(get_session)
):
    """
    Resend the verification email. Rate limited to once per 60 seconds.
    """
    # Check if email is configured
    if not is_email_configured(session):
        raise HTTPException(
            status_code=503,
            detail="Email service is not configured. Please contact the administrator."
        )
    
    # Find user by email
    statement = select(User).where(User.email == request.email)
    user = session.exec(statement).first()
    
    if not user:
        # Don't reveal whether email exists
        return VerificationResponse(
            success=True,
            message="If an account exists with this email, a verification link has been sent."
        )
    
    if user.email_verified:
        return VerificationResponse(
            success=True,
            message="This email is already verified."
        )
    
    # Check rate limiting
    if not can_resend_verification(user):
        raise HTTPException(
            status_code=429,
            detail="Please wait at least 60 seconds before requesting another verification email."
        )
    
    # Send verification email
    sent = send_verification_email(session, user)
    
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification email. Please try again later."
        )
    
    return VerificationResponse(
        success=True,
        message="Verification email sent! Please check your inbox."
    )


@router.get("/auth/email-status")
async def get_email_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's email verification status and whether email is configured.
    """
    return {
        "email_verified": current_user.email_verified,
        "email_configured": is_email_configured(session)
    }

# ============= Scoring Endpoints =============

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

@router.get("/results/{round_id}", response_model=RoundResult)
async def get_round_results(round_id: str, session: Session = Depends(get_session)):
    statement = select(JudgeScore).where(JudgeScore.round_id == round_id)
    round_scores = session.exec(statement).all()
    return calculator.calculate_round(round_id, list(round_scores))


# ============= Judge Pad Endpoints =============

@router.get("/judge/competitions", response_model=List[CompetitionForScoring])
async def get_competitions_for_scoring(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    Get all competitions available for scoring.
    Only shows competitions that have entries with assigned competitor numbers.
    """
    # Get all feiseanna
    feiseanna = session.exec(select(Feis)).all()
    feis_map = {f.id: f for f in feiseanna}
    
    # Get all competitions
    competitions = session.exec(select(Competition)).all()
    
    result = []
    for comp in competitions:
        # Count entries with assigned numbers (ready for scoring)
        entry_count = session.exec(
            select(func.count(Entry.id))
            .where(Entry.competition_id == comp.id)
            .where(Entry.competitor_number.isnot(None))
        ).one()
        
        # Only include competitions with scorable entries
        if entry_count > 0:
            feis = feis_map.get(comp.feis_id)
            result.append(CompetitionForScoring(
                id=str(comp.id),
                name=comp.name,
                feis_id=str(comp.feis_id),
                feis_name=feis.name if feis else "Unknown",
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
    """
    Get all competitors in a competition ready to be scored.
    Returns entries with assigned competitor numbers, along with any existing scores
    from this judge.
    """
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
    
    result = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        if not dancer:
            continue
        
        # Check for existing score from this judge
        # Using competition_id as round_id for simplicity
        existing_score = session.exec(
            select(JudgeScore)
            .where(JudgeScore.judge_id == str(current_user.id))
            .where(JudgeScore.competitor_id == str(entry.id))
            .where(JudgeScore.round_id == str(competition.id))
        ).first()
        
        # Get school name if available
        school_name = None
        if dancer.school_id:
            teacher = session.get(User, dancer.school_id)
            school_name = teacher.name if teacher else None
        
        result.append(CompetitorForScoring(
            entry_id=str(entry.id),
            competitor_number=entry.competitor_number,
            dancer_name=dancer.name,
            dancer_school=school_name,
            existing_score=existing_score.value if existing_score else None,
            existing_notes=existing_score.notes if existing_score else None
        ))
    
    return result


@router.post("/judge/scores", response_model=ScoreSubmissionResponse)
async def submit_judge_score(
    score_data: ScoreSubmission,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_adjudicator())
):
    """
    Submit or update a score for a competitor.
    If the judge has already scored this competitor in this competition,
    the existing score is updated.
    
    Broadcasts the score to all WebSocket clients watching this competition.
    """
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
    
    # Check for existing score from this judge
    existing_score = session.exec(
        select(JudgeScore)
        .where(JudgeScore.judge_id == str(current_user.id))
        .where(JudgeScore.competitor_id == str(entry.id))
        .where(JudgeScore.round_id == str(competition.id))
    ).first()
    
    from datetime import datetime
    
    if existing_score:
        # Update existing score
        existing_score.value = score_data.value
        existing_score.notes = score_data.notes
        existing_score.timestamp = datetime.utcnow()
        session.add(existing_score)
        session.commit()
        session.refresh(existing_score)
        
        response = ScoreSubmissionResponse(
            id=str(existing_score.id),
            entry_id=score_data.entry_id,
            competition_id=score_data.competition_id,
            value=existing_score.value,
            notes=existing_score.notes,
            timestamp=existing_score.timestamp.isoformat()
        )
    else:
        # Create new score
        new_score = JudgeScore(
            judge_id=str(current_user.id),
            competitor_id=str(entry.id),
            round_id=str(competition.id),  # Using competition_id as round_id
            value=score_data.value,
            notes=score_data.notes
        )
        session.add(new_score)
        session.commit()
        session.refresh(new_score)
        
        response = ScoreSubmissionResponse(
            id=str(new_score.id),
            entry_id=score_data.entry_id,
            competition_id=score_data.competition_id,
            value=new_score.value,
            notes=new_score.notes,
            timestamp=new_score.timestamp.isoformat()
        )
    
    # Broadcast score to WebSocket clients (fire and forget)
    asyncio.create_task(ws_manager.broadcast_score({
        "competition_id": score_data.competition_id,
        "entry_id": score_data.entry_id,
        "judge_id": str(current_user.id),
        "value": score_data.value,
        "timestamp": response.timestamp
    }))
    
    return response


# ============= Feis CRUD Endpoints =============

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
        # Count competitions and entries
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
    # Use current user as organizer if not provided
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
    """Update a feis. Requires organizer (owner) or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own feis")
    
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
    """Delete a feis and all its competitions/entries. Requires organizer (owner) or super_admin role."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own feis")
    
    # Delete all entries for competitions in this feis
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
    
    session.delete(feis)
    session.commit()
    
    return {"message": f"Feis '{feis.name}' and all associated data deleted"}

# ============= Competition Endpoints =============

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
            entry_count=entry_count
        ))
    
    return result

@router.post("/competitions", response_model=CompetitionResponse)
async def create_competition(comp_data: CompetitionCreate, session: Session = Depends(get_session)):
    """Create a single competition."""
    feis = session.get(Feis, UUID(comp_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    comp = Competition(
        feis_id=feis.id,
        name=comp_data.name,
        min_age=comp_data.min_age,
        max_age=comp_data.max_age,
        level=comp_data.level,
        gender=comp_data.gender
    )
    session.add(comp)
    session.commit()
    session.refresh(comp)
    
    return CompetitionResponse(
        id=str(comp.id),
        feis_id=str(comp.feis_id),
        name=comp.name,
        min_age=comp.min_age,
        max_age=comp.max_age,
        level=comp.level,
        gender=comp.gender,
        entry_count=0
    )

@router.put("/competitions/{comp_id}", response_model=CompetitionResponse)
async def update_competition(comp_id: str, comp_data: CompetitionUpdate, session: Session = Depends(get_session)):
    """Update a competition."""
    comp = session.get(Competition, UUID(comp_id))
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    if comp_data.name is not None:
        comp.name = comp_data.name
    if comp_data.min_age is not None:
        comp.min_age = comp_data.min_age
    if comp_data.max_age is not None:
        comp.max_age = comp_data.max_age
    if comp_data.level is not None:
        comp.level = comp_data.level
    if comp_data.gender is not None:
        comp.gender = comp_data.gender
    
    session.add(comp)
    session.commit()
    session.refresh(comp)
    
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
    ).one()
    
    return CompetitionResponse(
        id=str(comp.id),
        feis_id=str(comp.feis_id),
        name=comp.name,
        min_age=comp.min_age,
        max_age=comp.max_age,
        level=comp.level,
        gender=comp.gender,
        entry_count=entry_count
    )

@router.delete("/competitions/{comp_id}")
async def delete_competition(comp_id: str, session: Session = Depends(get_session)):
    """Delete a competition and its entries."""
    comp = session.get(Competition, UUID(comp_id))
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Delete all entries first
    entries = session.exec(
        select(Entry).where(Entry.competition_id == comp.id)
    ).all()
    for entry in entries:
        session.delete(entry)
    
    session.delete(comp)
    session.commit()
    
    return {"message": f"Competition '{comp.name}' deleted"}


@router.delete("/feis/{feis_id}/competitions/empty")
async def delete_empty_competitions(
    feis_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Delete all competitions with zero entries for a feis.
    This is more reliable than deleting one-by-one from the frontend.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only manage your own feis")
    
    # Get all competitions for this feis
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    deleted_count = 0
    for comp in competitions:
        # Check if competition has any entries
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

# ============= Syllabus Generation =============

@router.post("/admin/syllabus/generate", response_model=SyllabusGenerationResponse)
async def generate_syllabus(
    request: SyllabusGenerationRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Auto-generate syllabus competitions. Requires organizer or super_admin role."""
    feis = session.get(Feis, UUID(request.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only generate syllabus for your own feis")
    
    count = 0
    current_age = request.min_age
    
    while current_age <= request.max_age:
        age_group = f"U{current_age}"
        
        for gender in request.genders:
            for level in request.levels:
                for dance in request.dances:
                    comp_name = f"{gender.value.title()} {age_group} {dance} ({level.value.title()})"
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=current_age - 2,
                        max_age=current_age,
                        level=level,
                        gender=gender
                    )
                    session.add(comp)
                    count += 1
        
        current_age += 2
    
    session.commit()
    
    return SyllabusGenerationResponse(
        generated_count=count,
        message=f"Successfully created {count} competitions for {feis.name}."
    )

# ============= Entry Management Endpoints =============

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
    
    # Get all competitions for this feis
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in competitions]
    comp_map = {c.id: c for c in competitions}
    
    if not comp_ids:
        return []
    
    # Build entry query
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
                dancer_school=None,  # TODO: Add school lookup
                competition_id=str(entry.competition_id),
                competition_name=comp.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result

@router.put("/entries/{entry_id}", response_model=EntryResponse)
async def update_entry(entry_id: str, entry_data: EntryUpdate, session: Session = Depends(get_session)):
    """Update an entry (assign number, mark paid)."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry_data.competitor_number is not None:
        entry.competitor_number = entry_data.competitor_number
    if entry_data.paid is not None:
        entry.paid = entry_data.paid
    
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    dancer = session.get(Dancer, entry.dancer_id)
    comp = session.get(Competition, entry.competition_id)
    
    return EntryResponse(
        id=str(entry.id),
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name if dancer else "Unknown",
        dancer_school=None,
        competition_id=str(entry.competition_id),
        competition_name=comp.name if comp else "Unknown",
        competitor_number=entry.competitor_number,
        paid=entry.paid,
        pay_later=entry.pay_later
    )

@router.post("/feis/{feis_id}/assign-numbers", response_model=BulkNumberAssignmentResponse)
async def bulk_assign_numbers(feis_id: str, data: BulkNumberAssignment, session: Session = Depends(get_session)):
    """Bulk assign competitor numbers to all entries without numbers."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all competitions for this feis
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in competitions]
    
    if not comp_ids:
        return BulkNumberAssignmentResponse(assigned_count=0, message="No competitions found")
    
    # Get unique dancers who have entries without numbers
    entries = session.exec(
        select(Entry)
        .where(Entry.competition_id.in_(comp_ids))
        .where(Entry.competitor_number.is_(None))
    ).all()
    
    # Group by dancer to assign one number per dancer
    dancer_ids = list(set(e.dancer_id for e in entries))
    
    current_number = data.start_number
    dancer_numbers = {}
    
    for dancer_id in dancer_ids:
        dancer_numbers[dancer_id] = current_number
        current_number += 1
    
    # Update entries
    for entry in entries:
        entry.competitor_number = dancer_numbers[entry.dancer_id]
        session.add(entry)
    
    session.commit()
    
    return BulkNumberAssignmentResponse(
        assigned_count=len(dancer_ids),
        message=f"Assigned numbers {data.start_number} to {current_number - 1} to {len(dancer_ids)} dancers"
    )


# ============= Entry Creation Endpoints =============

@router.post("/entries", response_model=EntryResponse)
async def create_entry(
    entry_data: EntryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a single entry (register a dancer for a competition).
    
    Parents can only create entries for their own dancers.
    The pay_later option allows "Pay at Door" registration.
    """
    # Validate dancer exists and belongs to current user (if parent)
    dancer = session.get(Dancer, UUID(entry_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only register their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    # Validate competition exists
    competition = session.get(Competition, UUID(entry_data.competition_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    # Check if entry already exists
    existing = session.exec(
        select(Entry)
        .where(Entry.dancer_id == dancer.id)
        .where(Entry.competition_id == competition.id)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Dancer is already registered for this competition")
    
    # Create entry
    entry = Entry(
        dancer_id=dancer.id,
        competition_id=competition.id,
        paid=False,  # Will be set to True after payment (or by admin)
        pay_later=entry_data.pay_later
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    
    return EntryResponse(
        id=str(entry.id),
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name,
        dancer_school=None,
        competition_id=str(entry.competition_id),
        competition_name=competition.name,
        competitor_number=entry.competitor_number,
        paid=entry.paid,
        pay_later=entry.pay_later
    )


@router.post("/entries/batch", response_model=BulkEntryResponse)
async def create_entries_batch(
    entry_data: BulkEntryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create multiple entries at once (registration checkout).
    
    This is the main endpoint for completing a registration.
    Parents can only create entries for their own dancers.
    The pay_later option allows "Pay at Door" registration.
    """
    # Validate dancer exists and belongs to current user (if parent)
    dancer = session.get(Dancer, UUID(entry_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only register their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    created_entries = []
    skipped_count = 0
    
    for comp_id in entry_data.competition_ids:
        # Validate competition exists
        competition = session.get(Competition, UUID(comp_id))
        if not competition:
            continue  # Skip invalid competition IDs
        
        # Check if entry already exists
        existing = session.exec(
            select(Entry)
            .where(Entry.dancer_id == dancer.id)
            .where(Entry.competition_id == competition.id)
        ).first()
        
        if existing:
            skipped_count += 1
            continue  # Skip duplicates
        
        # Create entry
        entry = Entry(
            dancer_id=dancer.id,
            competition_id=competition.id,
            paid=False,
            pay_later=entry_data.pay_later
        )
        session.add(entry)
        session.flush()  # Get the ID without committing
        
        created_entries.append(EntryResponse(
            id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name,
            dancer_school=None,
            competition_id=str(entry.competition_id),
            competition_name=competition.name,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            pay_later=entry.pay_later
        ))
    
    session.commit()
    
    message = f"Successfully registered {dancer.name} for {len(created_entries)} competition(s)"
    if skipped_count > 0:
        message += f" ({skipped_count} already registered)"
    if entry_data.pay_later:
        message += ". Payment to be collected at check-in."
    
    return BulkEntryResponse(
        created_count=len(created_entries),
        entries=created_entries,
        message=message
    )


@router.get("/entries", response_model=List[EntryResponse])
async def list_all_entries(
    session: Session = Depends(get_session),
    dancer_id: Optional[str] = None,
    competition_id: Optional[str] = None,
    paid: Optional[bool] = None
):
    """List all entries with optional filters."""
    statement = select(Entry)
    
    if dancer_id:
        statement = statement.where(Entry.dancer_id == UUID(dancer_id))
    if competition_id:
        statement = statement.where(Entry.competition_id == UUID(competition_id))
    if paid is not None:
        statement = statement.where(Entry.paid == paid)
    
    entries = session.exec(statement).all()
    
    result = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        competition = session.get(Competition, entry.competition_id)
        if dancer and competition:
            result.append(EntryResponse(
                id=str(entry.id),
                dancer_id=str(entry.dancer_id),
                dancer_name=dancer.name,
                dancer_school=None,
                competition_id=str(entry.competition_id),
                competition_name=competition.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an entry. Parents can only delete entries for their own dancers.
    Organizers/admins can delete any entry.
    """
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check ownership
    dancer = session.get(Dancer, entry.dancer_id)
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only delete their own dancers' entries
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete entries for your own dancers")
    
    session.delete(entry)
    session.commit()
    
    return {"message": "Entry deleted successfully"}


# ============= User Management Endpoints =============

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    session: Session = Depends(get_session),
    role: Optional[RoleType] = None
):
    """List all users with optional role filter."""
    statement = select(User)
    if role:
        statement = statement.where(User.role == role)
    
    users = session.exec(statement).all()
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role
        )
        for u in users
    ]

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str, 
    user_data: UserUpdate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Update a user's name or role. Requires super_admin role."""
    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.name is not None:
        user.name = user_data.name
    if user_data.role is not None:
        user.role = user_data.role
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        email_verified=user.email_verified
    )


# ============= Site Settings (Admin) =============

@router.get("/admin/settings", response_model=SiteSettingsResponse)
async def get_settings(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Get site settings. Requires super_admin role."""
    settings = get_site_settings(session)
    
    return SiteSettingsResponse(
        resend_configured=bool(settings.resend_api_key),
        resend_from_email=settings.resend_from_email,
        site_name=settings.site_name,
        site_url=settings.site_url
    )


@router.put("/admin/settings", response_model=SiteSettingsResponse)
async def update_settings(
    settings_data: SiteSettingsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin())
):
    """Update site settings. Requires super_admin role."""
    settings = get_site_settings(session)
    
    if settings_data.resend_api_key is not None:
        settings.resend_api_key = settings_data.resend_api_key
    if settings_data.resend_from_email is not None:
        settings.resend_from_email = settings_data.resend_from_email
    if settings_data.site_name is not None:
        settings.site_name = settings_data.site_name
    if settings_data.site_url is not None:
        settings.site_url = settings_data.site_url
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return SiteSettingsResponse(
        resend_configured=bool(settings.resend_api_key),
        resend_from_email=settings.resend_from_email,
        site_name=settings.site_name,
        site_url=settings.site_url
    )

# ============= Dancer Endpoints =============

@router.get("/dancers", response_model=List[DancerResponse])
async def list_dancers(session: Session = Depends(get_session)):
    """List all dancers."""
    dancers = session.exec(select(Dancer)).all()
    return [
        DancerResponse(
            id=str(d.id),
            name=d.name,
            dob=d.dob,
            current_level=d.current_level,
            gender=d.gender,
            clrg_number=d.clrg_number,
            parent_id=str(d.parent_id),
            school_id=str(d.school_id) if d.school_id else None
        )
        for d in dancers
    ]


@router.get("/dancers/mine", response_model=List[DancerResponse])
async def list_my_dancers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """List dancers belonging to the current logged-in parent."""
    dancers = session.exec(
        select(Dancer).where(Dancer.parent_id == current_user.id)
    ).all()
    return [
        DancerResponse(
            id=str(d.id),
            name=d.name,
            dob=d.dob,
            current_level=d.current_level,
            gender=d.gender,
            clrg_number=d.clrg_number,
            parent_id=str(d.parent_id),
            school_id=str(d.school_id) if d.school_id else None
        )
        for d in dancers
    ]


@router.post("/dancers", response_model=DancerResponse)
async def create_dancer(
    dancer_data: DancerCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new dancer profile. The dancer is automatically linked to the 
    current logged-in user as the parent.
    """
    dancer = Dancer(
        parent_id=current_user.id,
        name=dancer_data.name,
        dob=dancer_data.dob,
        gender=dancer_data.gender,
        current_level=dancer_data.current_level,
        clrg_number=dancer_data.clrg_number,
        school_id=UUID(dancer_data.school_id) if dancer_data.school_id else None
    )
    session.add(dancer)
    session.commit()
    session.refresh(dancer)
    
    return DancerResponse(
        id=str(dancer.id),
        name=dancer.name,
        dob=dancer.dob,
        current_level=dancer.current_level,
        gender=dancer.gender,
        clrg_number=dancer.clrg_number,
        parent_id=str(dancer.parent_id),
        school_id=str(dancer.school_id) if dancer.school_id else None
    )


@router.put("/dancers/{dancer_id}", response_model=DancerResponse)
async def update_dancer(
    dancer_id: str,
    dancer_data: DancerUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update a dancer profile. Parents can only update their own dancers.
    """
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only update their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update your own dancers")
    
    # Apply updates
    if dancer_data.name is not None:
        dancer.name = dancer_data.name
    if dancer_data.dob is not None:
        dancer.dob = dancer_data.dob
    if dancer_data.gender is not None:
        dancer.gender = dancer_data.gender
    if dancer_data.current_level is not None:
        dancer.current_level = dancer_data.current_level
    if dancer_data.clrg_number is not None:
        dancer.clrg_number = dancer_data.clrg_number
    if dancer_data.school_id is not None:
        dancer.school_id = UUID(dancer_data.school_id) if dancer_data.school_id else None
    
    session.add(dancer)
    session.commit()
    session.refresh(dancer)
    
    return DancerResponse(
        id=str(dancer.id),
        name=dancer.name,
        dob=dancer.dob,
        current_level=dancer.current_level,
        gender=dancer.gender,
        clrg_number=dancer.clrg_number,
        parent_id=str(dancer.parent_id),
        school_id=str(dancer.school_id) if dancer.school_id else None
    )


@router.delete("/dancers/{dancer_id}")
async def delete_dancer(
    dancer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a dancer profile. Parents can only delete their own dancers.
    Will fail if the dancer has any existing entries.
    """
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Parents can only delete their own dancers
    if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own dancers")
    
    # Check if dancer has any entries
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.dancer_id == dancer.id)
    ).one()
    
    if entry_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot delete dancer with {entry_count} existing registration(s). Please delete entries first."
        )
    
    session.delete(dancer)
    session.commit()
    
    return {"message": f"Dancer '{dancer.name}' deleted successfully"}


# ============= Profile & Password Management =============

@router.put("/auth/profile", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update the current user's profile (name only).
    """
    if profile_data.name is not None:
        current_user.name = profile_data.name
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        email_verified=current_user.email_verified
    )


@router.put("/auth/password")
async def change_password(
    password_data: PasswordChangeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Change the current user's password.
    Requires the current password for verification.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(password_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    session.add(current_user)
    session.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/me/entries", response_model=List[EntryResponse])
async def get_my_entries(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get all entries for all dancers belonging to the current user.
    This is the user's registration history across all feiseanna.
    """
    # Get all dancers belonging to this user
    dancers = session.exec(
        select(Dancer).where(Dancer.parent_id == current_user.id)
    ).all()
    
    if not dancers:
        return []
    
    dancer_ids = [d.id for d in dancers]
    dancer_map = {d.id: d for d in dancers}
    
    # Get all entries for these dancers
    entries = session.exec(
        select(Entry).where(Entry.dancer_id.in_(dancer_ids))
    ).all()
    
    result = []
    for entry in entries:
        dancer = dancer_map.get(entry.dancer_id)
        competition = session.get(Competition, entry.competition_id)
        if dancer and competition:
            result.append(EntryResponse(
                id=str(entry.id),
                dancer_id=str(entry.dancer_id),
                dancer_name=dancer.name,
                dancer_school=None,
                competition_id=str(entry.competition_id),
                competition_name=competition.name,
                competitor_number=entry.competitor_number,
                paid=entry.paid,
                pay_later=entry.pay_later
            ))
    
    return result


# ============= Tabulator / Results Display =============

@router.get("/tabulator/competitions", response_model=List[CompetitionWithScores])
async def list_competitions_with_scores(
    session: Session = Depends(get_session),
    feis_id: Optional[str] = None
):
    """
    List competitions that have scores submitted.
    Used by the tabulator to select which competition to view results for.
    Optionally filter by feis_id.
    """
    # Build query for competitions
    if feis_id:
        competitions = session.exec(
            select(Competition).where(Competition.feis_id == UUID(feis_id))
        ).all()
    else:
        competitions = session.exec(select(Competition)).all()
    
    # Get feis info for names
    feis_ids = list(set(c.feis_id for c in competitions))
    feiseanna = session.exec(select(Feis).where(Feis.id.in_(feis_ids))).all()
    feis_map = {f.id: f for f in feiseanna}
    
    result = []
    for comp in competitions:
        # Count entries
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        # Count scores (using competition_id as round_id)
        score_count = session.exec(
            select(func.count(JudgeScore.id)).where(JudgeScore.round_id == str(comp.id))
        ).one()
        
        # Only include competitions that have scores
        if score_count > 0:
            feis = feis_map.get(comp.feis_id)
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
    
    Returns Irish Points rankings with dancer names, competitor numbers,
    and recall status (top 50% + tie extension).
    """
    competition = session.get(Competition, UUID(comp_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, competition.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all scores for this competition (competition_id is used as round_id)
    scores = session.exec(
        select(JudgeScore).where(JudgeScore.round_id == str(competition.id))
    ).all()
    
    # Calculate results using the scoring engine
    round_result = calculator.calculate_round(str(competition.id), list(scores))
    
    # Get unique judge count
    judge_ids = set(s.judge_id for s in scores)
    
    # Calculate recall list
    recalled_ids = calculator.calculate_recall(round_result.results)
    recalled_set = set(recalled_ids)
    
    # Build rich results with dancer info
    result_items = []
    for ranked in round_result.results:
        # competitor_id is actually entry_id
        entry = session.get(Entry, UUID(ranked.competitor_id))
        if not entry:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        if not dancer:
            continue
        
        # Get school name if available
        school_name = None
        if dancer.school_id:
            teacher = session.get(User, dancer.school_id)
            school_name = teacher.name if teacher else None
        
        result_items.append(TabulatorResultItem(
            rank=ranked.rank,
            competitor_number=entry.competitor_number,
            dancer_name=dancer.name,
            dancer_school=school_name,
            irish_points=ranked.irish_points,
            is_recalled=ranked.competitor_id in recalled_set
        ))
    
    # Count total competitors (entries with numbers in this competition)
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


# ============= Number Card PDF Generation =============

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
    """
    Look up school name from school_id (which references a User/Teacher).
    Returns None if not found.
    """
    if not school_id:
        return None
    teacher = session.get(User, school_id)
    return teacher.name if teacher else None


@router.get("/feis/{feis_id}/number-cards")
async def generate_feis_number_cards(
    feis_id: str,
    session: Session = Depends(get_session),
    base_url: str = Query("https://openfeis.com", description="Base URL for QR code check-in links"),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Generate a PDF of all number cards for a feis.
    
    Cards are sorted by School Name (blanks last), then Dancer Name.
    Each page contains 2 cards (5.5" x 8.5" landscape, stacked on US Letter).
    
    Requires organizer (owner) or super_admin role.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only generate cards for your own feis")
    
    # Get all competitions for this feis
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    if not competitions:
        raise HTTPException(status_code=400, detail="No competitions found for this feis")
    
    comp_ids = [c.id for c in competitions]
    comp_map = {c.id: c for c in competitions}
    
    # Get all entries with assigned numbers
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
    
    # Group entries by dancer to build card data
    dancer_entries: dict[UUID, list[Entry]] = {}
    for entry in entries:
        if entry.dancer_id not in dancer_entries:
            dancer_entries[entry.dancer_id] = []
        dancer_entries[entry.dancer_id].append(entry)
    
    # Build NumberCardData for each dancer
    cards: List[NumberCardData] = []
    
    for dancer_id, dancer_entry_list in dancer_entries.items():
        dancer = session.get(Dancer, dancer_id)
        if not dancer:
            continue
        
        # All entries for a dancer should have the same competitor number
        competitor_number = dancer_entry_list[0].competitor_number
        
        # Get school name
        school_name = get_school_name(session, dancer.school_id)
        
        # Calculate age group
        comp_age = calculate_competition_age(dancer.dob, feis.date)
        age_group = f"U{comp_age}"
        
        # Get level (use dancer's current level)
        level = dancer.current_level.value.title()
        
        # Get list of competition codes/numbers
        competition_codes = []
        for entry in dancer_entry_list:
            comp = comp_map.get(entry.competition_id)
            if comp:
                # Use competition name or extract a short code
                # For now, use first few chars of comp name
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
    
    # Generate PDF
    pdf_buffer = generate_number_cards_pdf(cards, base_url=base_url)
    
    # Create filename
    safe_feis_name = "".join(c for c in feis.name if c.isalnum() or c in " -_").strip()
    filename = f"{safe_feis_name}_NumberCards.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


# ============= Cloud Sync Endpoints =============

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
    scores: TypeList[SyncScoreItem]

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
    conflicts: TypeList[SyncConflict]
    successful_ids: TypeList[str]
    message: str

class ConflictResolutionRequest(BaseModel):
    score_id: str
    resolution: str  # 'use_local' or 'use_server'
    local_value: float
    local_timestamp: str


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
    from datetime import datetime
    
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
    from datetime import datetime
    
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


@router.get("/entries/{entry_id}/number-card")
async def generate_single_number_card(
    entry_id: str,
    session: Session = Depends(get_session),
    base_url: str = Query("https://openfeis.com", description="Base URL for QR code check-in links"),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Generate a PDF with a single number card (for reprints).
    
    Looks up the dancer from the entry and generates their card
    with all their competition entries for that feis.
    
    Requires organizer (owner) or super_admin role.
    """
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    if entry.competitor_number is None:
        raise HTTPException(
            status_code=400, 
            detail="This entry does not have a competitor number assigned"
        )
    
    # Get the dancer
    dancer = session.get(Dancer, entry.dancer_id)
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Get the competition to find the feis
    competition = session.get(Competition, entry.competition_id)
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, competition.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only generate cards for your own feis")
    
    # Get all entries for this dancer in this feis
    all_feis_competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    comp_ids = [c.id for c in all_feis_competitions]
    comp_map = {c.id: c for c in all_feis_competitions}
    
    dancer_entries = session.exec(
        select(Entry)
        .where(Entry.dancer_id == dancer.id)
        .where(Entry.competition_id.in_(comp_ids))
    ).all()
    
    # Get school name
    school_name = get_school_name(session, dancer.school_id)
    
    # Calculate age group
    comp_age = calculate_competition_age(dancer.dob, feis.date)
    age_group = f"U{comp_age}"
    
    # Get level
    level = dancer.current_level.value.title()
    
    # Get list of competition codes
    competition_codes = []
    for e in dancer_entries:
        comp = comp_map.get(e.competition_id)
        if comp:
            competition_codes.append(comp.name[:20])
    
    card = NumberCardData(
        dancer_id=str(dancer.id),
        dancer_name=dancer.name,
        school_name=school_name,
        competitor_number=entry.competitor_number,
        age_group=age_group,
        level=level,
        competition_codes=competition_codes,
        feis_name=feis.name,
        feis_date=feis.date
    )
    
    # Generate single card PDF
    pdf_buffer = generate_single_card_pdf(card, base_url=base_url)
    
    # Create filename
    safe_dancer_name = "".join(c for c in dancer.name if c.isalnum() or c in " -_").strip()
    filename = f"NumberCard_{entry.competitor_number}_{safe_dancer_name}.pdf"
    
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )
