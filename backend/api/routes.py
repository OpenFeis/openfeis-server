from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import StreamingResponse
from typing import List, Optional
from uuid import UUID
from datetime import date
from sqlmodel import Session, select, func
from backend.scoring_engine.models import JudgeScore, RoundResult, Round
from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry, CompetitionLevel, RoleType
from backend.scoring_engine.calculator import IrishPointsCalculator
from backend.db.database import get_session
from backend.api.schemas import (
    SyllabusGenerationRequest, SyllabusGenerationResponse,
    FeisCreate, FeisUpdate, FeisResponse,
    CompetitionCreate, CompetitionUpdate, CompetitionResponse,
    EntryUpdate, EntryResponse, BulkNumberAssignment, BulkNumberAssignmentResponse,
    DancerResponse, UserUpdate, UserResponse,
    LoginRequest, RegisterRequest, AuthResponse
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
            role=user.role
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
            role=user.role
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
        role=RoleType.PARENT  # Default role
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Create access token for auto-login
    access_token = create_access_token(user.id, user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role
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
        role=current_user.role
    )

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
                paid=entry.paid
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
        paid=entry.paid
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
        role=user.role
    )

# ============= Dancer Endpoints (for entry management) =============

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
            parent_id=str(d.parent_id)
        )
        for d in dancers
    ]


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
