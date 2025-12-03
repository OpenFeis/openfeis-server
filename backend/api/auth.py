"""
Authentication utilities for Open Feis.
Handles password hashing and JWT token management.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from backend.db.database import get_session
from backend.scoring_engine.models_platform import User, RoleType

# ============= Configuration =============

# Secret key for JWT signing - in production, use environment variable
SECRET_KEY = "open-feis-super-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# ============= Password Hashing =============

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

# ============= JWT Token Management =============

def create_access_token(user_id: UUID, role: RoleType, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode = {
        "sub": str(user_id),
        "role": role.value,
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ============= OAuth2 Scheme =============

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# ============= Dependencies =============

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.
    Raises 401 if token is invalid or user not found.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = session.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

async def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    session: Session = Depends(get_session)
) -> Optional[User]:
    """
    Dependency to optionally get the current user.
    Returns None if not authenticated (doesn't raise).
    """
    if not token:
        return None
    
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id:
            return session.get(User, UUID(user_id))
    except HTTPException:
        pass
    
    return None

def require_role(*allowed_roles: RoleType):
    """
    Dependency factory to require specific roles.
    Usage: Depends(require_role(RoleType.SUPER_ADMIN, RoleType.ORGANIZER))
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker

def require_admin():
    """Shortcut for requiring super_admin role."""
    return require_role(RoleType.SUPER_ADMIN)

def require_organizer_or_admin():
    """Shortcut for requiring organizer or super_admin role."""
    return require_role(RoleType.SUPER_ADMIN, RoleType.ORGANIZER)

def require_adjudicator():
    """Shortcut for requiring adjudicator or super_admin role."""
    return require_role(RoleType.ADJUDICATOR, RoleType.SUPER_ADMIN)

