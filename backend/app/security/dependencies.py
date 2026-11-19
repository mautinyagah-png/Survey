"""Authentication dependencies for protected API routes."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User, UserSession
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
