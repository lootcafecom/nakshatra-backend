"""
Authentication: password hashing and JWT session tokens.

Kept deliberately simple for this stage — email + password, a signed
JWT returned on login, sent back as a Bearer token on subsequent
requests. No email verification, no password reset flow yet; those are
reasonable additions once there's a real email-sending service wired
up (see the master plan's "what's needed from your side" list — an
email provider like Resend/Brevo was already flagged there).
"""

from __future__ import annotations
import os
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# In production, set JWT_SECRET to a long random value and keep it secret.
# Falling back to a fixed dev value here only so the app runs out of the
# box locally — this must be overridden before real deployment.
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 14  # 14 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    # bcrypt has a 72-byte input limit; truncate defensively rather than
    # erroring on unusually long passwords.
    truncated = password.encode("utf-8")[:72]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please sign in again.",
        )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    user_id = decode_access_token(token)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required.")
    return user


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Same as get_current_user but returns None instead of raising,
    for endpoints that work for both signed-in and anonymous users."""
    if not token:
        return None
    try:
        user_id = decode_access_token(token)
    except HTTPException:
        return None
    return db.get(User, user_id)
