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

    class Config:
        from_attributes = True

class BulkNumberAssignment(BaseModel):
    start_number: int = 100
    feis_id: str

class BulkNumberAssignmentResponse(BaseModel):
    assigned_count: int
    message: str

# ============= Dancer Read (for entry management) =============

class DancerResponse(BaseModel):
    id: str
    name: str
    dob: date
    current_level: CompetitionLevel
    gender: Gender
    clrg_number: Optional[str] = None
    parent_id: str

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
