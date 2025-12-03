from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from uuid import UUID
from backend.scoring_engine.models_platform import CompetitionLevel, Gender, RoleType

# ============= Syllabus Generation =============

class SyllabusGenerationRequest(BaseModel):
    feis_id: str
    levels: List[CompetitionLevel]
    min_age: int
    max_age: int
    genders: List[Gender]
    dances: List[str] = ["Reel", "Light Jig", "Slip Jig", "Treble Jig", "Hornpipe"]

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

class CompetitionUpdate(BaseModel):
    name: Optional[str] = None
    min_age: Optional[int] = None
    max_age: Optional[int] = None
    level: Optional[CompetitionLevel] = None
    gender: Optional[Gender] = None

class CompetitionResponse(BaseModel):
    id: str
    feis_id: str
    name: str
    min_age: int
    max_age: int
    level: CompetitionLevel
    gender: Optional[Gender] = None
    entry_count: int = 0

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
