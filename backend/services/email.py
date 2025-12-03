"""
Email service for Open Feis using Resend.
Handles sending verification emails and other transactional emails.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlmodel import Session, select

import resend

from backend.scoring_engine.models_platform import User, SiteSettings


def get_site_settings(session: Session) -> SiteSettings:
    """
    Get or create site settings (singleton pattern).
    """
    settings = session.get(SiteSettings, 1)
    if not settings:
        settings = SiteSettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def generate_verification_token() -> str:
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def is_email_configured(session: Session) -> bool:
    """Check if email sending is configured (Resend API key is set)."""
    settings = get_site_settings(session)
    return bool(settings.resend_api_key)


def send_verification_email(
    session: Session,
    user: User,
    base_url: Optional[str] = None
) -> bool:
    """
    Send a verification email to the user.
    
    Returns True if email was sent successfully, False otherwise.
    If Resend API key is not configured, returns False silently.
    """
    settings = get_site_settings(session)
    
    if not settings.resend_api_key:
        # Email not configured - skip silently
        # This allows the app to work without email in development
        return False
    
    # Generate new verification token
    token = generate_verification_token()
    user.email_verification_token = token
    user.email_verification_sent_at = datetime.utcnow()
    session.add(user)
    session.commit()
    
    # Build verification URL
    site_url = base_url or settings.site_url
    verification_url = f"{site_url}/verify-email?token={token}"
    
    # Configure Resend
    resend.api_key = settings.resend_api_key
    
    try:
        resend.Emails.send({
            "from": settings.resend_from_email,
            "to": user.email,
            "subject": f"Verify your {settings.site_name} account",
            "html": f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #16a34a; font-size: 28px; margin: 0;">☘️ {settings.site_name}</h1>
                    </div>
                    
                    <h2 style="color: #1f2937; font-size: 24px; margin-bottom: 16px;">
                        Welcome, {user.name}!
                    </h2>
                    
                    <p style="color: #4b5563; font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
                        Thanks for signing up! Please verify your email address by clicking the button below.
                    </p>
                    
                    <div style="text-align: center; margin: 32px 0;">
                        <a href="{verification_url}" 
                           style="background-color: #16a34a; color: white; padding: 14px 32px; 
                                  text-decoration: none; border-radius: 8px; font-weight: 600;
                                  font-size: 16px; display: inline-block;">
                            Verify Email Address
                        </a>
                    </div>
                    
                    <p style="color: #6b7280; font-size: 14px; line-height: 1.6;">
                        If the button doesn't work, copy and paste this link into your browser:
                        <br>
                        <a href="{verification_url}" style="color: #16a34a; word-break: break-all;">
                            {verification_url}
                        </a>
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
                    
                    <p style="color: #9ca3af; font-size: 12px; text-align: center;">
                        This link will expire in 24 hours.<br>
                        If you didn't create an account, you can safely ignore this email.
                    </p>
                </div>
            """
        })
        return True
    except Exception as e:
        # Log the error but don't crash
        print(f"Failed to send verification email: {e}")
        return False


def verify_email_token(session: Session, token: str) -> Optional[User]:
    """
    Verify an email verification token.
    
    Returns the User if token is valid and not expired, None otherwise.
    Marks the user as verified if successful.
    """
    # Find user with this token
    statement = select(User).where(User.email_verification_token == token)
    user = session.exec(statement).first()
    
    if not user:
        return None
    
    # Check if token has expired (24 hours)
    if user.email_verification_sent_at:
        expiry = user.email_verification_sent_at + timedelta(hours=24)
        if datetime.utcnow() > expiry:
            return None
    
    # Mark as verified and clear token
    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_sent_at = None
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return user


def can_resend_verification(user: User) -> bool:
    """
    Check if we can resend a verification email (rate limiting).
    Allows resending every 60 seconds.
    """
    if not user.email_verification_sent_at:
        return True
    
    elapsed = datetime.utcnow() - user.email_verification_sent_at
    return elapsed > timedelta(seconds=60)

