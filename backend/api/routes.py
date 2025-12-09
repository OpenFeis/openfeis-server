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
    Stage, DanceType, ScoringMethod, FeisSettings, FeeItem, FeeCategory, Order, OrderItem, PaymentStatus,
    FeisAdjudicator, AdjudicatorAvailability, AdjudicatorStatus, AvailabilityType, StageJudgeCoverage
)
from backend.scoring_engine.calculator import IrishPointsCalculator
from backend.db.database import get_session
from backend.utils.competition_codes import generate_competition_code
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
    StageCreate, StageUpdate, StageResponse, StageJudgeCoverageCreate, StageJudgeCoverageResponse,
    DurationEstimateRequest, DurationEstimateResponse,
    ScheduleCompetitionRequest, BulkScheduleRequest, BulkScheduleResponse,
    ScheduleConflict, ConflictCheckResponse, ScheduledCompetition, SchedulerViewResponse,
    # Financial Engine schemas (Phase 3)
    FeisSettingsCreate, FeisSettingsUpdate, FeisSettingsResponse,
    FeeItemCreate, FeeItemUpdate, FeeItemResponse,
    CartCalculationRequest, CartCalculationResponse, CartLineItemResponse, CartItemRequest,
    CheckoutRequest, CheckoutResponse, OrderResponse,
    RegistrationStatusResponse, StripeOnboardingRequest, StripeOnboardingResponse, StripeStatusResponse,
    # Adjudicator Roster schemas (Phase 6)
    AdjudicatorCreate, AdjudicatorUpdate, AdjudicatorResponse, AdjudicatorListResponse,
    AdjudicatorCapacityResponse,
    AvailabilityBlockCreate, AvailabilityBlockUpdate, AvailabilityBlockResponse,
    AdjudicatorAvailabilityResponse, BulkAvailabilityCreate,
    AdjudicatorInviteRequest, AdjudicatorInviteResponse,
    AdjudicatorAcceptInviteRequest, AdjudicatorAcceptInviteResponse,
    GeneratePinRequest, GeneratePinResponse, PinLoginRequest, PinLoginResponse,
    SchedulingDefaultsUpdate, SchedulingDefaultsResponse
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
import secrets
import random
from datetime import timedelta

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
            code=comp.code,
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
    
    # Auto-generate code if not provided
    code = comp_data.code
    if not code:
        code = generate_competition_code(
            level=comp_data.level.value,
            min_age=comp_data.min_age,
            dance_type=comp_data.dance_type.value if comp_data.dance_type else None
        )
    
    comp = Competition(
        feis_id=feis.id,
        name=comp_data.name,
        min_age=comp_data.min_age,
        max_age=comp_data.max_age,
        level=comp_data.level,
        gender=comp_data.gender,
        code=code,
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
        code=comp.code,
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

# Helper to format level names for display
def format_level_name(level_value: str) -> str:
    """Convert snake_case level to proper display name."""
    level_names = {
        'first_feis': 'First Feis',
        'beginner_1': 'Beginner 1',
        'beginner_2': 'Beginner 2',
        'novice': 'Novice',
        'prizewinner': 'Prizewinner',
        'preliminary_championship': 'Preliminary Championship',
        'open_championship': 'Open Championship',
    }
    return level_names.get(level_value, level_value.replace('_', ' ').title())


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
                    comp_name = f"{gender.value.title()} {age_group} {dance} ({format_level_name(level.value)})"
                    
                    # Map dance name to DanceType enum
                    dance_type = get_dance_type_from_name(dance)
                    tempo = get_default_tempo(dance_type)
                    
                    # Generate competition code
                    code = generate_competition_code(
                        level=level.value,
                        min_age=current_age,  # Use age group (e.g., U6 -> 6)
                        dance_type=dance_type.value if dance_type else None
                    )
                    
                    comp = Competition(
                        feis_id=feis.id,
                        name=comp_name,
                        min_age=current_age - 2,
                        max_age=current_age,
                        level=level,
                        gender=gender,
                        code=code,
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
        
        # Get judge coverage blocks for this stage
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
    
    # Get judge coverage blocks
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
    
    return StageResponse(
        id=str(stage.id),
        feis_id=str(stage.feis_id),
        name=stage.name,
        color=stage.color,
        sequence=stage.sequence,
        competition_count=comp_count,
        judge_coverage=coverage_responses
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


# ============= Stage Judge Coverage Endpoints =============

@router.get("/stages/{stage_id}/coverage", response_model=List[StageJudgeCoverageResponse])
async def list_stage_coverage(
    stage_id: str,
    session: Session = Depends(get_session)
):
    """List all judge coverage blocks for a stage."""
    stage = session.get(Stage, UUID(stage_id))
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    coverage_blocks = session.exec(
        select(StageJudgeCoverage)
        .where(StageJudgeCoverage.stage_id == stage.id)
        .order_by(StageJudgeCoverage.feis_day, StageJudgeCoverage.start_time)
    ).all()
    
    result = []
    for cov in coverage_blocks:
        adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
        result.append(StageJudgeCoverageResponse(
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
    
    return result


@router.post("/stages/{stage_id}/coverage", response_model=StageJudgeCoverageResponse)
async def create_stage_coverage(
    stage_id: str,
    coverage_data: StageJudgeCoverageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Add a judge coverage block to a stage."""
    from datetime import time as dt_time
    
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
    
    # Parse time strings
    try:
        start_parts = coverage_data.start_time.split(":")
        end_parts = coverage_data.end_time.split(":")
        start_time = dt_time(int(start_parts[0]), int(start_parts[1]))
        end_time = dt_time(int(end_parts[0]), int(end_parts[1]))
        feis_day = date.fromisoformat(coverage_data.feis_day)
    except (ValueError, IndexError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid time/date format: {str(e)}")
    
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    # Check for overlapping coverage blocks for the same judge on the same day
    existing = session.exec(
        select(StageJudgeCoverage)
        .where(StageJudgeCoverage.feis_adjudicator_id == adj.id)
        .where(StageJudgeCoverage.feis_day == feis_day)
    ).all()
    
    for block in existing:
        # Check for time overlap
        if not (end_time <= block.start_time or start_time >= block.end_time):
            other_stage = session.get(Stage, block.stage_id)
            raise HTTPException(
                status_code=400, 
                detail=f"Judge '{adj.name}' already has coverage on {other_stage.name if other_stage else 'another stage'} from {block.start_time.strftime('%H:%M')} to {block.end_time.strftime('%H:%M')}"
            )
    
    # Create coverage block
    coverage = StageJudgeCoverage(
        stage_id=stage.id,
        feis_adjudicator_id=adj.id,
        feis_day=feis_day,
        start_time=start_time,
        end_time=end_time,
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


@router.get("/feis/{feis_id}/judge-schedule", response_model=List[StageJudgeCoverageResponse])
async def get_feis_judge_schedule(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get all judge coverage blocks for a feis (cross-stage view for judges)."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all stages for this feis
    stages = session.exec(select(Stage).where(Stage.feis_id == feis.id)).all()
    stage_ids = [s.id for s in stages]
    stage_map = {s.id: s for s in stages}
    
    if not stage_ids:
        return []
    
    # Get all coverage blocks for these stages
    coverage_blocks = session.exec(
        select(StageJudgeCoverage)
        .where(StageJudgeCoverage.stage_id.in_(stage_ids))
        .order_by(StageJudgeCoverage.feis_day, StageJudgeCoverage.start_time)
    ).all()
    
    result = []
    for cov in coverage_blocks:
        adj = session.get(FeisAdjudicator, cov.feis_adjudicator_id)
        stage = stage_map.get(cov.stage_id)
        result.append(StageJudgeCoverageResponse(
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
    
    return result


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
        
        # Get judge coverage blocks for this stage
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
        
        stage_responses.append(StageResponse(
            id=str(stage.id),
            feis_id=str(stage.feis_id),
            name=stage.name,
            color=stage.color,
            sequence=stage.sequence,
            competition_count=comp_count,
            judge_coverage=coverage_responses
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
    role: Optional[RoleType] = None,
    search: Optional[str] = None,
    limit: int = 50
):
    """
    List users with optional filters.
    
    - role: Filter by role (teacher, organizer, etc.)
    - search: Search by email or name (partial match)
    - limit: Maximum number of results (default 50)
    """
    statement = select(User)
    
    if role:
        statement = statement.where(User.role == role)
    
    if search:
        search_lower = f"%{search.lower()}%"
        statement = statement.where(
            (func.lower(User.email).like(search_lower)) |
            (func.lower(User.name).like(search_lower))
        )
    
    statement = statement.limit(limit)
    users = session.exec(statement).all()
    
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            email_verified=u.email_verified
        )
        for u in users
    ]


@router.get("/teachers", response_model=List[UserResponse])
async def list_teachers(
    session: Session = Depends(get_session),
    search: Optional[str] = None
):
    """
    List all teachers (for school selection dropdown).
    
    Returns users with role=teacher, searchable by name.
    """
    statement = select(User).where(User.role == RoleType.TEACHER)
    
    if search:
        search_lower = f"%{search.lower()}%"
        statement = statement.where(func.lower(User.name).like(search_lower))
    
    teachers = session.exec(statement.order_by(User.name)).all()
    
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            name=u.name,
            role=u.role,
            email_verified=u.email_verified
        )
        for u in teachers
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


# ============= Phase 4: Teacher Portal & Advancement =============

from backend.scoring_engine.models_platform import PlacementHistory, EntryFlag, AdvancementNotice
from backend.api.schemas import (
    PlacementHistoryCreate, PlacementHistoryResponse, DancerPlacementHistoryResponse,
    AdvancementRuleInfo, AdvancementNoticeResponse, AdvancementCheckResponse,
    AcknowledgeAdvancementRequest, OverrideAdvancementRequest,
    EntryFlagCreate, EntryFlagResponse, ResolveFlagRequest, FlaggedEntriesResponse,
    TeacherStudentEntry, SchoolRosterResponse, SchoolStudentInfo,
    TeacherDashboardResponse, LinkDancerToSchoolRequest
)
from backend.services.advancement import (
    get_advancement_rules, get_rule_for_level, check_advancement,
    process_advancement, get_pending_advancements, get_all_advancements,
    acknowledge_advancement, override_advancement, get_eligible_levels,
    check_registration_eligibility, record_placement_and_check_advancement,
    get_dancer_placement_summary
)


# Helper for teacher role check
def require_teacher():
    """Require teacher role for endpoint access."""
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in [RoleType.TEACHER, RoleType.SUPER_ADMIN, RoleType.ORGANIZER]:
            raise HTTPException(
                status_code=403,
                detail="Teacher access required"
            )
        return current_user
    return role_checker


# --- Advancement Rules ---

@router.get("/advancement/rules", response_model=List[AdvancementRuleInfo])
async def list_advancement_rules():
    """Get all advancement rules."""
    rules = get_advancement_rules()
    return [
        AdvancementRuleInfo(
            level=r.level,
            wins_required=r.wins_required,
            next_level=r.next_level,
            per_dance=r.per_dance,
            description=r.description
        )
        for r in rules
    ]


# --- Placement History ---

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
    placement_data: PlacementHistoryCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Record a placement for a dancer.
    
    Typically called automatically when results are finalized,
    but can be called manually by organizers for corrections.
    """
    dancer = session.get(Dancer, UUID(placement_data.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    competition = session.get(Competition, UUID(placement_data.competition_id))
    if not competition:
        raise HTTPException(status_code=404, detail="Competition not found")
    
    feis = session.get(Feis, UUID(placement_data.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Create placement
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
    
    # Check for advancements if 1st place
    if placement.rank == 1:
        process_advancement(session, dancer)
    
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


# --- Advancement Checks ---

@router.get("/dancers/{dancer_id}/advancement", response_model=AdvancementCheckResponse)
async def check_dancer_advancement(
    dancer_id: str,
    session: Session = Depends(get_session)
):
    """
    Check a dancer's advancement status.
    
    Returns pending advancements and eligible levels.
    """
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
    """
    Override an advancement requirement (admin only).
    
    Allows a dancer to continue competing at their current level.
    """
    try:
        notice = override_advancement(
            session, UUID(advancement_id), current_user.id, override_data.reason
        )
        return {"success": True, "message": "Advancement requirement overridden"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- Entry Flagging ---

@router.post("/entries/{entry_id}/flag", response_model=EntryFlagResponse)
async def flag_entry(
    entry_id: str,
    flag_data: EntryFlagCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """
    Flag an entry for organizer review.
    
    Teachers can flag entries they believe are incorrect.
    """
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Check if already flagged
    existing = session.exec(
        select(EntryFlag)
        .where(EntryFlag.entry_id == entry.id)
        .where(EntryFlag.resolved == False)
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Entry already has an unresolved flag")
    
    # Create flag
    flag = EntryFlag(
        entry_id=entry.id,
        flagged_by=current_user.id,
        reason=flag_data.reason,
        flag_type=flag_data.flag_type
    )
    
    session.add(flag)
    session.commit()
    session.refresh(flag)
    
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    
    return EntryFlagResponse(
        id=str(flag.id),
        entry_id=str(flag.entry_id),
        dancer_name=dancer.name if dancer else "Unknown",
        competition_name=competition.name if competition else "Unknown",
        flagged_by=str(flag.flagged_by),
        flagged_by_name=current_user.name,
        reason=flag.reason,
        flag_type=flag.flag_type,
        resolved=flag.resolved,
        resolved_by=str(flag.resolved_by) if flag.resolved_by else None,
        resolved_by_name=None,
        resolved_at=flag.resolved_at,
        resolution_note=flag.resolution_note,
        created_at=flag.created_at
    )


@router.get("/feis/{feis_id}/flags", response_model=FlaggedEntriesResponse)
async def get_feis_flags(
    feis_id: str,
    include_resolved: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Get all flagged entries for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get all entries for this feis
    entry_ids = session.exec(
        select(Entry.id)
        .join(Competition)
        .where(Competition.feis_id == feis.id)
    ).all()
    
    # Get flags for these entries
    query = select(EntryFlag).where(EntryFlag.entry_id.in_(entry_ids))
    if not include_resolved:
        query = query.where(EntryFlag.resolved == False)
    
    flags = session.exec(query.order_by(EntryFlag.created_at.desc())).all()
    
    flag_responses = []
    for flag in flags:
        entry = session.get(Entry, flag.entry_id)
        dancer = session.get(Dancer, entry.dancer_id) if entry else None
        competition = session.get(Competition, entry.competition_id) if entry else None
        flagged_by_user = session.get(User, flag.flagged_by)
        resolved_by_user = session.get(User, flag.resolved_by) if flag.resolved_by else None
        
        flag_responses.append(EntryFlagResponse(
            id=str(flag.id),
            entry_id=str(flag.entry_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_name=competition.name if competition else "Unknown",
            flagged_by=str(flag.flagged_by),
            flagged_by_name=flagged_by_user.name if flagged_by_user else "Unknown",
            reason=flag.reason,
            flag_type=flag.flag_type,
            resolved=flag.resolved,
            resolved_by=str(flag.resolved_by) if flag.resolved_by else None,
            resolved_by_name=resolved_by_user.name if resolved_by_user else None,
            resolved_at=flag.resolved_at,
            resolution_note=flag.resolution_note,
            created_at=flag.created_at
        ))
    
    unresolved = len([f for f in flag_responses if not f.resolved])
    
    return FlaggedEntriesResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        total_flags=len(flag_responses),
        unresolved_count=unresolved,
        flags=flag_responses
    )


@router.post("/flags/{flag_id}/resolve")
async def resolve_flag(
    flag_id: str,
    resolve_data: ResolveFlagRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Resolve a flagged entry."""
    flag = session.get(EntryFlag, UUID(flag_id))
    if not flag:
        raise HTTPException(status_code=404, detail="Flag not found")
    
    from datetime import datetime
    
    flag.resolved = True
    flag.resolved_by = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.resolution_note = resolve_data.resolution_note
    
    session.add(flag)
    session.commit()
    
    return {"success": True, "message": "Flag resolved"}


# --- Teacher Dashboard ---

@router.get("/teacher/dashboard", response_model=TeacherDashboardResponse)
async def get_teacher_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get teacher dashboard with school overview."""
    # Get all dancers linked to this teacher's school
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    dancer_ids = [d.id for d in dancers]
    
    # Get all entries for these dancers
    entries = []
    entries_by_feis = {}
    
    if dancer_ids:
        entries = session.exec(
            select(Entry)
            .where(Entry.dancer_id.in_(dancer_ids))
        ).all()
        
        for entry in entries:
            comp = session.get(Competition, entry.competition_id)
            if comp:
                feis_id = str(comp.feis_id)
                entries_by_feis[feis_id] = entries_by_feis.get(feis_id, 0) + 1
    
    # Get pending advancements
    pending_advancements = 0
    for dancer in dancers:
        pending = get_pending_advancements(session, dancer.id)
        pending_advancements += len(pending)
    
    # Build recent entries
    recent_entries = []
    for entry in entries[:20]:  # Limit to 20 most recent
        dancer = session.get(Dancer, entry.dancer_id)
        comp = session.get(Competition, entry.competition_id)
        feis = session.get(Feis, comp.feis_id) if comp else None
        
        # Check if flagged
        flag = session.exec(
            select(EntryFlag)
            .where(EntryFlag.entry_id == entry.id)
            .where(EntryFlag.resolved == False)
        ).first()
        
        recent_entries.append(TeacherStudentEntry(
            entry_id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id),
            competition_name=comp.name if comp else "Unknown",
            level=comp.level if comp else CompetitionLevel.BEGINNER_1,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            feis_id=str(comp.feis_id) if comp else "",
            feis_name=feis.name if feis else "Unknown",
            feis_date=feis.date if feis else None,
            is_flagged=flag is not None,
            flag_id=str(flag.id) if flag else None
        ))
    
    return TeacherDashboardResponse(
        teacher_id=str(current_user.id),
        teacher_name=current_user.name,
        total_students=len(dancers),
        total_entries=len(entries),
        entries_by_feis=entries_by_feis,
        pending_advancements=pending_advancements,
        recent_entries=recent_entries
    )


@router.get("/teacher/roster", response_model=SchoolRosterResponse)
async def get_school_roster(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get the teacher's school roster."""
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    students = []
    for dancer in dancers:
        parent = session.get(User, dancer.parent_id)
        
        # Count entries
        entry_count = session.exec(
            select(func.count(Entry.id)).where(Entry.dancer_id == dancer.id)
        ).one()
        
        # Count pending advancements
        pending = get_pending_advancements(session, dancer.id)
        
        students.append(SchoolStudentInfo(
            id=str(dancer.id),
            name=dancer.name,
            dob=dancer.dob,
            current_level=dancer.current_level,
            gender=dancer.gender,
            parent_name=parent.name if parent else "Unknown",
            entry_count=entry_count,
            pending_advancements=len(pending)
        ))
    
    return SchoolRosterResponse(
        school_id=str(current_user.id),
        teacher_name=current_user.name,
        total_students=len(students),
        students=students
    )


@router.get("/teacher/entries", response_model=List[TeacherStudentEntry])
async def get_teacher_student_entries(
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """Get all entries for students in the teacher's school."""
    # Get all dancers linked to this teacher
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    dancer_ids = [d.id for d in dancers]
    
    if not dancer_ids:
        return []
    
    # Build entry query
    query = select(Entry).where(Entry.dancer_id.in_(dancer_ids))
    
    entries = session.exec(query).all()
    
    # Filter by feis if specified
    results = []
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if not comp:
            continue
        
        if feis_id and str(comp.feis_id) != feis_id:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, comp.feis_id)
        
        # Check if flagged
        flag = session.exec(
            select(EntryFlag)
            .where(EntryFlag.entry_id == entry.id)
            .where(EntryFlag.resolved == False)
        ).first()
        
        results.append(TeacherStudentEntry(
            entry_id=str(entry.id),
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id),
            competition_name=comp.name,
            level=comp.level,
            competitor_number=entry.competitor_number,
            paid=entry.paid,
            feis_id=str(comp.feis_id),
            feis_name=feis.name if feis else "Unknown",
            feis_date=feis.date if feis else None,
            is_flagged=flag is not None,
            flag_id=str(flag.id) if flag else None
        ))
    
    return results


@router.post("/dancers/{dancer_id}/link-school")
async def link_dancer_to_school(
    dancer_id: str,
    link_data: LinkDancerToSchoolRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Link a dancer to a school (teacher).
    
    Can be done by:
    - The dancer's parent
    - The teacher being linked to
    - An admin
    """
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    teacher = session.get(User, UUID(link_data.school_id))
    if not teacher or teacher.role != RoleType.TEACHER:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Check permissions
    is_parent = dancer.parent_id == current_user.id
    is_teacher = UUID(link_data.school_id) == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_parent or is_teacher or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to link this dancer")
    
    dancer.school_id = teacher.id
    session.add(dancer)
    session.commit()
    
    return {"success": True, "message": f"Dancer linked to {teacher.name}'s school"}


@router.delete("/dancers/{dancer_id}/unlink-school")
async def unlink_dancer_from_school(
    dancer_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Remove a dancer from their school."""
    dancer = session.get(Dancer, UUID(dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    
    # Check permissions
    is_parent = dancer.parent_id == current_user.id
    is_teacher = dancer.school_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_parent or is_teacher or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to unlink this dancer")
    
    dancer.school_id = None
    session.add(dancer)
    session.commit()
    
    return {"success": True, "message": "Dancer unlinked from school"}


@router.get("/teacher/export")
async def export_teacher_entries(
    feis_id: Optional[str] = None,
    format: str = "csv",
    session: Session = Depends(get_session),
    current_user: User = Depends(require_teacher())
):
    """
    Export teacher's student entries to CSV or JSON.
    """
    import csv
    import io
    import json
    
    # Get entries using the existing endpoint logic
    dancers = session.exec(
        select(Dancer).where(Dancer.school_id == current_user.id)
    ).all()
    
    dancer_ids = [d.id for d in dancers]
    
    if not dancer_ids:
        if format == "csv":
            return StreamingResponse(
                io.StringIO("No entries found"),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=school_entries.csv"}
            )
        return {"entries": []}
    
    entries = session.exec(
        select(Entry).where(Entry.dancer_id.in_(dancer_ids))
    ).all()
    
    # Build export data
    export_data = []
    for entry in entries:
        comp = session.get(Competition, entry.competition_id)
        if not comp:
            continue
        
        if feis_id and str(comp.feis_id) != feis_id:
            continue
        
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, comp.feis_id)
        
        export_data.append({
            "dancer_name": dancer.name if dancer else "Unknown",
            "competition_name": comp.name,
            "level": comp.level.value,
            "feis_name": feis.name if feis else "Unknown",
            "feis_date": str(feis.date) if feis else "",
            "competitor_number": entry.competitor_number or "",
            "paid": "Yes" if entry.paid else "No"
        })
    
    if format == "json":
        return {"entries": export_data}
    
    # CSV export
    output = io.StringIO()
    if export_data:
        writer = csv.DictWriter(output, fieldnames=export_data[0].keys())
        writer.writeheader()
        writer.writerows(export_data)
    
    output.seek(0)
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=school_entries_{feis_id or 'all'}.csv"}
    )


# ============= Phase 5: Waitlist, Check-In, Refunds =============

from backend.scoring_engine.models_platform import WaitlistEntry, RefundLog, CheckInStatus, WaitlistStatus
from backend.api.schemas import (
    WaitlistEntryResponse, WaitlistAddRequest, WaitlistStatusResponse,
    CheckInRequest, CheckInResponse, BulkCheckInRequest, BulkCheckInResponse,
    StageMonitorEntry, StageMonitorResponse, ScratchEntryRequest, ScratchEntryResponse,
    RefundRequest, RefundResponse, RefundLogResponse, OrderRefundSummary,
    FeisCapacityStatus
)
from backend.services.waitlist import (
    get_competition_capacity, get_feis_capacity, check_can_register,
    add_to_waitlist, get_user_waitlist_entries, process_spot_available,
    accept_waitlist_offer, cancel_waitlist_entry
)
from backend.services.checkin import (
    check_in_entry, check_in_by_number, bulk_check_in, undo_check_in,
    mark_scratched, get_stage_monitor_data, get_competition_check_in_stats,
    get_feis_check_in_summary, lookup_entry_by_qr
)
from backend.services.refund import (
    get_refund_policy, scratch_entry, process_full_refund,
    process_partial_refund, get_order_refund_summary, get_feis_refund_stats
)


# --- Capacity & Waitlist ---

@router.get("/feis/{feis_id}/capacity", response_model=FeisCapacityStatus)
async def get_feis_capacity_status(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get capacity status for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    cap_info = get_feis_capacity(session, UUID(feis_id))
    
    return FeisCapacityStatus(
        feis_id=str(feis.id),
        feis_name=feis.name,
        global_cap=cap_info.max_capacity,
        current_dancer_count=cap_info.current_count,
        spots_remaining=cap_info.spots_remaining,
        is_full=cap_info.is_full,
        waitlist_enabled=cap_info.waitlist_enabled,
        waitlist_count=cap_info.waitlist_count
    )


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


@router.post("/waitlist/add", response_model=WaitlistEntryResponse)
async def add_to_waitlist_endpoint(
    request: WaitlistAddRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Add a dancer to the waitlist."""
    # Verify dancer belongs to user
    dancer = session.get(Dancer, UUID(request.dancer_id))
    if not dancer:
        raise HTTPException(status_code=404, detail="Dancer not found")
    if dancer.parent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized for this dancer")
    
    feis = session.get(Feis, UUID(request.feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    comp_id = UUID(request.competition_id) if request.competition_id else None
    comp = session.get(Competition, comp_id) if comp_id else None
    
    entry = add_to_waitlist(
        session,
        UUID(request.feis_id),
        UUID(request.dancer_id),
        current_user.id,
        comp_id
    )
    
    return WaitlistEntryResponse(
        id=str(entry.id),
        feis_id=str(entry.feis_id),
        feis_name=feis.name,
        dancer_id=str(entry.dancer_id),
        dancer_name=dancer.name,
        competition_id=str(entry.competition_id) if entry.competition_id else None,
        competition_name=comp.name if comp else None,
        position=entry.position,
        status=entry.status,
        offer_sent_at=entry.offer_sent_at,
        offer_expires_at=entry.offer_expires_at,
        created_at=entry.created_at
    )


@router.get("/waitlist/mine", response_model=List[WaitlistEntryResponse])
async def get_my_waitlist_entries(
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get waitlist entries for current user's dancers."""
    feis_uuid = UUID(feis_id) if feis_id else None
    entries = get_user_waitlist_entries(session, current_user.id, feis_uuid)
    
    results = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        feis = session.get(Feis, entry.feis_id)
        comp = session.get(Competition, entry.competition_id) if entry.competition_id else None
        
        results.append(WaitlistEntryResponse(
            id=str(entry.id),
            feis_id=str(entry.feis_id),
            feis_name=feis.name if feis else "Unknown",
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id) if entry.competition_id else None,
            competition_name=comp.name if comp else None,
            position=entry.position,
            status=entry.status,
            offer_sent_at=entry.offer_sent_at,
            offer_expires_at=entry.offer_expires_at,
            created_at=entry.created_at
        ))
    
    return results


@router.post("/waitlist/{waitlist_id}/accept")
async def accept_waitlist(
    waitlist_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Accept a waitlist offer."""
    success, message, entry = accept_waitlist_offer(
        session, UUID(waitlist_id), current_user.id
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {
        "success": True,
        "message": message,
        "entry_id": str(entry.id) if entry else None
    }


@router.post("/waitlist/{waitlist_id}/cancel")
async def cancel_waitlist(
    waitlist_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Cancel a waitlist entry."""
    success, message = cancel_waitlist_entry(session, UUID(waitlist_id), current_user.id)
    
    if not success:
        raise HTTPException(status_code=400, detail=message)
    
    return {"success": True, "message": message}


@router.get("/feis/{feis_id}/waitlist", response_model=WaitlistStatusResponse)
async def get_feis_waitlist_status(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get waitlist status for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Global waitlist count
    global_count = session.exec(
        select(func.count(WaitlistEntry.id))
        .where(WaitlistEntry.feis_id == UUID(feis_id))
        .where(WaitlistEntry.competition_id.is_(None))
        .where(WaitlistEntry.status == WaitlistStatus.WAITING)
    ).one()
    
    # Per-competition waitlists
    comp_waitlists = {}
    competitions = session.exec(
        select(Competition).where(Competition.feis_id == UUID(feis_id))
    ).all()
    
    for comp in competitions:
        count = session.exec(
            select(func.count(WaitlistEntry.id))
            .where(WaitlistEntry.competition_id == comp.id)
            .where(WaitlistEntry.status == WaitlistStatus.WAITING)
        ).one()
        if count > 0:
            comp_waitlists[str(comp.id)] = count
    
    total = global_count + sum(comp_waitlists.values())
    
    # User's entries
    user_entries = get_user_waitlist_entries(session, current_user.id, UUID(feis_id))
    user_entry_responses = []
    for entry in user_entries:
        dancer = session.get(Dancer, entry.dancer_id)
        comp = session.get(Competition, entry.competition_id) if entry.competition_id else None
        user_entry_responses.append(WaitlistEntryResponse(
            id=str(entry.id),
            feis_id=str(entry.feis_id),
            feis_name=feis.name,
            dancer_id=str(entry.dancer_id),
            dancer_name=dancer.name if dancer else "Unknown",
            competition_id=str(entry.competition_id) if entry.competition_id else None,
            competition_name=comp.name if comp else None,
            position=entry.position,
            status=entry.status,
            offer_sent_at=entry.offer_sent_at,
            offer_expires_at=entry.offer_expires_at,
            created_at=entry.created_at
        ))
    
    return WaitlistStatusResponse(
        feis_id=str(feis.id),
        feis_name=feis.name,
        total_waiting=total,
        competition_waitlists=comp_waitlists,
        global_waitlist_count=global_count,
        user_waitlist_entries=user_entry_responses
    )


# --- Check-In ---

@router.post("/checkin", response_model=CheckInResponse)
async def check_in_dancer(
    request: CheckInRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Check in a dancer by entry ID."""
    result = check_in_entry(session, UUID(request.entry_id), current_user.id)
    
    return CheckInResponse(
        entry_id=result.entry_id,
        dancer_name=result.dancer_name,
        competitor_number=result.competitor_number,
        competition_name=result.competition_name,
        status=result.status,
        checked_in_at=datetime.utcnow() if result.success else None,
        message=result.message
    )


@router.post("/checkin/by-number", response_model=CheckInResponse)
async def check_in_by_competitor_number(
    competition_id: str,
    competitor_number: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Check in a dancer by competitor number."""
    result = check_in_by_number(
        session, UUID(competition_id), competitor_number, current_user.id
    )
    
    return CheckInResponse(
        entry_id=result.entry_id,
        dancer_name=result.dancer_name,
        competitor_number=result.competitor_number,
        competition_name=result.competition_name,
        status=result.status,
        checked_in_at=datetime.utcnow() if result.success else None,
        message=result.message
    )


@router.post("/checkin/bulk", response_model=BulkCheckInResponse)
async def bulk_check_in_endpoint(
    request: BulkCheckInRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Check in multiple dancers at once."""
    entry_uuids = [UUID(eid) for eid in request.entry_ids]
    results = bulk_check_in(session, entry_uuids, current_user.id)
    
    responses = [
        CheckInResponse(
            entry_id=r.entry_id,
            dancer_name=r.dancer_name,
            competitor_number=r.competitor_number,
            competition_name=r.competition_name,
            status=r.status,
            checked_in_at=datetime.utcnow() if r.success else None,
            message=r.message
        )
        for r in results
    ]
    
    successful = sum(1 for r in results if r.success)
    
    return BulkCheckInResponse(
        successful=successful,
        failed=len(results) - successful,
        results=responses
    )


@router.post("/checkin/{entry_id}/undo", response_model=CheckInResponse)
async def undo_check_in_endpoint(
    entry_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Undo a check-in."""
    result = undo_check_in(session, UUID(entry_id))
    
    return CheckInResponse(
        entry_id=result.entry_id,
        dancer_name=result.dancer_name,
        competitor_number=result.competitor_number,
        competition_name=result.competition_name,
        status=result.status,
        checked_in_at=None,
        message=result.message
    )


@router.get("/checkin/qr/{dancer_id}")
async def lookup_by_qr_code(
    dancer_id: str,
    feis_id: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """Look up entries for a dancer (from QR code scan)."""
    feis_uuid = UUID(feis_id) if feis_id else None
    entries = lookup_entry_by_qr(session, UUID(dancer_id), feis_uuid)
    
    results = []
    for entry in entries:
        dancer = session.get(Dancer, entry.dancer_id)
        competition = session.get(Competition, entry.competition_id)
        feis = session.get(Feis, competition.feis_id) if competition else None
        
        results.append({
            "entry_id": str(entry.id),
            "dancer_name": dancer.name if dancer else "Unknown",
            "competitor_number": entry.competitor_number,
            "competition_id": str(competition.id) if competition else None,
            "competition_name": competition.name if competition else "Unknown",
            "feis_name": feis.name if feis else "Unknown",
            "check_in_status": entry.check_in_status.value,
            "paid": entry.paid,
            "cancelled": entry.cancelled
        })
    
    return {"dancer_id": dancer_id, "entries": results}


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


@router.get("/feis/{feis_id}/checkin-summary")
async def get_feis_checkin_summary(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get check-in summary for all competitions in a feis."""
    return get_feis_check_in_summary(session, UUID(feis_id))


# --- Scratch / Refunds ---

@router.post("/entries/{entry_id}/scratch", response_model=ScratchEntryResponse)
async def scratch_entry_endpoint(
    entry_id: str,
    request: ScratchEntryRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Scratch (cancel) an entry with refund processing."""
    entry = session.get(Entry, UUID(entry_id))
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Verify user owns this entry (or is admin/organizer)
    dancer = session.get(Dancer, entry.dancer_id)
    competition = session.get(Competition, entry.competition_id)
    feis = session.get(Feis, competition.feis_id) if competition else None
    
    is_owner = dancer and dancer.parent_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    is_feis_owner = feis and feis.organizer_id == current_user.id
    
    if not (is_owner or is_admin or is_feis_owner):
        raise HTTPException(status_code=403, detail="Not authorized to scratch this entry")
    
    result = scratch_entry(session, UUID(entry_id), current_user.id, request.reason)
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return ScratchEntryResponse(
        entry_id=result.entry_id,
        dancer_name=result.dancer_name,
        competition_name=result.competition_name,
        refund_amount_cents=result.refund_amount_cents,
        message=result.message
    )


@router.get("/feis/{feis_id}/refund-policy")
async def get_feis_refund_policy(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """Get the refund policy for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    policy = get_refund_policy(session, UUID(feis_id))
    return {
        "feis_id": feis_id,
        "feis_name": feis.name,
        **policy
    }


@router.post("/orders/{order_id}/refund", response_model=RefundResponse)
async def refund_order(
    order_id: str,
    request: RefundRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Process a refund for an order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if request.entry_ids:
        # Partial refund
        entry_uuids = [UUID(eid) for eid in request.entry_ids]
        result = process_partial_refund(
            session, UUID(order_id), entry_uuids, current_user.id,
            request.reason, request.refund_amount_cents
        )
    else:
        # Full refund
        result = process_full_refund(
            session, UUID(order_id), current_user.id, request.reason
        )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    
    return RefundResponse(
        order_id=result.order_id,
        refund_amount_cents=result.refund_amount_cents,
        refund_type=result.refund_type,
        stripe_refund_id=result.stripe_refund_id,
        entries_refunded=result.entries_affected,
        message=result.message
    )


@router.get("/orders/{order_id}/refunds", response_model=OrderRefundSummary)
async def get_order_refunds(
    order_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Get refund summary for an order."""
    order = session.get(Order, UUID(order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify user owns this order or is admin
    is_owner = order.user_id == current_user.id
    is_admin = current_user.role in [RoleType.SUPER_ADMIN, RoleType.ORGANIZER]
    
    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    
    summary = get_order_refund_summary(session, UUID(order_id))
    
    logs = [
        RefundLogResponse(
            id=log["id"],
            order_id=order_id,
            entry_id=log.get("entry_name"),
            amount_cents=log["amount_cents"],
            reason=log["reason"],
            refund_type=log["refund_type"],
            processed_by_name=log["processed_by_name"],
            created_at=datetime.fromisoformat(log["created_at"])
        )
        for log in summary["refund_logs"]
    ]
    
    return OrderRefundSummary(
        order_id=order_id,
        original_total_cents=summary["original_total_cents"],
        refund_total_cents=summary["refund_total_cents"],
        remaining_cents=summary["remaining_cents"],
        status=PaymentStatus(summary["status"]),
        refund_logs=logs
    )


@router.get("/feis/{feis_id}/refund-stats")
async def get_feis_refund_statistics(
    feis_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """Get refund statistics for a feis."""
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    return get_feis_refund_stats(session, UUID(feis_id))


# ============= Adjudicator Roster Management (Phase 6) =============

@router.get("/feis/{feis_id}/adjudicators", response_model=AdjudicatorListResponse)
async def list_feis_adjudicators(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """
    Get all adjudicators on the roster for a feis.
    Public endpoint - anyone can view the roster.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    adjudicators = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == UUID(feis_id))
    ).all()
    
    # Build response with school affiliation names
    adjudicator_responses = []
    confirmed_count = 0
    invited_count = 0
    active_count = 0
    
    for adj in adjudicators:
        # Get school affiliation name if set
        school_name = None
        if adj.school_affiliation_id:
            school = session.get(User, adj.school_affiliation_id)
            if school:
                school_name = school.name
        
        # Count by status
        if adj.status == AdjudicatorStatus.CONFIRMED:
            confirmed_count += 1
        elif adj.status == AdjudicatorStatus.INVITED:
            invited_count += 1
        elif adj.status == AdjudicatorStatus.ACTIVE:
            active_count += 1
        
        adjudicator_responses.append(AdjudicatorResponse(
            id=str(adj.id),
            feis_id=str(adj.feis_id),
            user_id=str(adj.user_id) if adj.user_id else None,
            name=adj.name,
            email=adj.email,
            phone=adj.phone,
            credential=adj.credential,
            organization=adj.organization,
            school_affiliation_id=str(adj.school_affiliation_id) if adj.school_affiliation_id else None,
            school_affiliation_name=school_name,
            status=adj.status,
            invite_sent_at=adj.invite_sent_at,
            invite_expires_at=adj.invite_expires_at,
            has_access_pin=adj.access_pin_hash is not None,
            created_at=adj.created_at,
            confirmed_at=adj.confirmed_at
        ))
    
    return AdjudicatorListResponse(
        feis_id=feis_id,
        feis_name=feis.name,
        total_adjudicators=len(adjudicators),
        confirmed_count=confirmed_count,
        invited_count=invited_count,
        active_count=active_count,
        adjudicators=adjudicator_responses
    )


@router.post("/feis/{feis_id}/adjudicators", response_model=AdjudicatorResponse)
async def add_feis_adjudicator(
    feis_id: str,
    adjudicator_data: AdjudicatorCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Add an adjudicator to the feis roster.
    Requires organizer or admin role.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Verify user is the feis organizer or admin
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can add adjudicators")
    
    # Check if this adjudicator is already on the roster (by email or user_id)
    existing = None
    if adjudicator_data.email:
        existing = session.exec(
            select(FeisAdjudicator)
            .where(FeisAdjudicator.feis_id == UUID(feis_id))
            .where(FeisAdjudicator.email == adjudicator_data.email)
        ).first()
    
    if not existing and adjudicator_data.user_id:
        existing = session.exec(
            select(FeisAdjudicator)
            .where(FeisAdjudicator.feis_id == UUID(feis_id))
            .where(FeisAdjudicator.user_id == UUID(adjudicator_data.user_id))
        ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="This adjudicator is already on the roster")
    
    # Create the adjudicator
    adjudicator = FeisAdjudicator(
        feis_id=UUID(feis_id),
        user_id=UUID(adjudicator_data.user_id) if adjudicator_data.user_id else None,
        name=adjudicator_data.name,
        email=adjudicator_data.email,
        phone=adjudicator_data.phone,
        credential=adjudicator_data.credential,
        organization=adjudicator_data.organization,
        school_affiliation_id=UUID(adjudicator_data.school_affiliation_id) if adjudicator_data.school_affiliation_id else None,
        status=AdjudicatorStatus.CONFIRMED if adjudicator_data.user_id else AdjudicatorStatus.INVITED
    )
    
    session.add(adjudicator)
    session.commit()
    session.refresh(adjudicator)
    
    # Get school affiliation name
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


@router.get("/adjudicators/{adjudicator_id}", response_model=AdjudicatorResponse)
async def get_adjudicator(
    adjudicator_id: str,
    session: Session = Depends(get_session)
):
    """Get a specific adjudicator by ID."""
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Get school affiliation name
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
    """
    Update an adjudicator's details.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can update adjudicators")
    
    # Update fields
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
    
    # Get school affiliation name
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
    """
    Remove an adjudicator from the feis roster.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can remove adjudicators")
    
    # Check if adjudicator is assigned to any competitions
    assigned_comps = session.exec(
        select(Competition).where(Competition.adjudicator_id == adjudicator.user_id)
    ).all() if adjudicator.user_id else []
    
    if assigned_comps:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot remove adjudicator who is assigned to {len(assigned_comps)} competition(s). Unassign them first."
        )
    
    # Delete availability blocks first
    session.exec(
        select(AdjudicatorAvailability).where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))
    )
    for block in session.exec(select(AdjudicatorAvailability).where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))).all():
        session.delete(block)
    
    session.delete(adjudicator)
    session.commit()
    
    return {"message": "Adjudicator removed from roster", "adjudicator_id": adjudicator_id}


# --- Adjudicator Availability ---

@router.get("/adjudicators/{adjudicator_id}/availability", response_model=AdjudicatorAvailabilityResponse)
async def get_adjudicator_availability(
    adjudicator_id: str,
    session: Session = Depends(get_session)
):
    """
    Get all availability blocks for an adjudicator.
    Public endpoint.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    feis = session.get(Feis, adjudicator.feis_id)
    
    # Get availability blocks
    blocks = session.exec(
        select(AdjudicatorAvailability)
        .where(AdjudicatorAvailability.feis_adjudicator_id == UUID(adjudicator_id))
        .order_by(AdjudicatorAvailability.feis_day, AdjudicatorAvailability.start_time)
    ).all()
    
    # Calculate feis dates (for multi-day support - using feis.date as single day for now)
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
    """
    Create an availability block for an adjudicator.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    # Validate time range
    if block_data.start_time >= block_data.end_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    
    # Create the block
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
    """
    Create multiple availability blocks at once.
    Optionally replaces existing blocks for the specified days.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    # If replacing existing, delete blocks for the days being set
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
    
    # Create new blocks
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
    
    # Refresh and return
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
    """
    Update an availability block.
    Requires organizer or admin role.
    """
    block = session.get(AdjudicatorAvailability, UUID(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Availability block not found")
    
    # Verify user is the feis organizer or admin
    adjudicator = session.get(FeisAdjudicator, block.feis_adjudicator_id)
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    # Update fields
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
    
    # Validate time range
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
    """
    Delete an availability block.
    Requires organizer or admin role.
    """
    block = session.get(AdjudicatorAvailability, UUID(block_id))
    if not block:
        raise HTTPException(status_code=404, detail="Availability block not found")
    
    # Verify user is the feis organizer or admin
    adjudicator = session.get(FeisAdjudicator, block.feis_adjudicator_id)
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can manage adjudicator availability")
    
    session.delete(block)
    session.commit()
    
    return {"message": "Availability block deleted", "block_id": block_id}


# --- Adjudicator Invite Flow ---

@router.post("/adjudicators/{adjudicator_id}/invite", response_model=AdjudicatorInviteResponse)
async def send_adjudicator_invite(
    adjudicator_id: str,
    request: AdjudicatorInviteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Send or resend an invitation to an adjudicator.
    Generates a magic link token that can be used to accept the invite.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can send invites")
    
    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)  # Token valid for 7 days
    
    adjudicator.invite_token = invite_token
    adjudicator.invite_sent_at = datetime.utcnow()
    adjudicator.invite_expires_at = expires_at
    adjudicator.status = AdjudicatorStatus.INVITED
    
    session.add(adjudicator)
    session.commit()
    session.refresh(adjudicator)
    
    # Get site settings for URL
    settings = get_site_settings(session)
    site_url = settings.site_url if settings else "http://localhost:5173"
    invite_link = f"{site_url}/adjudicator-invite?token={invite_token}"
    
    # TODO: Send email with invite link if email is configured and adjudicator has email
    # For now, just return the link for manual sharing
    
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
    """
    Accept an adjudicator invitation via magic link.
    If the user is logged in, links their account to the roster entry.
    If not logged in, returns info for account creation.
    """
    # Find adjudicator by invite token
    adjudicator = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.invite_token == request.token)
    ).first()
    
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Invalid or expired invite token")
    
    # Check if token is expired
    if adjudicator.invite_expires_at and adjudicator.invite_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Invite token has expired. Please request a new invite.")
    
    feis = session.get(Feis, adjudicator.feis_id)
    
    if current_user:
        # Link existing account
        adjudicator.user_id = current_user.id
        adjudicator.status = AdjudicatorStatus.CONFIRMED
        adjudicator.confirmed_at = datetime.utcnow()
        adjudicator.invite_token = None  # Clear token after use
        
        # Update user role to adjudicator if they're just a parent
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
        # Not logged in - return info for the frontend to show login/register
        return AdjudicatorAcceptInviteResponse(
            success=True,
            feis_id=str(feis.id),
            feis_name=feis.name,
            adjudicator_name=adjudicator.name,
            message="Please log in or create an account to confirm your position as adjudicator",
            access_token=None,
            user=None
        )


# --- Day-of PIN Access ---

@router.post("/adjudicators/{adjudicator_id}/generate-pin", response_model=GeneratePinResponse)
async def generate_adjudicator_pin(
    adjudicator_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Generate a 6-digit PIN for day-of access.
    The PIN is only shown once and cannot be retrieved again.
    Requires organizer or admin role.
    """
    adjudicator = session.get(FeisAdjudicator, UUID(adjudicator_id))
    if not adjudicator:
        raise HTTPException(status_code=404, detail="Adjudicator not found")
    
    # Verify user is the feis organizer or admin
    feis = session.get(Feis, adjudicator.feis_id)
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can generate PINs")
    
    # Generate 6-digit PIN
    pin = ''.join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Hash the PIN for storage
    adjudicator.access_pin_hash = hash_password(pin)
    adjudicator.pin_generated_at = datetime.utcnow()
    
    session.add(adjudicator)
    session.commit()
    
    return GeneratePinResponse(
        success=True,
        adjudicator_id=adjudicator_id,
        adjudicator_name=adjudicator.name,
        pin=pin,  # Only shown once!
        message=f"PIN generated for {adjudicator.name}. Write it down - it cannot be shown again."
    )


@router.post("/adjudicator-login/pin", response_model=PinLoginResponse)
async def login_with_pin(
    request: PinLoginRequest,
    session: Session = Depends(get_session)
):
    """
    Login as an adjudicator using a day-of PIN.
    Creates a temporary session for scoring at the feis.
    """
    # Find adjudicators for this feis with a PIN set
    adjudicators = session.exec(
        select(FeisAdjudicator)
        .where(FeisAdjudicator.feis_id == UUID(request.feis_id))
        .where(FeisAdjudicator.access_pin_hash.isnot(None))
    ).all()
    
    # Try to find a matching PIN
    matched_adjudicator = None
    for adj in adjudicators:
        if verify_password(request.pin, adj.access_pin_hash):
            matched_adjudicator = adj
            break
    
    if not matched_adjudicator:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    
    feis = session.get(Feis, UUID(request.feis_id))
    
    # Mark adjudicator as active
    matched_adjudicator.status = AdjudicatorStatus.ACTIVE
    session.add(matched_adjudicator)
    
    # If adjudicator has a linked user account, use that for the token
    if matched_adjudicator.user_id:
        user = session.get(User, matched_adjudicator.user_id)
        access_token = create_access_token(user.id, user.role)
    else:
        # Create a temporary user or use a special token
        # For now, we'll create a simple session token
        # In production, you might want to create a temporary user record
        
        # Check if there's already a user with adjudicator role for this email
        if matched_adjudicator.email:
            existing_user = session.exec(
                select(User).where(User.email == matched_adjudicator.email)
            ).first()
            if existing_user:
                matched_adjudicator.user_id = existing_user.id
                session.add(matched_adjudicator)
                access_token = create_access_token(existing_user.id, existing_user.role)
            else:
                # Create a new adjudicator user
                temp_user = User(
                    email=matched_adjudicator.email or f"adj_{matched_adjudicator.id}@temp.openfeis.local",
                    password_hash=hash_password(secrets.token_urlsafe(32)),  # Random password
                    name=matched_adjudicator.name,
                    role=RoleType.ADJUDICATOR,
                    email_verified=True  # Skip verification for PIN-created accounts
                )
                session.add(temp_user)
                session.commit()
                session.refresh(temp_user)
                matched_adjudicator.user_id = temp_user.id
                session.add(matched_adjudicator)
                access_token = create_access_token(temp_user.id, temp_user.role)
        else:
            # No email - create with temporary identifier
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


# --- Adjudicator Capacity Metrics ---

@router.get("/feis/{feis_id}/adjudicator-capacity", response_model=AdjudicatorCapacityResponse)
async def get_adjudicator_capacity(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """
    Get derived scheduling capacity metrics based on the adjudicator roster.
    Shows how many stages/panels can run concurrently.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get adjudicator counts
    adjudicators = session.exec(
        select(FeisAdjudicator).where(FeisAdjudicator.feis_id == UUID(feis_id))
    ).all()
    
    total = len(adjudicators)
    confirmed = len([a for a in adjudicators if a.status == AdjudicatorStatus.CONFIRMED])
    active = len([a for a in adjudicators if a.status == AdjudicatorStatus.ACTIVE])
    
    # Get scheduling defaults from feis settings (or use defaults)
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    # Default values if not set
    grades_per_stage = getattr(settings, 'grades_judges_per_stage', None) or 1
    champs_per_panel = getattr(settings, 'champs_judges_per_panel', None) or 3
    
    # Calculate capacity based on confirmed + active judges
    available_judges = confirmed + active
    
    # Maximum concurrent operations
    max_grade_stages = available_judges // grades_per_stage if grades_per_stage > 0 else 0
    max_champs_panels = available_judges // champs_per_panel if champs_per_panel > 0 else 0
    
    # Generate recommendation
    if available_judges == 0:
        recommendation = "No confirmed adjudicators yet. Add adjudicators to your roster to enable scheduling."
    elif available_judges < champs_per_panel:
        recommendation = f"With {available_judges} adjudicator(s), you can run up to {max_grade_stages} single-judge stage(s). You need at least {champs_per_panel} judges for championship panels."
    else:
        # Calculate mixed scenarios
        remaining_after_one_panel = available_judges - champs_per_panel
        grades_with_one_panel = remaining_after_one_panel // grades_per_stage
        
        recommendation = (
            f"With {available_judges} confirmed adjudicator(s), you can run:\n"
            f"- Up to {max_grade_stages} single-judge grade stages, OR\n"
            f"- Up to {max_champs_panels} championship panel(s) ({champs_per_panel} judges each), OR\n"
            f"- 1 championship panel + {grades_with_one_panel} grade stage(s)"
        )
    
    return AdjudicatorCapacityResponse(
        feis_id=feis_id,
        feis_name=feis.name,
        total_adjudicators=total,
        confirmed_count=confirmed,
        active_count=active,
        grades_judges_per_stage=grades_per_stage,
        champs_judges_per_panel=champs_per_panel,
        max_grade_stages=max_grade_stages,
        max_champs_panels=max_champs_panels,
        recommendation=recommendation
    )


# --- Scheduling Defaults ---

@router.get("/feis/{feis_id}/scheduling-defaults", response_model=SchedulingDefaultsResponse)
async def get_scheduling_defaults(
    feis_id: str,
    session: Session = Depends(get_session)
):
    """
    Get scheduling defaults for a feis.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Get or create settings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    if not settings:
        # Return defaults if no settings exist
        return SchedulingDefaultsResponse(
            feis_id=feis_id,
            grades_judges_per_stage=1,
            champs_judges_per_panel=3,
            lunch_duration_minutes=30,
            lunch_window_start=None,
            lunch_window_end=None
        )
    
    return SchedulingDefaultsResponse(
        feis_id=feis_id,
        grades_judges_per_stage=settings.grades_judges_per_stage,
        champs_judges_per_panel=settings.champs_judges_per_panel,
        lunch_duration_minutes=settings.lunch_duration_minutes,
        lunch_window_start=settings.lunch_window_start,
        lunch_window_end=settings.lunch_window_end
    )


@router.put("/feis/{feis_id}/scheduling-defaults", response_model=SchedulingDefaultsResponse)
async def update_scheduling_defaults(
    feis_id: str,
    update_data: SchedulingDefaultsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(require_organizer_or_admin())
):
    """
    Update scheduling defaults for a feis.
    Requires organizer or admin role.
    """
    feis = session.get(Feis, UUID(feis_id))
    if not feis:
        raise HTTPException(status_code=404, detail="Feis not found")
    
    # Verify user is the feis organizer or admin
    if current_user.role != RoleType.SUPER_ADMIN and feis.organizer_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the feis organizer can update scheduling defaults")
    
    # Get or create settings
    settings = session.exec(
        select(FeisSettings).where(FeisSettings.feis_id == UUID(feis_id))
    ).first()
    
    if not settings:
        settings = FeisSettings(feis_id=UUID(feis_id))
        session.add(settings)
    
    # Update fields
    if update_data.grades_judges_per_stage is not None:
        settings.grades_judges_per_stage = update_data.grades_judges_per_stage
    if update_data.champs_judges_per_panel is not None:
        settings.champs_judges_per_panel = update_data.champs_judges_per_panel
    if update_data.lunch_duration_minutes is not None:
        settings.lunch_duration_minutes = update_data.lunch_duration_minutes
    if update_data.lunch_window_start is not None:
        from datetime import time as time_type
        settings.lunch_window_start = time_type.fromisoformat(update_data.lunch_window_start) if isinstance(update_data.lunch_window_start, str) else update_data.lunch_window_start
    if update_data.lunch_window_end is not None:
        from datetime import time as time_type
        settings.lunch_window_end = time_type.fromisoformat(update_data.lunch_window_end) if isinstance(update_data.lunch_window_end, str) else update_data.lunch_window_end
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    
    return SchedulingDefaultsResponse(
        feis_id=feis_id,
        grades_judges_per_stage=settings.grades_judges_per_stage,
        champs_judges_per_panel=settings.champs_judges_per_panel,
        lunch_duration_minutes=settings.lunch_duration_minutes,
        lunch_window_start=settings.lunch_window_start,
        lunch_window_end=settings.lunch_window_end
    )


# ============= Demo Data Endpoints (Super Admin Only) =============

from backend.api.schemas import DemoDataSummary, DemoDataStatus
from backend.services.demo_data import populate_demo_data, delete_demo_data, has_demo_data


@router.get("/admin/demo-data/status", response_model=DemoDataStatus)
async def get_demo_data_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Check if demo data exists in the system.
    Super Admin only.
    """
    has_data = has_demo_data(session)
    return DemoDataStatus(
        has_demo_data=has_data,
        message="Demo data is present in the database." if has_data else "No demo data found."
    )


@router.post("/admin/demo-data/populate", response_model=DemoDataSummary)
async def populate_demo_data_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Populate the database with comprehensive demo data.
    
    Creates:
    - 1 demo organizer, 8 teachers, 6 adjudicators
    - 3 feiseanna:
      - Shamrock Classic Feis (60 days out, ~250 dancers)
      - Celtic Pride Championships (90 days out, ~103 dancers)  
      - Emerald Isle Fall Feis (7 days ago, ~100 dancers, with complete results)
    - Full syllabus with competitions for each feis
    - Realistic registrations, schedules, and (for past feis) scores
    
    Super Admin only.
    """
    if has_demo_data(session):
        return DemoDataSummary(
            success=False,
            message="Demo data already exists. Delete existing demo data first."
        )
    
    try:
        summary = populate_demo_data(session)
        return DemoDataSummary(
            success=True,
            message=f"Successfully created demo data: {summary['feiseanna']} feiseanna, {summary['dancers']} dancers, {summary['entries']} entries.",
            **summary
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to populate demo data: {str(e)}"
        )


@router.delete("/admin/demo-data", response_model=DemoDataSummary)
async def delete_demo_data_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(require_admin)
):
    """
    Delete all demo data from the database.
    
    Identifies demo data by email patterns (demo_*@openfeis.demo).
    This will delete:
    - All demo users (organizers, teachers, parents, adjudicators)
    - All feiseanna created by demo organizers
    - All dancers belonging to demo parents
    - All associated entries, scores, etc.
    
    Super Admin only.
    """
    if not has_demo_data(session):
        return DemoDataSummary(
            success=False,
            message="No demo data found to delete."
        )
    
    try:
        summary = delete_demo_data(session)
        return DemoDataSummary(
            success=True,
            message=f"Successfully deleted demo data: {summary['users_deleted']} users, {summary['feiseanna_deleted']} feiseanna, {summary['dancers_deleted']} dancers.",
            feiseanna=summary["feiseanna_deleted"],
            dancers=summary["dancers_deleted"],
            entries=summary["entries_deleted"],
            scores=summary["scores_deleted"]
        )
    except Exception as e:
        session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete demo data: {str(e)}"
        )
