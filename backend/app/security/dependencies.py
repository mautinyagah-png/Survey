"""Authentication dependencies for protected API routes."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import Role, User, UserSession
from app.security.tokens import decode_token_session


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UserSession:
    """Return the active database session for a valid access token."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or revoked authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    claims = decode_token_session(
        credentials.credentials,
        expected_type="access",
    )

    if claims is None:
        raise unauthorized

    user_id, session_id = claims
    session = db.get(UserSession, session_id)

    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(timezone.utc)
    ):
        raise unauthorized

    user = db.get(User, user_id)

    if (
        user is None
        or user.status != "active"
        or user.email_verified_at is None
    ):
        raise unauthorized

    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    """Return the active user identified by a valid session."""
    user = db.get(User, session.user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication account no longer exists.",
        )

    return user



def get_admin_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Allow only administrators and super administrators."""
    role_name = db.scalar(
        select(Role.name).where(Role.id == current_user.role_id)
    )

    if role_name not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator permissions are required.",
        )

    return current_user


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return an authenticated user, or None for an anonymous visitor."""

    if credentials is None:
        return None

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or revoked authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials.scheme.lower() != "bearer":
        raise unauthorized

    claims = decode_token_session(
        credentials.credentials,
        expected_type="access",
    )

    if claims is None:
        raise unauthorized

    user_id, session_id = claims
    session = db.get(UserSession, session_id)

    if (
        session is None
        or session.user_id != user_id
        or session.revoked_at is not None
        or session.expires_at <= datetime.now(timezone.utc)
    ):
        raise unauthorized

    user = db.get(User, user_id)

    if (
        user is None
        or user.status != "active"
        or user.email_verified_at is None
    ):
        raise unauthorized

    return user
