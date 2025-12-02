from typing import List, Optional
from uuid import UUID, uuid4
from datetime import date
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum

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

# --- Database Models ---

class User(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str 
    role: RoleType = Field(default=RoleType.PARENT)
    name: str
    
    # Relationships
    dancers: List["Dancer"] = Relationship(back_populates="parent")
    feiseanna: List["Feis"] = Relationship(back_populates="organizer")

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
    
    # Relationships
    feis: Feis = Relationship(back_populates="competitions")
    entries: List["Entry"] = Relationship(back_populates="competition")
    # Note: 'rounds' relationship will be linked in the scoring models file or here if consolidated

class Entry(SQLModel, table=True):
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    dancer_id: UUID = Field(foreign_key="dancer.id")
    competition_id: UUID = Field(foreign_key="competition.id")
    competitor_number: Optional[int] = None
    paid: bool = Field(default=False)
    
    # Relationships
    dancer: Dancer = Relationship(back_populates="entries")
    competition: Competition = Relationship(back_populates="entries")

