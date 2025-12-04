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
    
    # Relationships
    dancer: Dancer = Relationship(back_populates="entries")
    competition: Competition = Relationship(back_populates="entries")

