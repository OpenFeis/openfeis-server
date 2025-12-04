from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID
from backend.scoring_engine.models_platform import CompetitionLevel, Gender, RoleType, DanceType, ScoringMethod

# ============= Syllabus Generation =============

class SyllabusGenerationRequest(BaseModel):
    feis_id: str
    levels: List[CompetitionLevel]
    min_age: int
    max_age: int
    genders: List[Gender]
    dances: List[str] = ["Reel", "Light Jig", "Slip Jig", "Treble Jig", "Hornpipe"]
    # New options
    price_cents: int = 1000  # Default $10.00 per competition
    scoring_method: ScoringMethod = ScoringMethod.SOLO

class SyllabusGenerationResponse(BaseModel):
    generated_count: int
    message: str

# ============= Feis CRUD =============

class FeisCreate(BaseModel):
    name: str
    date: date
    location: str
    organizer_id: Optional[str] = None  # Will use current user if not provided

class FeisUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[date] = None
    location: Optional[str] = None
    stripe_account_id: Optional[str] = None

class FeisResponse(BaseModel):
    id: str
    name: str
    date: date
    location: str
    organizer_id: str
    stripe_account_id: Optional[str] = None
    competition_count: int = 0
    entry_count: int = 0

    class Config:
        from_attributes = True

# ============= Competition CRUD =============

class CompetitionCreate(BaseModel):
    feis_id: str
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: int = 48
    scoring_method: ScoringMethod = ScoringMethod.SOLO
    price_cents: int = 1000
    max_entries: Optional[int] = None

class CompetitionUpdate(BaseModel):
    name: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    level: Optional[CompetitionLevel] = None
    gender: Optional[Gender] = None
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: Optional[int] = None
    scoring_method: Optional[ScoringMethod] = None
    price_cents: Optional[int] = None
    max_entries: Optional[int] = None
    stage_id: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    adjudicator_id: Optional[str] = None

class CompetitionResponse(BaseModel):
    id: str
    feis_id: str
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    entry_count: int = 0
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: int = 48
    scoring_method: ScoringMethod = ScoringMethod.SOLO
    price_cents: int = 1000
    max_entries: Optional[int] = None
    stage_id: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    adjudicator_id: Optional[str] = None

    class Config:
        from_attributes = True


# ============= Stage CRUD =============

class StageCreate(BaseModel):
    feis_id: str
    name: str
    color: Optional[str] = None  # Hex color, e.g., "#FF5733"
    sequence: int = 0

class StageUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    sequence: Optional[int] = None

class StageResponse(BaseModel):
    id: str
    feis_id: str
    name: str
    color: Optional[str] = None
    sequence: int = 0
    competition_count: int = 0

    class Config:
        from_attributes = True


# ============= Entry Management =============

class EntryCreate(BaseModel):
    """Request to create a single entry (dancer registering for a competition)."""
    dancer_id: str
    competition_id: str
    pay_later: bool = False  # If True, entry is created with paid=False


class BulkEntryCreate(BaseModel):
    """Request to create multiple entries at once (registration checkout)."""
    dancer_id: str
    competition_ids: List[str]
    pay_later: bool = False  # "Pay at Door" option


class BulkEntryResponse(BaseModel):
    """Response after creating multiple entries."""
    created_count: int
    entries: List["EntryResponse"]
    message: str


class EntryUpdate(BaseModel):
    competitor_number: Optional[int] = None
    paid: Optional[bool] = None


class EntryResponse(BaseModel):
    id: str
    dancer_id: str
    dancer_name: str
    dancer_school: Optional[str] = None
    competition_id: str
    competition_name: str
    competitor_number: Optional[int] = None
    paid: bool
    pay_later: bool = False  # Indicates if this was a "pay at door" registration

    class Config:
        from_attributes = True

class BulkNumberAssignment(BaseModel):
    start_number: int = 100
    feis_id: str

class BulkNumberAssignmentResponse(BaseModel):
    assigned_count: int
    message: str

# ============= Dancer CRUD =============

class DancerCreate(BaseModel):
    """Request to create a new dancer profile."""
    name: str
    dob: date
    gender: Gender
    current_level: CompetitionLevel
    clrg_number: Optional[str] = None
    school_id: Optional[str] = None


class DancerUpdate(BaseModel):
    """Request to update an existing dancer profile."""
    name: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[Gender] = None
    current_level: Optional[CompetitionLevel] = None
    clrg_number: Optional[str] = None
    school_id: Optional[str] = None


class DancerResponse(BaseModel):
    id: str
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str] = None
    parent_id: str
    school_id: Optional[str] = None

    class Config:
        from_attributes = True

# ============= User Management =============

class ProfileUpdate(BaseModel):
    """Request to update current user's own profile."""
    name: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Request to change current user's password."""
    current_password: str
    new_password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[RoleType] = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: RoleType
    email_verified: bool = False

    class Config:
        from_attributes = True

# ============= Authentication =============

class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenPayload(BaseModel):
    sub: str  # user_id
    role: str
    exp: int  # expiration timestamp


# ============= Email Verification =============

class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: str


class VerificationResponse(BaseModel):
    success: bool
    message: str


# ============= Site Settings (Admin) =============

class SiteSettingsUpdate(BaseModel):
    resend_api_key: Optional[str] = None
    resend_from_email: Optional[str] = None
    site_name: Optional[str] = None
    site_url: Optional[str] = None


class SiteSettingsResponse(BaseModel):
    resend_configured: bool  # Don't expose actual API key
    resend_from_email: str
    site_name: str
    site_url: str

    class Config:
        from_attributes = True


# ============= Scoring / Judge Pad =============

class CompetitorForScoring(BaseModel):
    """A competitor (entry) ready to be scored by a judge."""
    entry_id: str
    competitor_number: int
    dancer_name: str
    dancer_school: Optional[str] = None
    existing_score: Optional[float] = None
    existing_notes: Optional[str] = None

    class Config:
        from_attributes = True


class CompetitionForScoring(BaseModel):
    """Competition info for the judge's scoring interface."""
    id: str
    name: str
    feis_id: str
    feis_name: str
    level: CompetitionLevel
    competitor_count: int

    class Config:
        from_attributes = True


class ScoreSubmission(BaseModel):
    """Request to submit a score for a competitor."""
    entry_id: str  # The Entry ID (competitor in this competition)
    competition_id: str  # The Competition being scored
    value: float  # Score 0-100
    notes: Optional[str] = None  # Optional judge notes


class ScoreSubmissionResponse(BaseModel):
    """Response after submitting a score."""
    id: str
    entry_id: str
    competition_id: str
    value: float
    notes: Optional[str] = None
    timestamp: str

    class Config:
        from_attributes = True


# ============= Tabulator / Results =============

class TabulatorResultItem(BaseModel):
    """A single competitor's result for display in the tabulator."""
    rank: int
    competitor_number: Optional[int] = None
    dancer_name: str
    dancer_school: Optional[str] = None
    irish_points: float
    is_recalled: bool = False  # Whether this competitor recalls to next round

    class Config:
        from_attributes = True


class TabulatorResults(BaseModel):
    """Full results for a competition, ready for tabulator display."""
    competition_id: str
    competition_name: str
    feis_name: str
    total_competitors: int
    total_scores: int  # Number of scores submitted
    judge_count: int  # Number of unique judges who have scored
    results: List[TabulatorResultItem]

    class Config:
        from_attributes = True


class CompetitionWithScores(BaseModel):
    """Competition info for tabulator selection - only shows comps with scores."""
    id: str
    name: str
    feis_id: str
    feis_name: str
    level: CompetitionLevel
    entry_count: int
    score_count: int  # How many scores have been submitted

    class Config:
        from_attributes = True


# ============= Scheduling / Duration Estimation =============

class DurationEstimateRequest(BaseModel):
    """Request to estimate competition duration."""
    entry_count: int
    bars: int = 48
    tempo_bpm: int = 113
    dancers_per_rotation: int = 2
    setup_time_minutes: int = 2

class DurationEstimateResponse(BaseModel):
    """Estimated duration for a competition."""
    estimated_minutes: int
    rotations: int
    breakdown: str  # Human-readable breakdown


class ScheduleCompetitionRequest(BaseModel):
    """Request to schedule a competition on a stage."""
    competition_id: str
    stage_id: str
    scheduled_time: datetime


class BulkScheduleRequest(BaseModel):
    """Request to schedule multiple competitions at once."""
    schedules: List[ScheduleCompetitionRequest]


class BulkScheduleResponse(BaseModel):
    """Response after bulk scheduling."""
    scheduled_count: int
    conflicts: List["ScheduleConflict"]
    message: str


# ============= Conflict Detection =============

class ConflictType(str):
    """Types of scheduling conflicts."""
    SIBLING = "sibling"           # Same family on multiple stages at same time
    ADJUDICATOR = "adjudicator"   # Judge assigned to their own students
    TIME_OVERLAP = "time_overlap" # Same dancer in overlapping competitions


class ScheduleConflict(BaseModel):
    """A detected scheduling conflict."""
    conflict_type: str  # sibling, adjudicator, time_overlap
    severity: str  # warning, error (blocking)
    message: str
    affected_competition_ids: List[str]
    affected_dancer_ids: List[str] = []
    affected_stage_ids: List[str] = []


class ConflictCheckResponse(BaseModel):
    """Response from conflict detection."""
    has_conflicts: bool
    warning_count: int
    error_count: int
    conflicts: List[ScheduleConflict]


# ============= Scheduler View Data =============

class ScheduledCompetition(BaseModel):
    """Competition data for the Gantt scheduler view."""
    id: str
    name: str
    stage_id: Optional[str] = None
    stage_name: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    estimated_duration_minutes: int
    entry_count: int
    level: CompetitionLevel
    dance_type: Optional[DanceType] = None
    has_conflicts: bool = False

    class Config:
        from_attributes = True


class SchedulerViewResponse(BaseModel):
    """Full data for the scheduler view."""
    feis_id: str
    feis_name: str
    feis_date: date
    stages: List[StageResponse]
    competitions: List[ScheduledCompetition]
    conflicts: List[ScheduleConflict]
