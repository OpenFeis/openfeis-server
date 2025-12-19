from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import date as Date, datetime as DateTime, time as Time
from uuid import UUID
from backend.scoring_engine.models_platform import (
    CompetitionLevel, Gender, RoleType, DanceType, ScoringMethod,
    FeeCategory, PaymentStatus, AdjudicatorStatus, AvailabilityType,
    CompetitionCategory
)

# ============= Syllabus Generation =============

class SyllabusGenerationRequest(BaseModel):
    feis_id: str
    levels: List[CompetitionLevel]
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    selected_ages: Optional[List[str]] = None  # e.g., ["U6", "U7", "O15", "Adult"]
    genders: List[Gender]
    dances: List[str] = ["Reel", "Light Jig", "Slip Jig", "Treble Jig", "Hornpipe"]
    # New options
    price_cents: int = 1000  # Default $10.00 per competition
    scoring_method: ScoringMethod = ScoringMethod.SOLO
    # Figure/Ceili dances
    figure_dances: Optional[List[str]] = None  # ["2-Hand", "3-Hand", "4-Hand", "6-Hand", "8-Hand"]
    include_mixed_figure: bool = True  # Include mixed-gender figure competitions
    # Championships
    include_championships: bool = False
    championship_types: Optional[List[str]] = None  # ["prelim", "open"]

class SyllabusGenerationResponse(BaseModel):
    generated_count: int
    message: str

# ============= Feis CRUD =============

class FeisCreate(BaseModel):
    name: str
    date: Date
    location: str
    organizer_id: Optional[str] = None  # Will use current user if not provided

class FeisUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[Date] = None
    location: Optional[str] = None
    stripe_account_id: Optional[str] = None

class FeisResponse(BaseModel):
    id: UUID
    name: str
    date: Date
    location: str
    organizer_id: UUID
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
    code: Optional[str] = None  # Display code (e.g., "407SJ") - auto-generated if not provided
    description: Optional[str] = None
    allowed_levels: Optional[List[CompetitionLevel]] = None  # List of levels for special comps
    # Competition category (solo, figure, championship)
    category: CompetitionCategory = CompetitionCategory.SOLO
    is_mixed: bool = False  # For figure dances - mixed gender team
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: int = 48
    scoring_method: ScoringMethod = ScoringMethod.SOLO
    price_cents: int = 1000
    max_entries: Optional[int] = None
    description: Optional[str] = None
    allowed_levels: Optional[List[CompetitionLevel]] = None

class CompetitionUpdate(BaseModel):
    name: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    level: Optional[CompetitionLevel] = None
    gender: Optional[Gender] = None
    code: Optional[str] = None  # Display code - set to override auto-generated
    description: Optional[str] = None
    allowed_levels: Optional[List[CompetitionLevel]] = None
    # Competition category
    category: Optional[CompetitionCategory] = None
    is_mixed: Optional[bool] = None
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: Optional[int] = None
    scoring_method: Optional[ScoringMethod] = None
    price_cents: Optional[int] = None
    max_entries: Optional[int] = None
    stage_id: Optional[str] = None
    scheduled_time: Optional[DateTime] = None
    estimated_duration_minutes: Optional[int] = None
    adjudicator_id: Optional[str] = None
    panel_id: Optional[str] = None

class CompetitionResponse(BaseModel):
    id: str
    feis_id: str
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    code: Optional[str] = None  # Display code (e.g., "407SJ")
    # Competition category
    category: CompetitionCategory = CompetitionCategory.SOLO
    is_mixed: bool = False
    entry_count: int = 0
    # New scheduling fields
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None
    bars: int = 48
    scoring_method: ScoringMethod = ScoringMethod.SOLO
    price_cents: int = 1000
    max_entries: Optional[int] = None
    stage_id: Optional[str] = None
    scheduled_time: Optional[DateTime] = None
    estimated_duration_minutes: Optional[int] = None
    adjudicator_id: Optional[str] = None  # Single judge for solo events
    panel_id: Optional[str] = None  # Panel for championship events (all members score)
    description: Optional[str] = None
    allowed_levels: Optional[List[CompetitionLevel]] = None

    @field_validator("allowed_levels", mode="before")
    @classmethod
    def parse_allowed_levels(cls, v):
        if isinstance(v, str):
            return [CompetitionLevel(l) for l in v.split(",") if l]
        return v

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


# ============= Stage Judge Coverage =============

class StageJudgeCoverageCreate(BaseModel):
    """Create a time-based judge or panel assignment to a stage."""
    feis_adjudicator_id: Optional[str] = None  # For single judge assignment
    panel_id: Optional[str] = None  # For panel assignment
    feis_day: str  # ISO date string (YYYY-MM-DD)
    start_time: str  # HH:MM format
    end_time: str    # HH:MM format
    note: Optional[str] = None

class StageJudgeCoverageResponse(BaseModel):
    id: str
    stage_id: str
    stage_name: str
    feis_adjudicator_id: Optional[str] = None
    adjudicator_name: Optional[str] = None
    panel_id: Optional[str] = None
    panel_name: Optional[str] = None
    is_panel: bool = False  # True if this is a panel assignment
    feis_day: str
    start_time: str
    end_time: str
    note: Optional[str] = None

    class Config:
        from_attributes = True

class StageResponse(BaseModel):
    id: str
    feis_id: str
    name: str
    color: Optional[str] = None
    sequence: int = 0
    competition_count: int = 0
    # Coverage blocks for this stage
    judge_coverage: List[StageJudgeCoverageResponse] = []

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
    dob: Date
    gender: Gender
    current_level: CompetitionLevel
    clrg_number: Optional[str] = None
    school_id: Optional[str] = None
    # Per-dance levels (optional - defaults to current_level)
    level_reel: Optional[CompetitionLevel] = None
    level_light_jig: Optional[CompetitionLevel] = None
    level_slip_jig: Optional[CompetitionLevel] = None
    level_single_jig: Optional[CompetitionLevel] = None
    level_treble_jig: Optional[CompetitionLevel] = None
    level_hornpipe: Optional[CompetitionLevel] = None
    level_traditional_set: Optional[CompetitionLevel] = None
    level_figure: Optional[CompetitionLevel] = None
    is_adult: bool = False


class DancerUpdate(BaseModel):
    """Request to update an existing dancer profile."""
    name: Optional[str] = None
    dob: Optional[Date] = None
    gender: Optional[Gender] = None
    current_level: Optional[CompetitionLevel] = None
    clrg_number: Optional[str] = None
    school_id: Optional[str] = None
    # Per-dance levels
    level_reel: Optional[CompetitionLevel] = None
    level_light_jig: Optional[CompetitionLevel] = None
    level_slip_jig: Optional[CompetitionLevel] = None
    level_single_jig: Optional[CompetitionLevel] = None
    level_treble_jig: Optional[CompetitionLevel] = None
    level_hornpipe: Optional[CompetitionLevel] = None
    level_traditional_set: Optional[CompetitionLevel] = None
    level_figure: Optional[CompetitionLevel] = None
    is_adult: Optional[bool] = None


class DancerResponse(BaseModel):
    id: str
    name: str
    dob: Date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str] = None
    parent_id: str
    school_id: Optional[str] = None
    # Per-dance levels
    level_reel: Optional[CompetitionLevel] = None
    level_light_jig: Optional[CompetitionLevel] = None
    level_slip_jig: Optional[CompetitionLevel] = None
    level_single_jig: Optional[CompetitionLevel] = None
    level_treble_jig: Optional[CompetitionLevel] = None
    level_hornpipe: Optional[CompetitionLevel] = None
    level_traditional_set: Optional[CompetitionLevel] = None
    level_figure: Optional[CompetitionLevel] = None
    is_adult: bool = False

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
    is_feis_organizer: bool = False  # True if user is co-organizer of any feis

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
    warning: Optional[str] = None

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

class JudgeScoreDetailSchema(BaseModel):
    """Detail of a score from a single judge for API response."""
    judge_id: str
    judge_name: Optional[str] = None
    raw_score: float
    rank: int
    irish_points: float

    class Config:
        from_attributes = True

class TabulatorResultItem(BaseModel):
    """A single competitor's result for display in the tabulator."""
    rank: int
    competitor_number: Optional[int] = None
    dancer_name: str
    dancer_school: Optional[str] = None
    irish_points: float
    is_recalled: bool = False  # Whether this competitor recalls to next round
    judge_scores: List[JudgeScoreDetailSchema] = [] # Detailed per-judge scores

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
    scheduled_time: DateTime


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
    scheduled_time: Optional[DateTime] = None
    estimated_duration_minutes: int
    entry_count: int
    level: CompetitionLevel
    dance_type: Optional[DanceType] = None
    has_conflicts: bool = False
    adjudicator_id: Optional[str] = None
    code: Optional[str] = None

    class Config:
        from_attributes = True


class SchedulerViewResponse(BaseModel):
    """Full data for the scheduler view."""
    feis_id: str
    feis_name: str
    feis_date: Date
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
    late_fee_date: Optional[Date] = None
    change_fee_cents: int = 1000
    registration_opens: Optional[DateTime] = None
    registration_closes: Optional[DateTime] = None


class FeisSettingsUpdate(BaseModel):
    """Request to update feis settings."""
    base_entry_fee_cents: Optional[int] = None
    per_competition_fee_cents: Optional[int] = None
    family_max_cents: Optional[int] = None  # Use -1 to remove cap
    late_fee_cents: Optional[int] = None
    late_fee_date: Optional[Date] = None
    change_fee_cents: Optional[int] = None
    registration_opens: Optional[DateTime] = None
    registration_closes: Optional[DateTime] = None


class FeisSettingsResponse(BaseModel):
    """Response with feis settings."""
    id: str
    feis_id: str
    base_entry_fee_cents: int
    per_competition_fee_cents: int
    family_max_cents: Optional[int]
    late_fee_cents: int
    late_fee_date: Optional[Date]
    change_fee_cents: int
    registration_opens: Optional[DateTime]
    registration_closes: Optional[DateTime]
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
    late_fee_date: Optional[Date]
    
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
    created_at: DateTime
    paid_at: Optional[DateTime]
    entry_count: int

    class Config:
        from_attributes = True


class RegistrationStatusResponse(BaseModel):
    """Response with registration status for a feis."""
    is_open: bool
    message: str
    opens_at: Optional[DateTime]
    closes_at: Optional[DateTime]
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
    competition_date: Date


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
    competition_date: Date
    triggered_advancement: bool
    created_at: DateTime

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
    acknowledged_at: Optional[DateTime]
    overridden: bool
    override_reason: Optional[str]
    created_at: DateTime

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
    resolved_at: Optional[DateTime]
    resolution_note: Optional[str]
    created_at: DateTime

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
    feis_date: Date
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
    dob: Date
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


# ============= Phase 5: Waitlist, Check-In, Refunds =============

from backend.scoring_engine.models_platform import CheckInStatus, WaitlistStatus


# --- Waitlist ---

class WaitlistEntryResponse(BaseModel):
    """Response for a waitlist entry."""
    id: str
    feis_id: str
    feis_name: str
    dancer_id: str
    dancer_name: str
    competition_id: Optional[str]
    competition_name: Optional[str]
    position: int
    status: WaitlistStatus
    offer_sent_at: Optional[DateTime]
    offer_expires_at: Optional[DateTime]
    created_at: DateTime
    
    class Config:
        from_attributes = True


class WaitlistAddRequest(BaseModel):
    """Request to add to waitlist."""
    feis_id: str
    dancer_id: str
    competition_id: Optional[str] = None  # None = global feis waitlist


class WaitlistOfferResponse(BaseModel):
    """Response when a waitlist offer is available."""
    waitlist_id: str
    dancer_name: str
    competition_name: Optional[str]
    feis_name: str
    expires_at: DateTime
    accept_url: str


class WaitlistStatusResponse(BaseModel):
    """Response for waitlist status check."""
    feis_id: str
    feis_name: str
    total_waiting: int
    competition_waitlists: dict  # {competition_id: count}
    global_waitlist_count: int
    user_waitlist_entries: List[WaitlistEntryResponse]


# --- Check-In ---

class CheckInRequest(BaseModel):
    """Request to check in a dancer."""
    entry_id: str


class CheckInResponse(BaseModel):
    """Response after check-in."""
    entry_id: str
    dancer_name: str
    competitor_number: Optional[int]
    competition_name: str
    status: CheckInStatus
    checked_in_at: Optional[DateTime]
    message: str


class BulkCheckInRequest(BaseModel):
    """Request to check in multiple dancers at once."""
    entry_ids: List[str]


class BulkCheckInResponse(BaseModel):
    """Response for bulk check-in."""
    successful: int
    failed: int
    results: List[CheckInResponse]


class StageMonitorEntry(BaseModel):
    """An entry to display on the stage monitor."""
    entry_id: str
    competitor_number: Optional[int]
    dancer_name: str
    school_name: Optional[str]
    check_in_status: CheckInStatus
    is_current: bool
    is_on_deck: bool


class StageMonitorResponse(BaseModel):
    """Response for stage monitor view."""
    competition_id: str
    competition_name: str
    stage_name: Optional[str]
    feis_name: str
    total_entries: int
    checked_in_count: int
    scratched_count: int
    current_dancer: Optional[StageMonitorEntry]
    on_deck: List[StageMonitorEntry]
    all_entries: List[StageMonitorEntry]


class ScratchEntryRequest(BaseModel):
    """Request to scratch (cancel) an entry."""
    entry_id: str
    reason: str


class ScratchEntryResponse(BaseModel):
    """Response after scratching an entry."""
    entry_id: str
    dancer_name: str
    competition_name: str
    refund_amount_cents: int
    message: str


# --- Refunds ---

class RefundRequest(BaseModel):
    """Request to process a refund."""
    order_id: str
    entry_ids: Optional[List[str]] = None  # None = full refund, specific = partial
    reason: str
    refund_amount_cents: Optional[int] = None  # None = auto-calculate based on policy


class RefundResponse(BaseModel):
    """Response after processing a refund."""
    order_id: str
    refund_amount_cents: int
    refund_type: str  # "full", "partial"
    stripe_refund_id: Optional[str]
    entries_refunded: int
    message: str


class RefundLogResponse(BaseModel):
    """Response with refund log details."""
    id: str
    order_id: str
    entry_id: Optional[str]
    amount_cents: int
    reason: str
    refund_type: str
    processed_by_name: str
    created_at: DateTime
    
    class Config:
        from_attributes = True


class OrderRefundSummary(BaseModel):
    """Summary of refunds for an order."""
    order_id: str
    original_total_cents: int
    refund_total_cents: int
    remaining_cents: int
    status: PaymentStatus
    refund_logs: List[RefundLogResponse]


# --- Updated Feis Settings with Caps/Waitlist ---

class FeisSettingsUpdatePhase5(BaseModel):
    """Extended feis settings update including Phase 5 fields."""
    # Existing fields
    base_entry_fee_cents: Optional[int] = None
    per_competition_fee_cents: Optional[int] = None
    family_max_cents: Optional[int] = None
    late_fee_cents: Optional[int] = None
    late_fee_date: Optional[Date] = None
    change_fee_cents: Optional[int] = None
    registration_opens: Optional[DateTime] = None
    registration_closes: Optional[DateTime] = None
    
    # Phase 5 fields
    global_dancer_cap: Optional[int] = None  # None = unlimited
    enable_waitlist: Optional[bool] = None
    waitlist_offer_hours: Optional[int] = None
    allow_scratches: Optional[bool] = None
    scratch_refund_percent: Optional[int] = None  # 0-100
    scratch_deadline: Optional[DateTime] = None


class FeisCapacityStatus(BaseModel):
    """Status of feis capacity and waitlist."""
    feis_id: str
    feis_name: str
    global_cap: Optional[int]
    current_dancer_count: int
    spots_remaining: Optional[int]  # None if no cap
    is_full: bool
    waitlist_enabled: bool
    waitlist_count: int


# ============= Demo Data (Super Admin Only) =============

class DemoDataSummary(BaseModel):
    """Summary of demo data operations."""
    success: bool
    message: str
    organizers: int = 0
    teachers: int = 0
    parents: int = 0
    adjudicators: int = 0
    dancers: int = 0
    feiseanna: int = 0
    competitions: int = 0
    entries: int = 0
    scores: int = 0


class DemoDataStatus(BaseModel):
    """Status of demo data in the system."""
    has_demo_data: bool
    message: str


# ============= Phase 6: Adjudicator Roster Management =============

class AdjudicatorCreate(BaseModel):
    """Request to add an adjudicator to a feis roster."""
    name: str  # Required even without account
    email: Optional[str] = None  # For sending invites
    phone: Optional[str] = None
    credential: Optional[str] = None  # e.g., "TCRG", "ADCRG", "SDCRG"
    organization: Optional[str] = None  # e.g., "CLRG", "CRN", "WIDA"
    school_affiliation_id: Optional[str] = None  # User ID of their school (for conflict detection)
    user_id: Optional[str] = None  # If linking to existing user account


class AdjudicatorUpdate(BaseModel):
    """Request to update an adjudicator's details."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    credential: Optional[str] = None
    organization: Optional[str] = None
    school_affiliation_id: Optional[str] = None
    status: Optional[AdjudicatorStatus] = None
    user_id: Optional[str] = None


class AdjudicatorResponse(BaseModel):
    """Response with adjudicator details."""
    id: str
    feis_id: str
    user_id: Optional[str]
    name: str
    email: Optional[str]
    phone: Optional[str]
    credential: Optional[str]
    organization: Optional[str]
    school_affiliation_id: Optional[str]
    school_affiliation_name: Optional[str]  # Teacher's name for display
    status: AdjudicatorStatus
    invite_sent_at: Optional[DateTime]
    invite_expires_at: Optional[DateTime]
    has_access_pin: bool  # True if a PIN has been generated
    created_at: DateTime
    confirmed_at: Optional[DateTime]
    
    class Config:
        from_attributes = True


class AdjudicatorListResponse(BaseModel):
    """Response with list of adjudicators for a feis."""
    feis_id: str
    feis_name: str
    total_adjudicators: int
    confirmed_count: int
    invited_count: int
    active_count: int
    adjudicators: List[AdjudicatorResponse]


class AdjudicatorInviteRequest(BaseModel):
    """Request to send or resend an invite to an adjudicator."""
    adjudicator_id: str
    custom_message: Optional[str] = None  # Optional personalized message


class AdjudicatorInviteResponse(BaseModel):
    """Response after sending an invite."""
    success: bool
    adjudicator_id: str
    invite_link: str  # The magic link URL
    expires_at: DateTime
    message: str


class AdjudicatorAcceptInviteRequest(BaseModel):
    """Request to accept an adjudicator invite via magic link."""
    token: str  # The magic link token


class AdjudicatorAcceptInviteResponse(BaseModel):
    """Response after accepting an invite."""
    success: bool
    feis_id: str
    feis_name: str
    adjudicator_name: str
    message: str
    access_token: Optional[str]  # JWT if new account created
    user: Optional[UserResponse]


class GeneratePinRequest(BaseModel):
    """Request to generate a day-of access PIN."""
    adjudicator_id: str


class GeneratePinResponse(BaseModel):
    """Response with generated PIN (only shown once!)."""
    success: bool
    adjudicator_id: str
    adjudicator_name: str
    pin: str  # The 6-digit PIN (show once, cannot be retrieved again)
    message: str


class PinLoginRequest(BaseModel):
    """Request to login using a day-of PIN."""
    feis_id: str
    pin: str


class PinLoginResponse(BaseModel):
    """Response after PIN login."""
    success: bool
    access_token: str
    feis_id: str
    feis_name: str
    adjudicator_name: str
    message: str


# --- Judge Panels ---

class PanelMemberCreate(BaseModel):
    """Member to add to a panel."""
    feis_adjudicator_id: str
    sequence: int  # Position in panel (0, 1, 2 for 3-judge; 0-4 for 5-judge)


class JudgePanelCreate(BaseModel):
    """Request to create a new judge panel."""
    name: str  # e.g., "Championship Panel A"
    description: Optional[str] = None
    members: List[PanelMemberCreate]  # List of judges in the panel


class JudgePanelUpdate(BaseModel):
    """Request to update a judge panel."""
    name: Optional[str] = None
    description: Optional[str] = None
    members: Optional[List[PanelMemberCreate]] = None  # Replaces all members if provided


class PanelMemberResponse(BaseModel):
    """Response with panel member details."""
    id: str
    feis_adjudicator_id: str
    adjudicator_name: str
    credential: Optional[str]
    sequence: int
    
    class Config:
        from_attributes = True


class JudgePanelResponse(BaseModel):
    """Response with judge panel details."""
    id: str
    feis_id: str
    name: str
    description: Optional[str]
    members: List[PanelMemberResponse]
    member_count: int  # Computed: 3 or 5 typically
    created_at: DateTime
    updated_at: DateTime
    
    class Config:
        from_attributes = True


class JudgePanelListResponse(BaseModel):
    """Response with list of panels for a feis."""
    feis_id: str
    feis_name: str
    total_panels: int
    panels: List[JudgePanelResponse]


# --- Adjudicator Availability ---

class AvailabilityBlockCreate(BaseModel):
    """Request to create an availability block for an adjudicator."""
    feis_day: Date  # Which day of the feis
    start_time: Time  # e.g., "08:00"
    end_time: Time  # e.g., "17:00"
    availability_type: AvailabilityType = AvailabilityType.AVAILABLE
    note: Optional[str] = None


class AvailabilityBlockUpdate(BaseModel):
    """Request to update an availability block."""
    feis_day: Optional[Date] = None
    start_time: Optional[Time] = None
    end_time: Optional[Time] = None
    availability_type: Optional[AvailabilityType] = None
    note: Optional[str] = None


class AvailabilityBlockResponse(BaseModel):
    """Response with availability block details."""
    id: str
    feis_adjudicator_id: str
    feis_day: Date
    start_time: Time
    end_time: Time
    availability_type: AvailabilityType
    note: Optional[str]
    created_at: DateTime
    
    class Config:
        from_attributes = True


class AdjudicatorAvailabilityResponse(BaseModel):
    """Response with all availability blocks for an adjudicator."""
    adjudicator_id: str
    adjudicator_name: str
    feis_id: str
    feis_dates: List[Date]  # All dates of the feis (for multi-day support)
    availability_blocks: List[AvailabilityBlockResponse]


class BulkAvailabilityCreate(BaseModel):
    """Request to set multiple availability blocks at once."""
    blocks: List[AvailabilityBlockCreate]
    replace_existing: bool = False  # If true, deletes existing blocks for those days


# --- Capacity Metrics ---

class AdjudicatorCapacityResponse(BaseModel):
    """Response with derived scheduling capacity metrics."""
    feis_id: str
    feis_name: str
    total_adjudicators: int
    confirmed_count: int
    active_count: int
    # Derived metrics based on scheduling defaults
    grades_judges_per_stage: int
    champs_judges_per_panel: int
    max_grade_stages: int  # How many single-judge stages can run concurrently
    max_champs_panels: int  # How many championship panels can run concurrently
    recommendation: str  # Human-readable recommendation


# --- Scheduling Defaults (to be added to FeisSettings) ---

class SchedulingDefaultsUpdate(BaseModel):
    """Request to update scheduling defaults for a feis."""
    grades_judges_per_stage: Optional[int] = None  # Default 1
    champs_judges_per_panel: Optional[int] = None  # Default 3
    lunch_duration_minutes: Optional[int] = None  # Default 30
    lunch_window_start: Optional[Time] = None  # e.g., 11:00
    lunch_window_end: Optional[Time] = None  # e.g., 13:00


class SchedulingDefaultsResponse(BaseModel):
    """Response with scheduling defaults."""
    feis_id: str
    grades_judges_per_stage: int
    champs_judges_per_panel: int
    lunch_duration_minutes: int
    lunch_window_start: Optional[Time]
    lunch_window_end: Optional[Time]
    
    class Config:
        from_attributes = True


# ============= Phase 7: Multi-Organizer Support =============

class FeisOrganizerCreate(BaseModel):
    """Request to add a co-organizer to a feis."""
    user_id: str  # User to add as co-organizer
    role: str = "co_organizer"  # co_organizer, assistant, volunteer_coordinator
    can_edit_feis: bool = True
    can_manage_entries: bool = True
    can_manage_schedule: bool = True
    can_manage_adjudicators: bool = True
    can_add_organizers: bool = False


class FeisOrganizerUpdate(BaseModel):
    """Request to update a co-organizer's permissions."""
    role: Optional[str] = None
    can_edit_feis: Optional[bool] = None
    can_manage_entries: Optional[bool] = None
    can_manage_schedule: Optional[bool] = None
    can_manage_adjudicators: Optional[bool] = None
    can_add_organizers: Optional[bool] = None


class FeisOrganizerResponse(BaseModel):
    """Response with co-organizer details."""
    id: str
    feis_id: str
    user_id: str
    user_name: str
    user_email: str
    role: str
    can_edit_feis: bool
    can_manage_entries: bool
    can_manage_schedule: bool
    can_manage_adjudicators: bool
    can_add_organizers: bool
    added_by: str
    added_by_name: str
    added_at: DateTime
    
    class Config:
        from_attributes = True


class FeisOrganizerListResponse(BaseModel):
    """Response with list of organizers for a feis."""
    feis_id: str
    feis_name: str
    primary_organizer_id: str
    primary_organizer_name: str
    co_organizers: List[FeisOrganizerResponse]
    total_organizers: int


# ============= Instant Scheduler =============

class InstantSchedulerRequest(BaseModel):
    """Configuration options for the instant scheduler."""
    min_comp_size: int = 5  # Minimum dancers for a viable competition
    max_comp_size: int = 25  # Maximum dancers before splitting
    lunch_window_start: Optional[str] = "11:00"  # HH:MM format
    lunch_window_end: Optional[str] = "12:00"  # HH:MM format
    lunch_duration_minutes: int = 30
    allow_two_year_merge_up: bool = True  # Allow merging U8 into U10 if U9 doesn't exist
    strict_no_exhibition: bool = False  # If true, force merges when possible
    feis_start_time: Optional[str] = "08:00"  # HH:MM format
    feis_end_time: Optional[str] = "17:00"  # HH:MM format
    clear_existing: bool = True  # Clear existing schedule before generating
    # Duration settings for competitions without entries
    default_grade_duration_minutes: int = 15  # Default duration for grade comps with no entries
    default_champ_duration_minutes: int = 30  # Default duration for champ comps with no entries


class MergeActionResponse(BaseModel):
    """Records a merge action."""
    source_competition_id: str
    target_competition_id: str
    source_competition_name: str
    target_competition_name: str
    source_age_range: str  # e.g., "U8"
    target_age_range: str  # e.g., "U9"
    dancers_moved: int
    reason: str
    rationale: str


class SplitActionResponse(BaseModel):
    """Records a split action."""
    original_competition_id: str
    new_competition_id: str
    competition_name: str
    original_size: int
    group_a_size: int
    group_b_size: int
    reason: str
    assignment_method: str  # "random" or "birth_month"


class SchedulerWarningResponse(BaseModel):
    """A warning generated during scheduling."""
    code: str  # Warning code enum value
    message: str
    competition_ids: List[str] = []
    stage_ids: List[str] = []
    severity: str = "warning"  # "warning" or "critical"


class NormalizationResponse(BaseModel):
    """Result of competition normalization."""
    merges: List[MergeActionResponse] = []
    splits: List[SplitActionResponse] = []
    warnings: List[SchedulerWarningResponse] = []
    final_competition_count: int = 0


class StagePlanResponse(BaseModel):
    """Plan for a stage based on judge coverage."""
    stage_id: str
    stage_name: str
    coverage_block_count: int
    is_championship_capable: bool
    track: str  # "grades" or "championships"


class PlacementResponse(BaseModel):
    """A scheduled competition placement."""
    competition_id: str
    competition_name: str
    stage_id: str
    stage_name: str
    scheduled_start: DateTime
    scheduled_end: DateTime
    duration_minutes: int
    entry_count: int


class LunchHoldResponse(BaseModel):
    """A lunch break hold on a stage."""
    stage_id: str
    stage_name: str
    start_time: DateTime
    end_time: DateTime
    duration_minutes: int


class InstantSchedulerResponse(BaseModel):
    """Full result from the instant scheduler."""
    success: bool
    message: str
    
    # Normalization results
    normalized: NormalizationResponse
    
    # Stage plan
    stage_plan: List[StagePlanResponse] = []
    
    # Placements
    placements: List[PlacementResponse] = []
    lunch_holds: List[LunchHoldResponse] = []
    
    # Warnings and conflicts
    warnings: List[SchedulerWarningResponse] = []
    conflicts: List[ScheduleConflict] = []
    
    # Summary stats
    total_competitions_scheduled: int = 0
    total_competitions_unscheduled: int = 0
    merge_count: int = 0
    split_count: int = 0
    grade_competitions: int = 0
    championship_competitions: int = 0
