import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import List
from sqlmodel import Session, select
from backend.scoring_engine.models_platform import User, RoleType, FeisOrganizer
from backend.db.database import get_session
from backend.api.schemas import (
    LoginRequest, RegisterRequest, AuthResponse,
    VerifyEmailRequest, ResendVerificationRequest, VerificationResponse,
    ProfileUpdate, PasswordChangeRequest, UserResponse
)
from backend.api.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user
)
from backend.services.email import (
    send_verification_email,
    verify_email_token,
    can_resend_verification,
    is_email_configured
)

router = APIRouter()

LOCAL_MODE = os.getenv("OPENFEIS_LOCAL_MODE", "false").lower() == "true"
SEED_ADMIN_EMAIL = os.getenv("OPENFEIS_SEED_ADMIN_EMAIL", "admin@openfeis.org")
DEFAULT_LOCAL_ADMIN_PASSWORD = "admin123"

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

    warning = None
    if (
        LOCAL_MODE
        and credentials.email == SEED_ADMIN_EMAIL
        and credentials.password == DEFAULT_LOCAL_ADMIN_PASSWORD
        and user.role == RoleType.SUPER_ADMIN
    ):
        warning = (
            "You're signed in with the default local admin password. "
            "Go to My Account → Change Password before using this outside a private/dev environment."
        )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        ),
        warning=warning,
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

    warning = None
    if (
        LOCAL_MODE
        and form_data.username == SEED_ADMIN_EMAIL
        and form_data.password == DEFAULT_LOCAL_ADMIN_PASSWORD
        and user.role == RoleType.SUPER_ADMIN
    ):
        warning = (
            "You're signed in with the default local admin password. "
            "Go to My Account → Change Password before using this outside a private/dev environment."
        )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        ),
        warning=warning,
    )

@router.post("/auth/register", response_model=AuthResponse)
async def register(
    registration: RegisterRequest,
    session: Session = Depends(get_session)
):
    """
    Register a new user account. Default role is 'parent'.
    Auto-logs in the user after registration.
    Sends verification email if email is configured.
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
        role=RoleType.PARENT,  # Default role
        email_verified=False
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    
    # Send verification email (will be skipped if not configured)
    send_verification_email(session, user)
    
    # Create access token for auto-login
    access_token = create_access_token(user.id, user.role)
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            role=user.role,
            email_verified=user.email_verified
        )
    )

@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Get the current authenticated user's information.
    
    The `is_feis_organizer` field is True if:
    - User's role is 'organizer' or 'super_admin', OR
    - User is a co-organizer of at least one feis (FeisOrganizer entry)
    """
    # Check if user is a co-organizer of any feis
    is_feis_organizer = current_user.role in [RoleType.ORGANIZER, RoleType.SUPER_ADMIN]
    
    if not is_feis_organizer:
        # Check FeisOrganizer table
        co_org = session.exec(
            select(FeisOrganizer).where(FeisOrganizer.user_id == current_user.id)
        ).first()
        is_feis_organizer = co_org is not None
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        email_verified=current_user.email_verified,
        is_feis_organizer=is_feis_organizer
    )


# ============= Email Verification Endpoints =============

@router.post("/auth/verify-email", response_model=VerificationResponse)
async def verify_email(
    request: VerifyEmailRequest,
    session: Session = Depends(get_session)
):
    """
    Verify a user's email address using the token from the verification email.
    """
    user = verify_email_token(session, request.token)
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    return VerificationResponse(
        success=True,
        message="Email verified successfully! You can now access all features."
    )


@router.post("/auth/resend-verification", response_model=VerificationResponse)
async def resend_verification(
    request: ResendVerificationRequest,
    session: Session = Depends(get_session)
):
    """
    Resend the verification email. Rate limited to once per 60 seconds.
    """
    # Check if email is configured
    if not is_email_configured(session):
        raise HTTPException(
            status_code=503,
            detail="Email service is not configured. Please contact the administrator."
        )
    
    # Find user by email
    statement = select(User).where(User.email == request.email)
    user = session.exec(statement).first()
    
    if not user:
        # Don't reveal whether email exists
        return VerificationResponse(
            success=True,
            message="If an account exists with this email, a verification link has been sent."
        )
    
    if user.email_verified:
        return VerificationResponse(
            success=True,
            message="This email is already verified."
        )
    
    # Check rate limiting
    if not can_resend_verification(user):
        raise HTTPException(
            status_code=429,
            detail="Please wait at least 60 seconds before requesting another verification email."
        )
    
    # Send verification email
    sent = send_verification_email(session, user)
    
    if not sent:
        raise HTTPException(
            status_code=500,
            detail="Failed to send verification email. Please try again later."
        )
    
    return VerificationResponse(
        success=True,
        message="Verification email sent! Please check your inbox."
    )


@router.get("/auth/email-status")
async def get_email_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's email verification status and whether email is configured.
    """
    return {
        "email_verified": current_user.email_verified,
        "email_configured": is_email_configured(session)
    }

@router.put("/auth/profile", response_model=UserResponse)
async def update_profile(
    profile_data: ProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Update the current user's profile (name only).
    """
    if profile_data.name is not None:
        current_user.name = profile_data.name
    
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        email_verified=current_user.email_verified
    )


@router.put("/auth/password")
async def change_password(
    password_data: PasswordChangeRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Change the current user's password.
    Requires the current password for verification.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if len(password_data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    session.add(current_user)
    session.commit()
    
    return {"message": "Password changed successfully"}
