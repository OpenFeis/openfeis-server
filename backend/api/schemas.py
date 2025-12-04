from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime
from uuid import UUID
from backend.scoring_engine.models_platform import (
    CompetitionLevel, Gender, RoleType, DanceType, ScoringMethod,
    FeeCategory, PaymentStatus
)

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


# ============= Financial Engine (Phase 3) =============

class FeisSettingsCreate(BaseModel):
    """Request to create feis settings."""
    feis_id: str
    base_entry_fee_cents: int = 2500
    per_competition_fee_cents: int = 1000
    family_max_cents: Optional[int] = 15000
    late_fee_cents: int = 500
    late_fee_date: Optional[date] = None
    change_fee_cents: int = 1000
    registration_opens: Optional[datetime] = None
    registration_closes: Optional[datetime] = None


class FeisSettingsUpdate(BaseModel):
    """Request to update feis settings."""
    base_entry_fee_cents: Optional[int] = None
    per_competition_fee_cents: Optional[int] = None
    family_max_cents: Optional[int] = None  # Use -1 to remove cap
    late_fee_cents: Optional[int] = None
    late_fee_date: Optional[date] = None
    change_fee_cents: Optional[int] = None
    registration_opens: Optional[datetime] = None
    registration_closes: Optional[datetime] = None


class FeisSettingsResponse(BaseModel):
    """Response with feis settings."""
    id: str
    feis_id: str
    base_entry_fee_cents: int
    per_competition_fee_cents: int
    family_max_cents: Optional[int]
    late_fee_cents: int
    late_fee_date: Optional[date]
    change_fee_cents: int
    registration_opens: Optional[datetime]
    registration_closes: Optional[datetime]
    # Stripe status
    stripe_account_id: Optional[str]
    stripe_onboarding_complete: bool

    class Config:
        from_attributes = True


class FeeItemCreate(BaseModel):
    """Request to create a fee item."""
    feis_id: str
    name: str
    description: Optional[str] = None
    amount_cents: int
    category: FeeCategory = FeeCategory.NON_QUALIFYING
    required: bool = False
    max_quantity: int = 1


class FeeItemUpdate(BaseModel):
    """Request to update a fee item."""
    name: Optional[str] = None
    description: Optional[str] = None
    amount_cents: Optional[int] = None
    category: Optional[FeeCategory] = None
    required: Optional[bool] = None
    max_quantity: Optional[int] = None
    active: Optional[bool] = None


class FeeItemResponse(BaseModel):
    """Response with fee item details."""
    id: str
    feis_id: str
    name: str
    description: Optional[str]
    amount_cents: int
    category: FeeCategory
    required: bool
    max_quantity: int
    active: bool

    class Config:
        from_attributes = True


# ============= Cart & Checkout =============

class CartLineItemResponse(BaseModel):
    """A single line item in the cart."""
    id: str
    type: str  # 'competition', 'base_fee', or 'fee_item'
    name: str
    description: Optional[str]
    dancer_id: Optional[str]
    dancer_name: Optional[str]
    unit_price_cents: int
    quantity: int
    total_cents: int
    category: FeeCategory


class CartCalculationRequest(BaseModel):
    """Request to calculate cart totals."""
    feis_id: str
    items: List["CartItemRequest"]
    fee_items: Optional[dict] = None  # {fee_item_id: quantity}


class CartItemRequest(BaseModel):
    """A single item in the cart calculation request."""
    competition_id: str
    dancer_id: str


class CartCalculationResponse(BaseModel):
    """Response with calculated cart totals."""
    line_items: List[CartLineItemResponse]
    
    # Subtotals
    qualifying_subtotal_cents: int
    non_qualifying_subtotal_cents: int
    subtotal_cents: int
    
    # Discounts
    family_discount_cents: int
    family_cap_applied: bool
    family_cap_cents: Optional[int]
    
    # Late fee
    late_fee_cents: int
    late_fee_applied: bool
    late_fee_date: Optional[date]
    
    # Final
    total_cents: int
    
    # Info
    dancer_count: int
    competition_count: int
    savings_percent: int

    class Config:
        from_attributes = True


class CheckoutRequest(BaseModel):
    """Request to start checkout."""
    feis_id: str
    items: List[CartItemRequest]
    fee_items: Optional[dict] = None
    pay_at_door: bool = False


class CheckoutResponse(BaseModel):
    """Response from checkout initiation."""
    success: bool
    order_id: Optional[str]
    checkout_url: Optional[str]  # URL to redirect to for payment
    is_test_mode: bool
    message: str


class OrderResponse(BaseModel):
    """Response with order details."""
    id: str
    feis_id: str
    user_id: str
    subtotal_cents: int
    qualifying_subtotal_cents: int
    non_qualifying_subtotal_cents: int
    family_discount_cents: int
    late_fee_cents: int
    total_cents: int
    status: PaymentStatus
    created_at: datetime
    paid_at: Optional[datetime]
    entry_count: int

    class Config:
        from_attributes = True


class RegistrationStatusResponse(BaseModel):
    """Response with registration status for a feis."""
    is_open: bool
    message: str
    opens_at: Optional[datetime]
    closes_at: Optional[datetime]
    is_late: bool
    late_fee_cents: int
    stripe_enabled: bool
    payment_methods: List[str]  # ['stripe', 'pay_at_door']


class StripeOnboardingRequest(BaseModel):
    """Request to start Stripe Connect onboarding."""
    feis_id: str
    return_url: str
    refresh_url: str


class StripeOnboardingResponse(BaseModel):
    """Response with Stripe onboarding URL."""
    success: bool
    onboarding_url: Optional[str]
    is_test_mode: bool
    error: Optional[str]


class StripeStatusResponse(BaseModel):
    """Response with Stripe configuration status."""
    stripe_configured: bool  # Global Stripe config
    stripe_mode: str  # 'live', 'test', or 'disabled'
    feis_connected: bool  # This feis has connected account
    onboarding_complete: bool
    message: str


# ============= Phase 4: Teacher Portal & Advancement =============

# --- Placement History ---

class PlacementHistoryCreate(BaseModel):
    """Request to record a placement (usually auto-created when results finalized)."""
    dancer_id: str
    competition_id: str
    feis_id: str
    entry_id: Optional[str] = None
    rank: int
    irish_points: Optional[float] = None
    dance_type: Optional[DanceType] = None
    level: CompetitionLevel
    competition_date: date


class PlacementHistoryResponse(BaseModel):
    """Response with placement history record."""
    id: str
    dancer_id: str
    dancer_name: str
    competition_id: str
    competition_name: str
    feis_id: str
    feis_name: str
    rank: int
    irish_points: Optional[float]
    dance_type: Optional[DanceType]
    level: CompetitionLevel
    competition_date: date
    triggered_advancement: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DancerPlacementHistoryResponse(BaseModel):
    """Response with all placement history for a dancer."""
    dancer_id: str
    dancer_name: str
    total_placements: int
    first_place_count: int
    placements: List[PlacementHistoryResponse]


# --- Advancement ---

class AdvancementRuleInfo(BaseModel):
    """Information about an advancement rule."""
    level: CompetitionLevel
    wins_required: int
    next_level: CompetitionLevel
    per_dance: bool  # True = advances only for that dance, False = advances for all
    description: str


class AdvancementNoticeResponse(BaseModel):
    """Response with an advancement notice."""
    id: str
    dancer_id: str
    dancer_name: str
    from_level: CompetitionLevel
    to_level: CompetitionLevel
    dance_type: Optional[DanceType]  # None = all dances
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    overridden: bool
    override_reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AdvancementCheckResponse(BaseModel):
    """Response from checking a dancer's advancement status."""
    dancer_id: str
    dancer_name: str
    current_level: CompetitionLevel
    pending_advancements: List[AdvancementNoticeResponse]
    eligible_levels: List[CompetitionLevel]  # Levels this dancer can register for
    warnings: List[str]  # Any warnings about level eligibility


class AcknowledgeAdvancementRequest(BaseModel):
    """Request to acknowledge an advancement notice."""
    advancement_id: str


class OverrideAdvancementRequest(BaseModel):
    """Request to override (bypass) an advancement requirement."""
    advancement_id: str
    reason: str


# --- Entry Flagging ---

class EntryFlagCreate(BaseModel):
    """Request to flag an entry for review."""
    entry_id: str
    reason: str
    flag_type: str = "level_incorrect"  # level_incorrect, school_wrong, other


class EntryFlagResponse(BaseModel):
    """Response with entry flag details."""
    id: str
    entry_id: str
    dancer_name: str
    competition_name: str
    flagged_by: str
    flagged_by_name: str
    reason: str
    flag_type: str
    resolved: bool
    resolved_by: Optional[str]
    resolved_by_name: Optional[str]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ResolveFlagRequest(BaseModel):
    """Request to resolve a flagged entry."""
    flag_id: str
    resolution_note: str


class FlaggedEntriesResponse(BaseModel):
    """Response with all flagged entries for a feis."""
    feis_id: str
    feis_name: str
    total_flags: int
    unresolved_count: int
    flags: List[EntryFlagResponse]


# --- Teacher Dashboard ---

class TeacherStudentEntry(BaseModel):
    """An entry belonging to a student of the teacher."""
    entry_id: str
    dancer_id: str
    dancer_name: str
    competition_id: str
    competition_name: str
    level: CompetitionLevel
    competitor_number: Optional[int]
    paid: bool
    feis_id: str
    feis_name: str
    feis_date: date
    is_flagged: bool
    flag_id: Optional[str] = None


class SchoolRosterResponse(BaseModel):
    """Response with all students linked to a teacher's school."""
    school_id: str
    teacher_name: str
    total_students: int
    students: List["SchoolStudentInfo"]


class SchoolStudentInfo(BaseModel):
    """Information about a student in the school roster."""
    id: str
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    parent_name: str
    entry_count: int
    pending_advancements: int

    class Config:
        from_attributes = True


class TeacherDashboardResponse(BaseModel):
    """Response for the teacher dashboard."""
    teacher_id: str
    teacher_name: str
    total_students: int
    total_entries: int
    entries_by_feis: dict  # {feis_id: count}
    pending_advancements: int
    recent_entries: List[TeacherStudentEntry]


class TeacherEntriesExportRequest(BaseModel):
    """Request to export teacher's student entries."""
    feis_id: Optional[str] = None  # None = all feiseanna
    format: str = "csv"  # csv or json


class LinkDancerToSchoolRequest(BaseModel):
    """Request to link a dancer to a school (teacher)."""
    dancer_id: str
    school_id: str  # Teacher's user ID
