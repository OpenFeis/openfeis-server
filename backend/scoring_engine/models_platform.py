from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import date, datetime, time
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

if TYPE_CHECKING:
    pass

# --- Enums ---

class RoleType(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORGANIZER = "organizer"
    TEACHER = "teacher"
    PARENT = "parent"
    ADJUDICATOR = "adjudicator"

class CompetitionLevel(str, Enum):
    """Competition levels following industry standard numbering."""
    FIRST_FEIS = "first_feis"                       # Level 1
    BEGINNER_1 = "beginner_1"                       # Level 2
    BEGINNER_2 = "beginner_2"                       # Level 3 (Advanced Beginner)
    NOVICE = "novice"                               # Level 4
    PRIZEWINNER = "prizewinner"                     # Level 5 (Open)
    PRELIMINARY_CHAMPIONSHIP = "preliminary_championship"  # Level 6
    OPEN_CHAMPIONSHIP = "open_championship"         # Level 7

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class DanceType(str, Enum):
    """Standard Irish dance types with their typical tempos."""
    # Solo dances
    REEL = "REEL"                           # 113 bpm
    LIGHT_JIG = "LIGHT_JIG"                 # 115 bpm  
    SLIP_JIG = "SLIP_JIG"                   # 113 bpm
    SINGLE_JIG = "SINGLE_JIG"               # 124 bpm (NEW)
    TREBLE_JIG = "TREBLE_JIG"               # 73 bpm
    HORNPIPE = "HORNPIPE"                   # 138 bpm
    TRADITIONAL_SET = "TRADITIONAL_SET"     # Varies
    CONTEMPORARY_SET = "CONTEMPORARY_SET"   # Varies
    TREBLE_REEL = "TREBLE_REEL"             # 92 bpm
    
    # Figure/Ceili dances (team dances)
    TWO_HAND = "TWO_HAND"                   # 2-hand reel
    THREE_HAND = "THREE_HAND"               # 3-hand reel
    FOUR_HAND = "FOUR_HAND"                 # 4-hand jig or reel
    SIX_HAND = "SIX_HAND"                   # 6-hand reel
    EIGHT_HAND = "EIGHT_HAND"               # 8-hand ceili


class CompetitionCategory(str, Enum):
    """Category of competition for registration grouping."""
    SOLO = "SOLO"                   # Individual solo dances
    FIGURE = "FIGURE"               # Team/ceili dances (2-hand, 3-hand, etc.)
    CHAMPIONSHIP = "CHAMPIONSHIP"   # Prelim and Open Championships
    SPECIAL = "SPECIAL"             # Special/Trophy competitions (e.g. Treble Reel Special)

class ScoringMethod(str, Enum):
    """How a competition is scored."""
    SOLO = "SOLO"                   # 1 judge, raw scores
    CHAMPIONSHIP = "CHAMPIONSHIP"   # 3-5 judges, Irish Points


class FeeCategory(str, Enum):
    """Category of fee for family max calculation."""
    QUALIFYING = "qualifying"           # Counts toward family max (competitions)
    NON_QUALIFYING = "non_qualifying"   # Doesn't count (venue levy, program book, merch)


class PaymentStatus(str, Enum):
    """Status of a payment/order."""
    PENDING = "pending"         # Not yet paid
    COMPLETED = "completed"     # Payment received
    FAILED = "failed"           # Payment attempt failed
    REFUNDED = "refunded"       # Payment was refunded (full)
    PARTIAL_REFUND = "partial_refund"  # Some entries refunded
    PAY_AT_DOOR = "pay_at_door" # Will pay at event check-in


class CheckInStatus(str, Enum):
    """Check-in status for entries at the event."""
    NOT_CHECKED_IN = "not_checked_in"  # Default state
    CHECKED_IN = "checked_in"          # Dancer is present
    SCRATCHED = "scratched"            # Dancer cancelled/no-show


class WaitlistStatus(str, Enum):
    """Status of a waitlist entry."""
    WAITING = "waiting"       # In queue
    PROMOTED = "promoted"     # Moved to registered
    EXPIRED = "expired"       # Offer expired
    CANCELLED = "cancelled"   # User cancelled


class AdjudicatorStatus(str, Enum):
    """Status of an adjudicator's participation in a feis."""
    INVITED = "invited"       # Invite sent, not yet confirmed
    CONFIRMED = "confirmed"   # Accepted, will attend
    ACTIVE = "active"         # Currently judging at the event
    DECLINED = "declined"     # Declined invitation


class AvailabilityType(str, Enum):
    """Type of availability block for an adjudicator."""
    AVAILABLE = "available"       # Judge is available to work
    UNAVAILABLE = "unavailable"   # Judge cannot work during this time
    LUNCH = "lunch"               # Scheduled lunch break


# --- Database Models ---

class User(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str 
    role: RoleType = Field(default=RoleType.PARENT)
    name: str
    
    # Email verification
    email_verified: bool = Field(default=False)
    email_verification_token: Optional[str] = Field(default=None, index=True)
    email_verification_sent_at: Optional[datetime] = Field(default=None)
    
    # Relationships
    dancers: List["Dancer"] = Relationship(
        back_populates="parent",
        sa_relationship_kwargs={"foreign_keys": "Dancer.parent_id"}
    )
    feiseanna: List["Feis"] = Relationship(back_populates="organizer")


class SiteSettings(SQLModel, table=True):
    """
    Singleton table for site-wide configuration.
    Stores settings like API keys that admins can configure via the UI.
    """
    id: int = Field(default=1, primary_key=True)  # Always use id=1 for singleton
    
    # Email settings (Resend)
    resend_api_key: Optional[str] = Field(default=None)
    resend_from_email: str = Field(default="Open Feis <noreply@openfeis.com>")
    
    # General settings
    site_name: str = Field(default="Open Feis")
    site_url: str = Field(default="https://openfeis.com")

class Feis(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    organizer_id: UUID = Field(foreign_key="user.id")
    name: str
    date: date
    location: str
    stripe_account_id: Optional[str] = None
    
    # Relationships
    organizer: User = Relationship(back_populates="feiseanna")
    competitions: List["Competition"] = Relationship(back_populates="feis")
    stages: List["Stage"] = Relationship(back_populates="feis")
    settings: Optional["FeisSettings"] = Relationship(back_populates="feis")
    fee_items: List["FeeItem"] = Relationship(back_populates="feis")
    orders: List["Order"] = Relationship(back_populates="feis")
    adjudicators: List["FeisAdjudicator"] = Relationship(back_populates="feis")
    judge_panels: List["JudgePanel"] = Relationship()
    co_organizers: List["FeisOrganizer"] = Relationship(
        back_populates="feis",
        sa_relationship_kwargs={"foreign_keys": "FeisOrganizer.feis_id"}
    )


class Stage(SQLModel, table=True):
    """A stage/area at a feis where competitions take place."""
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    name: str  # e.g., "Stage A", "Main Hall", "Stage 1"
    color: Optional[str] = None  # Hex color for UI display, e.g., "#FF5733"
    sequence: int = Field(default=0)  # Display order
    
    # Relationships
    feis: Feis = Relationship(back_populates="stages")
    competitions: List["Competition"] = Relationship(back_populates="stage")
    judge_coverage: List["StageJudgeCoverage"] = Relationship(back_populates="stage")


class StageJudgeCoverage(SQLModel, table=True):
    """
    Time-based judge or panel assignment to a stage.
    
    Can represent either:
    - Single judge coverage (feis_adjudicator_id set, panel_id is None)
    - Panel coverage (panel_id set, feis_adjudicator_id can be None)
    
    For multi-stage panels, multiple StageJudgeCoverage records share the same panel_id.
    """
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    stage_id: UUID = Field(foreign_key="stage.id", index=True)
    
    # Either a single judge OR a panel (mutually exclusive in most cases)
    feis_adjudicator_id: Optional[UUID] = Field(default=None, foreign_key="feisadjudicator.id", index=True)
    panel_id: Optional[UUID] = Field(default=None, foreign_key="judgepanel.id", index=True)
    
    # Time range for this coverage
    feis_day: date  # Which day of the feis
    start_time: time  # e.g., 09:00
    end_time: time    # e.g., 12:30
    
    # Optional note (e.g., "covering lunch break", "grades only", "Championship Panel A")
    note: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    stage: Stage = Relationship(back_populates="judge_coverage")
    feis_adjudicator: Optional["FeisAdjudicator"] = Relationship(back_populates="stage_coverage")
    panel: Optional["JudgePanel"] = Relationship(back_populates="stage_coverage")

class Dancer(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    parent_id: UUID = Field(foreign_key="user.id")
    school_id: Optional[UUID] = Field(default=None, foreign_key="user.id")  # Link to User(Teacher)
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str] = None
    
    # Per-dance levels (defaults to current_level if None)
    # Allows dancers to compete at different levels for different dances
    level_reel: Optional[CompetitionLevel] = None
    level_light_jig: Optional[CompetitionLevel] = None
    level_slip_jig: Optional[CompetitionLevel] = None
    level_single_jig: Optional[CompetitionLevel] = None
    level_treble_jig: Optional[CompetitionLevel] = None
    level_hornpipe: Optional[CompetitionLevel] = None
    level_traditional_set: Optional[CompetitionLevel] = None
    level_figure: Optional[CompetitionLevel] = None  # For all figure/ceili dances
    
    # Adult dancer flag
    is_adult: bool = Field(default=False)
    
    # Relationships
    parent: User = Relationship(
        back_populates="dancers",
        sa_relationship_kwargs={"foreign_keys": "[Dancer.parent_id]"}
    )
    school: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Dancer.school_id]"}
    )
    entries: List["Entry"] = Relationship(back_populates="dancer")

class Competition(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    
    # Display code (e.g., "407SJ" for Novice U7 Slip Jig)
    # Auto-generated but can be overridden by organizer
    code: Optional[str] = Field(default=None, index=True)
    
    # Competition category (solo, figure, championship)
    category: CompetitionCategory = Field(default=CompetitionCategory.SOLO)
    
    # For figure/ceili dances: is this a mixed (boys+girls) competition?
    is_mixed: bool = Field(default=False)
    
    # Description for Special competitions (and others)
    description: Optional[str] = None
    
    # Comma-separated list of allowed levels for Special competitions
    # If set, this overrides the 'level' field for eligibility checks
    allowed_levels: Optional[str] = None
    
    # New scheduling/competition definition fields (Phase 2)
    dance_type: Optional[DanceType] = None
    tempo_bpm: Optional[int] = None  # e.g., 113 for Reel
    bars: int = Field(default=48)  # Number of bars danced
    scoring_method: ScoringMethod = Field(default=ScoringMethod.SOLO)
    price_cents: int = Field(default=1000)  # $10.00 default
    max_entries: Optional[int] = None  # None = unlimited
    
    # Fee category for family max calculation (Phase 3)
    fee_category: FeeCategory = Field(default=FeeCategory.QUALIFYING)
    
    # Stage and scheduling
    stage_id: Optional[UUID] = Field(default=None, foreign_key="stage.id")
    scheduled_time: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    
    # Adjudicator assignment - single judge for solo events
    adjudicator_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Panel assignment - for championship/panel events where multiple judges score
    # When panel_id is set, ALL judges in the panel can score this competition
    panel_id: Optional[UUID] = Field(default=None, foreign_key="judgepanel.id")
    
    # Relationships
    feis: Feis = Relationship(back_populates="competitions")
    entries: List["Entry"] = Relationship(back_populates="competition")
    stage: Optional["Stage"] = Relationship(back_populates="competitions")
    adjudicator: Optional["User"] = Relationship()
    panel: Optional["JudgePanel"] = Relationship()
    # Note: 'rounds' relationship will be linked in the scoring models file or here if consolidated

class Entry(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id")
    competition_id: UUID = Field(foreign_key="competition.id")
    competitor_number: Optional[int] = None
    paid: bool = Field(default=False)
    pay_later: bool = Field(default=False)  # "Pay at Door" option - permanent feature
    order_id: Optional[UUID] = Field(default=None, foreign_key="order.id")
    
    # Check-in status (Phase 5)
    check_in_status: CheckInStatus = Field(default=CheckInStatus.NOT_CHECKED_IN)
    checked_in_at: Optional[datetime] = None
    checked_in_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Cancellation/Scratch (Phase 5)
    cancelled: bool = Field(default=False)
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    refund_amount_cents: int = Field(default=0)  # Amount refunded for this entry
    
    # Relationships
    dancer: Dancer = Relationship(back_populates="entries")
    competition: Competition = Relationship(back_populates="entries")
    order: Optional["Order"] = Relationship(back_populates="entries")
    flags: List["EntryFlag"] = Relationship(back_populates="entry")


class FeisSettings(SQLModel, table=True):
    """
    Per-feis configuration for pricing and registration.
    
    Each feis has its own pricing rules that can be configured by the organizer.
    Supports family caps, late fees, and registration windows.
    """
    __tablename__ = "feissettings"  # Explicit table name
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", unique=True)
    
    # Pricing
    base_entry_fee_cents: int = Field(default=2500)  # $25.00 per dancer (one-time)
    per_competition_fee_cents: int = Field(default=1000)  # $10.00 per competition
    family_max_cents: Optional[int] = Field(default=15000)  # $150.00 family cap (None = no cap)
    
    # Late fees
    late_fee_cents: int = Field(default=500)  # $5.00 per entry after deadline
    late_fee_date: Optional[date] = None  # Date after which late fee applies
    
    # Change/modification fee
    change_fee_cents: int = Field(default=1000)  # $10.00 to change registration after close
    
    # Registration window
    registration_opens: Optional[datetime] = None
    registration_closes: Optional[datetime] = None
    
    # Capacity limits (Phase 5)
    global_dancer_cap: Optional[int] = None  # Max total dancers (None = unlimited)
    enable_waitlist: bool = Field(default=True)  # Auto-add to waitlist when caps reached
    waitlist_offer_hours: int = Field(default=48)  # Hours to accept waitlist offer before expiring
    
    # Refund policy (Phase 5)
    allow_scratches: bool = Field(default=True)  # Can entries be cancelled?
    scratch_refund_percent: int = Field(default=50)  # % refund when scratching (0-100)
    scratch_deadline: Optional[datetime] = None  # After this, no refunds
    
    # Stripe settings (per-feis, for Stripe Connect)
    stripe_account_id: Optional[str] = None  # Connected Stripe account ID
    stripe_onboarding_complete: bool = Field(default=False)
    
    # Scheduling defaults (Phase 6)
    grades_judges_per_stage: int = Field(default=1)  # Typically 1 judge for grade comps
    champs_judges_per_panel: int = Field(default=3)  # Typically 3 judges for champs
    lunch_duration_minutes: int = Field(default=30)  # Standard lunch break duration
    lunch_window_start: Optional[time] = None  # e.g., 11:00 - preferred lunch window start
    lunch_window_end: Optional[time] = None  # e.g., 13:00 - preferred lunch window end
    
    # Relationships
    feis: "Feis" = Relationship(back_populates="settings")


class FeeItem(SQLModel, table=True):
    """
    Additional fees beyond competition entry.
    
    Used for venue levies, program books, t-shirts, etc.
    These can be marked as required (auto-added to every order) or optional.
    """
    __tablename__ = "feeitem"  # Explicit table name
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    
    name: str  # e.g., "Venue Levy", "Program Book", "Event T-Shirt"
    description: Optional[str] = None
    amount_cents: int  # Price in cents
    category: FeeCategory = Field(default=FeeCategory.NON_QUALIFYING)
    required: bool = Field(default=False)  # If true, auto-added to every order
    max_quantity: int = Field(default=1)  # Maximum per order (e.g., 1 for venue levy, 10 for t-shirts)
    active: bool = Field(default=True)  # Can be disabled without deleting
    
    # Relationships
    feis: "Feis" = Relationship(back_populates="fee_items")


class Order(SQLModel, table=True):
    """
    A registration order/transaction.
    
    Groups entries and fee items into a single payment transaction.
    Tracks payment status and provides audit trail.
    """
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    user_id: UUID = Field(foreign_key="user.id")  # The parent/purchaser
    
    # Amounts (all in cents)
    subtotal_cents: int = Field(default=0)
    qualifying_subtotal_cents: int = Field(default=0)  # Amount subject to family cap
    non_qualifying_subtotal_cents: int = Field(default=0)  # Fees not subject to cap
    family_discount_cents: int = Field(default=0)  # Amount saved by family cap
    late_fee_cents: int = Field(default=0)  # Late fee if applicable
    total_cents: int = Field(default=0)  # Final amount charged
    
    # Payment info
    status: PaymentStatus = Field(default=PaymentStatus.PENDING)
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    
    # Refund tracking (Phase 5)
    refund_total_cents: int = Field(default=0)  # Total amount refunded
    refunded_at: Optional[datetime] = None
    refund_reason: Optional[str] = None
    stripe_refund_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None
    
    # Relationships
    feis: "Feis" = Relationship(back_populates="orders")
    user: "User" = Relationship()
    entries: List["Entry"] = Relationship(back_populates="order")
    order_items: List["OrderItem"] = Relationship(back_populates="order")


class OrderItem(SQLModel, table=True):
    """
    Individual items within an order (fee items, not entries).
    
    Entries are linked directly to Order, but additional fee items
    (venue levy, t-shirts, etc.) are tracked here.
    """
    __tablename__ = "orderitem"  # Explicit table name
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="order.id")
    fee_item_id: UUID = Field(foreign_key="feeitem.id")
    
    quantity: int = Field(default=1)
    unit_price_cents: int  # Snapshot of price at time of order
    total_cents: int  # quantity * unit_price_cents
    
    # Relationships
    order: "Order" = Relationship(back_populates="order_items")
    fee_item: "FeeItem" = Relationship()


# ============= Phase 4: Teacher Portal & Advancement =============

class PlacementHistory(SQLModel, table=True):
    """
    Records a dancer's placement in a competition.
    
    Used for tracking advancement eligibility (e.g., CLRG rules
    where winning at a level advances the dancer to the next level).
    """
    __tablename__ = "placementhistory"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id", index=True)
    competition_id: UUID = Field(foreign_key="competition.id")
    feis_id: UUID = Field(foreign_key="feis.id")
    entry_id: Optional[UUID] = Field(default=None, foreign_key="entry.id")
    
    # Placement info
    rank: int  # 1st, 2nd, 3rd, etc.
    irish_points: Optional[float] = None
    
    # Competition snapshot (for historical record)
    dance_type: Optional[DanceType] = None
    level: CompetitionLevel
    competition_date: date
    
    # Advancement tracking
    triggered_advancement: bool = Field(default=False)
    advancement_processed_at: Optional[datetime] = None
    
    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    dancer: "Dancer" = Relationship()
    competition: "Competition" = Relationship()
    feis: "Feis" = Relationship()


class EntryFlag(SQLModel, table=True):
    """
    Flags an entry for organizer review.
    
    Teachers can flag entries when they believe:
    - A dancer is registered at the wrong level
    - Wrong school/teacher affiliation
    - Other registration issues
    """
    __tablename__ = "entryflag"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    entry_id: UUID = Field(foreign_key="entry.id", index=True)
    flagged_by: UUID = Field(foreign_key="user.id")  # Teacher who flagged
    
    # Flag details
    reason: str  # Free text explanation
    flag_type: str = Field(default="level_incorrect")  # level_incorrect, school_wrong, other
    
    # Resolution
    resolved: bool = Field(default=False)
    resolved_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    entry: "Entry" = Relationship()
    flagged_by_user: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[EntryFlag.flagged_by]"}
    )


class AdvancementNotice(SQLModel, table=True):
    """
    Records when a dancer should advance to the next level.
    
    Generated by the advancement rules engine when a dancer 
    meets the criteria to move up (e.g., 1st place at Beginner).
    """
    __tablename__ = "advancementnotice"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id", index=True)
    
    # What triggered the advancement
    from_level: CompetitionLevel
    to_level: CompetitionLevel
    dance_type: Optional[DanceType] = None  # None = all dances, specific = per-dance advancement
    
    # Reference to the placement that triggered it
    triggering_placement_id: Optional[UUID] = Field(default=None, foreign_key="placementhistory.id")
    
    # Status
    acknowledged: bool = Field(default=False)  # Has parent/teacher seen this?
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Override (admin can override advancement requirement)
    overridden: bool = Field(default=False)
    overridden_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    override_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    dancer: "Dancer" = Relationship()


# ============= Phase 5: Waitlist, Check-In, Refunds =============

class WaitlistEntry(SQLModel, table=True):
    """
    Tracks dancers waiting for a spot in a competition or feis.
    
    When a competition or feis reaches capacity, new registrations
    go to the waitlist. If a spot opens (scratch/cancellation),
    the next person in line is offered the spot.
    """
    __tablename__ = "waitlistentry"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", index=True)
    dancer_id: UUID = Field(foreign_key="dancer.id", index=True)
    competition_id: Optional[UUID] = Field(default=None, foreign_key="competition.id")  # None = global waitlist
    user_id: UUID = Field(foreign_key="user.id")  # Parent who added to waitlist
    
    # Queue position and status
    position: int  # Position in waitlist (1 = first in line)
    status: WaitlistStatus = Field(default=WaitlistStatus.WAITING)
    
    # Offer tracking (when spot becomes available)
    offer_sent_at: Optional[datetime] = None
    offer_expires_at: Optional[datetime] = None
    offer_accepted_at: Optional[datetime] = None
    
    # If promoted, reference to the created entry
    promoted_entry_id: Optional[UUID] = Field(default=None, foreign_key="entry.id")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    feis: "Feis" = Relationship()
    dancer: "Dancer" = Relationship()
    competition: Optional["Competition"] = Relationship()
    user: "User" = Relationship()


class RefundLog(SQLModel, table=True):
    """
    Audit log for refunds processed.
    
    Tracks individual refund transactions for compliance and debugging.
    """
    __tablename__ = "refundlog"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(foreign_key="order.id", index=True)
    entry_id: Optional[UUID] = Field(default=None, foreign_key="entry.id")  # Specific entry if partial refund
    
    # Refund details
    amount_cents: int
    reason: str
    refund_type: str  # "full", "partial", "scratch"
    
    # Processing info
    processed_by: UUID = Field(foreign_key="user.id")
    stripe_refund_id: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    order: "Order" = Relationship()


# ============= Phase 6: Adjudicator Roster Management =============

class FeisAdjudicator(SQLModel, table=True):
    """
    Links adjudicators to a specific feis roster.
    
    Enables roster-driven adjudicator management where organizers can:
    - Build a roster before judges have accounts
    - Track invitation and confirmation status
    - Manage day-of access via PINs
    - Detect school affiliation conflicts
    """
    __tablename__ = "feisadjudicator"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")  # Null until they accept/create account
    
    # Identity (can exist before account)
    name: str  # Required even without account
    email: Optional[str] = Field(default=None, index=True)  # For sending invites
    phone: Optional[str] = None  # Optional contact
    
    # Credentials
    credential: Optional[str] = None  # e.g., "TCRG", "ADCRG", "SDCRG"
    organization: Optional[str] = None  # e.g., "CLRG", "CRN", "WIDA"
    school_affiliation_id: Optional[UUID] = Field(default=None, foreign_key="user.id")  # FK to User (teacher) for conflict detection
    
    # Status
    status: AdjudicatorStatus = Field(default=AdjudicatorStatus.INVITED)
    
    # Access - Magic link invite
    invite_token: Optional[str] = Field(default=None, index=True)  # Magic link token
    invite_sent_at: Optional[datetime] = None
    invite_expires_at: Optional[datetime] = None
    
    # Access - Day-of PIN
    access_pin_hash: Optional[str] = None  # 6-digit day-of PIN (hashed)
    pin_generated_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confirmed_at: Optional[datetime] = None
    
    # Relationships
    feis: "Feis" = Relationship(back_populates="adjudicators")
    user: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[FeisAdjudicator.user_id]"}
    )
    school_affiliation: Optional["User"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[FeisAdjudicator.school_affiliation_id]"}
    )
    availability_blocks: List["AdjudicatorAvailability"] = Relationship(back_populates="adjudicator")
    stage_coverage: List["StageJudgeCoverage"] = Relationship(back_populates="feis_adjudicator")


class AdjudicatorAvailability(SQLModel, table=True):
    """
    Time blocks when an adjudicator can or cannot work.
    
    Supports multi-day feiseanna where availability varies by day.
    Used by the scheduler to prevent assigning judges outside their available times.
    """
    __tablename__ = "adjudicatoravailability"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_adjudicator_id: UUID = Field(foreign_key="feisadjudicator.id", index=True)
    
    # Multi-day support - which day of the feis
    feis_day: date
    
    # Time window
    start_time: time  # e.g., 08:00
    end_time: time    # e.g., 17:00
    availability_type: AvailabilityType = Field(default=AvailabilityType.AVAILABLE)
    note: Optional[str] = None  # e.g., "Lunch with organizer", "Flight arrives at 10am"
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    adjudicator: "FeisAdjudicator" = Relationship(back_populates="availability_blocks")


class JudgePanel(SQLModel, table=True):
    """
    A formal panel of judges (e.g., 3-judge or 5-judge panel).
    
    Panels are first-class entities that can be assigned to one or more stages.
    Examples:
    - Championship Panel A (3 judges, single stage for major events)
    - Ping Pong Panel B (3 judges, stages 3 and 4)
    - Grand Championship Panel (5 judges, single stage)
    """
    __tablename__ = "judgepanel"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", index=True)
    
    name: str  # e.g., "Championship Panel A", "Ping Pong Panel B"
    description: Optional[str] = None  # Optional notes
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    feis: "Feis" = Relationship(sa_relationship_kwargs={"overlaps": "judge_panels"})
    members: List["PanelMember"] = Relationship(back_populates="panel", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    stage_coverage: List["StageJudgeCoverage"] = Relationship(back_populates="panel")


class PanelMember(SQLModel, table=True):
    """
    Junction table linking judges to panels.
    
    Tracks which judges are part of which panel and their position/sequence.
    """
    __tablename__ = "panelmember"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    panel_id: UUID = Field(foreign_key="judgepanel.id", index=True)
    feis_adjudicator_id: UUID = Field(foreign_key="feisadjudicator.id", index=True)
    
    sequence: int = Field(default=0)  # Order in panel (Judge 1, Judge 2, Judge 3, etc.)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    panel: JudgePanel = Relationship(back_populates="members")
    feis_adjudicator: "FeisAdjudicator" = Relationship()


# ============= Phase 7: Multi-Organizer Support =============

class FeisOrganizer(SQLModel, table=True):
    """
    Links additional organizers (co-organizers) to a feis.
    
    The primary organizer is stored in Feis.organizer_id.
    This table tracks additional users who can manage the feis.
    """
    __tablename__ = "feisorganizer"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    
    # Role within the feis organizing team
    role: str = Field(default="co_organizer")  # "co_organizer", "assistant", "volunteer_coordinator"
    
    # Permissions (can be customized per co-organizer)
    can_edit_feis: bool = Field(default=True)  # Edit feis details, settings
    can_manage_entries: bool = Field(default=True)  # Manage registrations
    can_manage_schedule: bool = Field(default=True)  # Edit schedule
    can_manage_adjudicators: bool = Field(default=True)  # Manage judge roster
    can_add_organizers: bool = Field(default=False)  # Only primary owner by default
    
    # Audit
    added_by: UUID = Field(foreign_key="user.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    feis: "Feis" = Relationship()
    user: "User" = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[FeisOrganizer.user_id]"}
    )

