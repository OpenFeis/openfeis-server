from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import date, datetime
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
    BEGINNER = "beginner"
    NOVICE = "novice"
    PRIZEWINNER = "prizewinner"
    CHAMPIONSHIP = "championship"

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class DanceType(str, Enum):
    """Standard Irish dance types with their typical tempos."""
    REEL = "REEL"                           # 113 bpm
    LIGHT_JIG = "LIGHT_JIG"                 # 115 bpm  
    SLIP_JIG = "SLIP_JIG"                   # 113 bpm
    TREBLE_JIG = "TREBLE_JIG"               # 73 bpm
    HORNPIPE = "HORNPIPE"                   # 138 bpm
    TRADITIONAL_SET = "TRADITIONAL_SET"     # Varies
    CONTEMPORARY_SET = "CONTEMPORARY_SET"   # Varies
    TREBLE_REEL = "TREBLE_REEL"             # 92 bpm

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
    REFUNDED = "refunded"       # Payment was refunded
    PAY_AT_DOOR = "pay_at_door" # Will pay at event check-in


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
    dancers: List["Dancer"] = Relationship(back_populates="parent")
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

class Dancer(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    parent_id: UUID = Field(foreign_key="user.id")
    school_id: Optional[UUID] = None # Link to User(Teacher) in future
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str] = None
    
    # Relationships
    parent: User = Relationship(back_populates="dancers")
    entries: List["Entry"] = Relationship(back_populates="dancer")

class Competition(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    feis_id: UUID = Field(foreign_key="feis.id")
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    
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
    
    # Adjudicator assignment (for conflict detection)
    adjudicator_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Relationships
    feis: Feis = Relationship(back_populates="competitions")
    entries: List["Entry"] = Relationship(back_populates="competition")
    stage: Optional["Stage"] = Relationship(back_populates="competitions")
    adjudicator: Optional["User"] = Relationship()
    # Note: 'rounds' relationship will be linked in the scoring models file or here if consolidated

class Entry(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id")
    competition_id: UUID = Field(foreign_key="competition.id")
    competitor_number: Optional[int] = None
    paid: bool = Field(default=False)
    pay_later: bool = Field(default=False)  # "Pay at Door" option - permanent feature
    order_id: Optional[UUID] = Field(default=None, foreign_key="order.id")
    
    # Relationships
    dancer: Dancer = Relationship(back_populates="entries")
    competition: Competition = Relationship(back_populates="entries")
    order: Optional["Order"] = Relationship(back_populates="entries")


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
    
    # Stripe settings (per-feis, for Stripe Connect)
    stripe_account_id: Optional[str] = None  # Connected Stripe account ID
    stripe_onboarding_complete: bool = Field(default=False)
    
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

