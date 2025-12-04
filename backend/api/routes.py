from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from datetime import date, datetime
from sqlmodel import Session, select, func
from backend.scoring_engine.models import JudgeScore, RoundResult, Round
from backend.scoring_engine.models_platform import (
    User, Feis, Competition, Dancer, Entry, CompetitionLevel, RoleType, SiteSettings,
    Stage, DanceType, ScoringMethod, FeisSettings, FeeItem, FeeCategory, Order, OrderItem, PaymentStatus
)
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
    TabulatorResultItem, TabulatorResults, CompetitionWithScores,
    # New scheduling schemas
    StageCreate, StageUpdate, StageResponse,
    DurationEstimateRequest, DurationEstimateResponse,
    ScheduleCompetitionRequest, BulkScheduleRequest, BulkScheduleResponse,
    ScheduleConflict, ConflictCheckResponse, ScheduledCompetition, SchedulerViewResponse,
    # Financial Engine schemas (Phase 3)
    FeisSettingsCreate, FeisSettingsUpdate, FeisSettingsResponse,
    FeeItemCreate, FeeItemUpdate, FeeItemResponse,
    CartCalculationRequest, CartCalculationResponse, CartLineItemResponse, CartItemRequest,
    CheckoutRequest, CheckoutResponse, OrderResponse,
    RegistrationStatusResponse, StripeOnboardingRequest, StripeOnboardingResponse, StripeStatusResponse
)
from backend.services.scheduling import (
    estimate_duration, estimate_competition_duration, detect_all_conflicts,
    get_dance_type_from_name, get_default_tempo, Conflict
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
            entry_count=entry_count,
            # New scheduling fields
            dance_type=comp.dance_type,
            tempo_bpm=comp.tempo_bpm,
            bars=comp.bars or 48,
            scoring_method=comp.scoring_method or ScoringMethod.SOLO,
            price_cents=comp.price_cents or 1000,
            max_entries=comp.max_entries,
            stage_id=str(comp.stage_id) if comp.stage_id else None,
            scheduled_time=comp.scheduled_time,
            estimated_duration_minutes=comp.estimated_duration_minutes,
            adjudicator_id=str(comp.adjudicator_id) if comp.adjudicator_id else None
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
        gender=comp_data.gender,
        # New fields
        dance_type=comp_data.dance_type,
        tempo_bpm=comp_data.tempo_bpm,
        bars=comp_data.bars,
        scoring_method=comp_data.scoring_method,
        price_cents=comp_data.price_cents,
        max_entries=comp_data.max_entries
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
        entry_count=0,
        dance_type=comp.dance_type,
        tempo_bpm=comp.tempo_bpm,
        bars=comp.bars or 48,
        scoring_method=comp.scoring_method or ScoringMethod.SOLO,
        price_cents=comp.price_cents or 1000,
        max_entries=comp.max_entries
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
    # New scheduling fields
    if comp_data.dance_type is not None:
        comp.dance_type = comp_data.dance_type
    if comp_data.tempo_bpm is not None:
        comp.tempo_bpm = comp_data.tempo_bpm
    if comp_data.bars is not None:
        comp.bars = comp_data.bars
    if comp_data.scoring_method is not None:
        comp.scoring_method = comp_data.scoring_method
    if comp_data.price_cents is not None:
        comp.price_cents = comp_data.price_cents
    if comp_data.max_entries is not None:
        comp.max_entries = comp_data.max_entries
    if comp_data.stage_id is not None:
        comp.stage_id = UUID(comp_data.stage_id) if comp_data.stage_id else None
    if comp_data.scheduled_time is not None:
        comp.scheduled_time = comp_data.scheduled_time
    if comp_data.estimated_duration_minutes is not None:
        comp.estimated_duration_minutes = comp_data.estimated_duration_minutes
    if comp_data.adjudicator_id is not None:
        comp.adjudicator_id = UUID(comp_data.adjudicator_id) if comp_data.adjudicator_id else None
    
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
        adjudicator_id=str(comp.adjudicator_id) if comp.adjudicator_id else None
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
                    
                    # Map dance name to DanceType enum
                    dance_type = get_dance_type_from_name(dance)
                    tempo = get_default_tempo(dance_type)
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=current_age - 2,
                        max_age=current_age,
                        level=level,
                        gender=gender,
                        # New fields
                        dance_type=dance_type,
                        tempo_bpm=tempo,
                        bars=48,  # Standard
                        scoring_method=request.scoring_method,
                        price_cents=request.price_cents
                    )
                    session.add(comp)
                    count += 1
        
        current_age += 2
    
    session.commit()
    
    return SyllabusGenerationResponse(
        generated_count=count,
        message=f"Successfully created {count} competitions for {feis.name}."
    )


# ============= Stage Management Endpoints =============

@router.get("/feis/{feis_id}/stages", response_model=List[StageResponse])
async def list_stages(feis_id: str, session: Session = Depends(get_session)):
    """List all stages for a feis."""
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
        result.append(StageResponse(
            id=str(stage.id),
            feis_id=str(stage.feis_id),
            name=stage.name,
            color=stage.color,
            sequence=stage.sequence,
            competition_count=comp_count
        ))
    
    return result


@router.post("/stages", response_model=StageResponse)
async def create_stage(
    stage_data: StageCreate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Create a new stage for a feis. Requires organizer or super_admin role."""
    feis = session.get(Feis, UUID(stage_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
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
        competition_count=0
    )


@router.put("/stages/{stage_id}", response_model=StageResponse)
async def update_stage(
    stage_id: str, 
    stage_data: StageUpdate, 
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Update a stage. Requires organizer or super_admin role."""
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    feis = session.get(Feis, stage.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update stages for your own feis")
    
    if stage_data.name is not None:
        stage.name = stage_data.name
    if stage_data.color is not None:
        stage.color = stage_data.color
    if stage_data.sequence is not None:
        stage.sequence = stage_data.sequence
    
    session.add(stage)
    session.commit()
    session.refresh(stage)
    
    comp_count = session.exec(
        select(func.count(Competition.id)).where(Competition.stage_id == stage.id)
    ).one()
    
    return StageResponse(
        id=str(stage.id),
        feis_id=str(stage.feis_id),
        name=stage.name,
        color=stage.color,
        sequence=stage.sequence,
        competition_count=comp_count
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
    competitions = session.exec(
        select(Competition).where(Competition.stage_id == stage.id)
    ).all()
    for comp in competitions:
        comp.stage_id = None
        session.add(comp)
    
    session.delete(stage)
    session.commit()
    
    return {"message": f"Stage '{stage.name}' deleted"}


# ============= Scheduling Endpoints =============

@router.post("/scheduling/estimate-duration", response_model=DurationEstimateResponse)
async def estimate_competition_duration_endpoint(
    request: DurationEstimateRequest
):
    """
    Estimate how long a competition will take based on entry count and dance parameters.
    
    This is a stateless calculation endpoint - no authentication required.
    """
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


@router.get("/feis/{feis_id}/scheduler", response_model=SchedulerViewResponse)
async def get_scheduler_view(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """
    Get all data needed for the scheduler view.
    
    Returns stages, competitions with scheduling info, and detected conflicts.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get stages
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
        stage_responses.append(StageResponse(
            id=str(stage.id),
            feis_id=str(stage.feis_id),
            name=stage.name,
            color=stage.color,
            sequence=stage.sequence,
            competition_count=comp_count
        ))
    
    # Get competitions with entry counts and estimated durations
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == feis.id)
    ).all()
    
    # Detect conflicts
    conflicts = detect_all_conflicts(feis.id, session)
    conflict_comp_ids = set()
    for conflict in conflicts:
        conflict_comp_ids.update(conflict.affected_competition_ids)
    
    comp_responses = []
    for comp in competitions:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
        ).one()
        
        # Get stage name if assigned
        stage_name = None
        if comp.stage_id:
            stage = session.get(Stage, comp.stage_id)
            stage_name = stage.name if stage else None
        
        # Calculate estimated duration if not set
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
            has_conflicts=str(comp.id) in conflict_comp_ids
        ))
    
    # Convert conflicts to response format
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
    """
    Schedule multiple competitions at once.
    
    Used by the Gantt scheduler to save all changes.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only schedule competitions for your own feis")
    
    scheduled_count = 0
    for schedule in request.schedules:
        comp = session.get(Competition, UUID(schedule.competition_id))
        if comp and comp.feis_id == feis.id:
            comp.stage_id = UUID(schedule.stage_id) if schedule.stage_id else None
            comp.scheduled_time = schedule.scheduled_time
            session.add(comp)
            scheduled_count += 1
    
    session.commit()
    
    # Detect conflicts after scheduling
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


@router.get("/feis/{feis_id}/conflicts", response_model=ConflictCheckResponse)
async def check_conflicts(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """
    Check for scheduling conflicts in a feis.
    
    Returns all detected sibling conflicts, adjudicator conflicts, and time overlaps.
    """
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


@router.post("/competitions/{comp_id}/update-duration")
async def update_competition_duration(
    comp_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Recalculate and update a competition's estimated duration based on current entry count.
    """
    comp = session.get(Competition, UUID(comp_id))
    if not comp:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, comp.feis_id)
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check ownership (unless super_admin)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update competitions for your own feis")
    
    # Get entry count
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.competition_id == comp.id)
    ).one()
    
    # Calculate new duration
    new_duration = estimate_competition_duration(comp, entry_count)
    comp.estimated_duration_minutes = new_duration
    
    session.add(comp)
    session.commit()
    
    return {
        "competition_id": str(comp.id),
        "entry_count": entry_count,
        "estimated_duration_minutes": new_duration
    }


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


# ============= Financial Engine (Phase 3) =============
# Imports for cart and stripe services
from backend.services.cart import (
    calculate_cart, create_order, get_feis_settings as get_cart_feis_settings,
    is_registration_open, is_late_registration, CartTotals
)
from backend.services.stripe import (
    is_stripe_configured, get_stripe_mode, is_organizer_connected,
    create_checkout_session, handle_checkout_success,
    create_organizer_onboarding_link, check_onboarding_status
)


# ============= Feis Settings Endpoints =============

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
        # Return defaults
        settings = FeisSettings(feis_id=feis.id)
        # Don't persist, just return defaults
    
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
    
    # Check ownership
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update settings for your own feis")
    
    # Get or create settings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    
    if not settings:
        settings = FeisSettings(feis_id=feis.id)
        session.add(settings)
    
    # Apply updates
    if settings_data.base_entry_fee_cents is not None:
        settings.base_entry_fee_cents = settings_data.base_entry_fee_cents
    if settings_data.per_competition_fee_cents is not None:
        settings.per_competition_fee_cents = settings_data.per_competition_fee_cents
    if settings_data.family_max_cents is not None:
        # -1 means no cap
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


# ============= Fee Item Endpoints =============

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
    
    # Soft delete - deactivate instead of removing
    item.active = False
    session.add(item)
    session.commit()
    
    return {"message": f"Fee item '{item.name}' deactivated"}


# ============= Cart & Checkout Endpoints =============

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
    
    # Check Stripe status
    stripe_connected, _ = is_organizer_connected(feis, session)
    stripe_enabled = is_stripe_configured() and stripe_connected
    
    # Determine available payment methods
    payment_methods = ["pay_at_door"]  # Always available
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


@router.post("/cart/calculate", response_model=CartCalculationResponse)
async def calculate_cart_totals(
    cart_data: CartCalculationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate cart totals with family cap and late fees.
    
    This is a stateless calculation endpoint - it doesn't create orders.
    Used by the frontend to show live pricing updates.
    """
    competition_ids = [UUID(item.competition_id) for item in cart_data.items]
    dancer_ids = [UUID(item.dancer_id) for item in cart_data.items]
    
    try:
        cart_totals = calculate_cart(
            session=session,
            feis_id=UUID(cart_data.feis_id),
            user_id=current_user.id,
            competition_ids=competition_ids,
            dancer_ids=dancer_ids,
            fee_item_quantities=cart_data.fee_items
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return CartCalculationResponse(
        line_items=[
            CartLineItemResponse(
                id=li.id,
                type=li.type,
                name=li.name,
                description=li.description,
                dancer_id=li.dancer_id,
                dancer_name=li.dancer_name,
                unit_price_cents=li.unit_price_cents,
                quantity=li.quantity,
                total_cents=li.total_cents,
                category=li.category
            )
            for li in cart_totals.line_items
        ],
        qualifying_subtotal_cents=cart_totals.qualifying_subtotal_cents,
        non_qualifying_subtotal_cents=cart_totals.non_qualifying_subtotal_cents,
        subtotal_cents=cart_totals.subtotal_cents,
        family_discount_cents=cart_totals.family_discount_cents,
        family_cap_applied=cart_totals.family_cap_applied,
        family_cap_cents=cart_totals.family_cap_cents,
        late_fee_cents=cart_totals.late_fee_cents,
        late_fee_applied=cart_totals.late_fee_applied,
        late_fee_date=cart_totals.late_fee_date,
        total_cents=cart_totals.total_cents,
        dancer_count=cart_totals.dancer_count,
        competition_count=cart_totals.competition_count,
        savings_percent=cart_totals.savings_percent
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    checkout_data: CheckoutRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Start checkout process.
    
    For pay_at_door=True: Creates order and entries immediately with PAY_AT_DOOR status.
    For pay_at_door=False: Creates order and returns Stripe checkout URL.
    """
    feis = session.get(Feis, UUID(checkout_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Check registration is open
    settings = get_cart_feis_settings(session, feis.id)
    is_open, message = is_registration_open(settings)
    if not is_open:
        raise HTTPException(status_code=400, detail=message)
    
    # Validate dancers belong to current user
    competition_ids = [UUID(item.competition_id) for item in checkout_data.items]
    dancer_ids = [UUID(item.dancer_id) for item in checkout_data.items]
    
    for dancer_id in set(dancer_ids):
        dancer = session.get(Dancer, dancer_id)
        if not dancer:
            raise HTTPException(status_code=404, detail=f"Dancer not found")
        if current_user.role == RoleType.PARENT and dancer.parent_id != current_user.id:
            raise HTTPException(status_code=403, detail="You can only register your own dancers")
    
    # Calculate cart
    try:
        cart_totals = calculate_cart(
            session=session,
            feis_id=feis.id,
            user_id=current_user.id,
            competition_ids=competition_ids,
            dancer_ids=dancer_ids,
            fee_item_quantities=checkout_data.fee_items
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create order
    order = create_order(
        session=session,
        feis_id=feis.id,
        user_id=current_user.id,
        cart_totals=cart_totals,
        pay_at_door=checkout_data.pay_at_door
    )
    
    if checkout_data.pay_at_door:
        # Done - entries created, will pay at door
        return CheckoutResponse(
            success=True,
            order_id=str(order.id),
            checkout_url=None,
            is_test_mode=False,
            message=f"Registration complete! Please pay ${order.total_cents / 100:.2f} at check-in."
        )
    
    # Online payment - create Stripe checkout session
    # Note: These URLs would need to be configured properly in production
    base_url = settings.site_url if hasattr(settings, 'site_url') else "http://localhost:5173"
    site_settings = get_site_settings(session)
    base_url = site_settings.site_url
    
    success_url = f"{base_url}/registration/success"
    cancel_url = f"{base_url}/registration/cancel"
    
    result = create_checkout_session(
        session=session,
        order=order,
        cart_totals=cart_totals,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    if not result.success:
        return CheckoutResponse(
            success=False,
            order_id=str(order.id),
            checkout_url=None,
            is_test_mode=result.is_test_mode,
            message=result.error or "Failed to create checkout session"
        )
    
    return CheckoutResponse(
        success=True,
        order_id=str(order.id),
        checkout_url=result.checkout_url,
        is_test_mode=result.is_test_mode,
        message="Redirecting to payment..." if not result.is_test_mode else "Test mode: Simulating successful payment"
    )


@router.get("/checkout/success")
async def checkout_success(
    session_id: str,
    test_mode: bool = False,
    session: Session = Depends(get_session)
):
    """
    Handle successful checkout return.
    
    Called when user is redirected back from Stripe (or test mode).
    Marks the order as paid.
    """
    success, order, error = handle_checkout_success(
        session=session,
        checkout_session_id=session_id,
        is_test_mode=test_mode
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=error or "Payment verification failed")
    
    return {
        "success": True,
        "order_id": str(order.id),
        "message": "Payment successful! Your registration is confirmed."
    }


@router.get("/orders", response_model=List[OrderResponse])
async def list_my_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    feis_id: Optional[str] = None
):
    """List orders for the current user."""
    statement = select(Order).where(Order.user_id == current_user.id)
    
    if feis_id:
        statement = statement.where(Order.feis_id == UUID(feis_id))
    
    statement = statement.order_by(Order.created_at.desc())
    orders = session.exec(statement).all()
    
    result = []
    for order in orders:
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.order_id == order.id)
        ).one()
        
        result.append(OrderResponse(
            id=str(order.id),
            feis_id=str(order.feis_id),
            user_id=str(order.user_id),
            subtotal_cents=order.subtotal_cents,
            qualifying_subtotal_cents=order.qualifying_subtotal_cents,
            non_qualifying_subtotal_cents=order.non_qualifying_subtotal_cents,
            family_discount_cents=order.family_discount_cents,
            late_fee_cents=order.late_fee_cents,
            total_cents=order.total_cents,
            status=order.status,
            created_at=order.created_at,
            paid_at=order.paid_at,
            entry_count=entry_count
        ))
    
    return result


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get a specific order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Check ownership
    if order.user_id != current_user.id and current_user.role not in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entry_count = session.exec(
        select(func.count(Entry.id)).where(Entry.order_id == order.id)
    ).one()
    
    return OrderResponse(
        id=str(order.id),
        feis_id=str(order.feis_id),
        user_id=str(order.user_id),
        subtotal_cents=order.subtotal_cents,
        qualifying_subtotal_cents=order.qualifying_subtotal_cents,
        non_qualifying_subtotal_cents=order.non_qualifying_subtotal_cents,
        family_discount_cents=order.family_discount_cents,
        late_fee_cents=order.late_fee_cents,
        total_cents=order.total_cents,
        status=order.status,
        created_at=order.created_at,
        paid_at=order.paid_at,
        entry_count=entry_count
    )


# ============= Stripe Connect Endpoints =============

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
    
    # Check onboarding status
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == feis.id)
    ).first()
    onboarding_complete = settings.stripe_onboarding_complete if settings else False
    
    # Build message
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
    
    # In test mode, just mark as complete
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
    
    # Real Stripe - check account status
    is_complete, message = check_onboarding_status(session, feis.id)
    
    return {
        "success": is_complete,
        "message": message,
        "is_test_mode": False
    }
