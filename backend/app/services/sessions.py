"""Database-backed authentication session services."""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.identity import User, UserSession
from app.security.tokens import (
    create_refresh_token,
    decode_token_session,
)


settings = get_settings()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(
    db: Session,
    user: User,
) -> tuple[UUID, str]:
    """Create a session and its initial refresh token."""
    now = datetime.now(timezone.utc)
    session_id = uuid4()
    refresh_token = create_refresh_token(user.id, session_id)

    db.add(
        UserSession(
            id=session_id,
            user_id=user.id,
            refresh_token_hash=_hash_token(refresh_token),
            expires_at=now + timedelta(days=settings.refresh_token_days),
            last_used_at=now,
        )
    )
    db.commit()

    return session_id, refresh_token


def rotate_refresh_token(
    db: Session,
    raw_token: str,
) -> tuple[User, UUID, str] | None:
    """Validate and rotate a session's refresh token exactly once."""
    claims = decode_token_session(raw_token, "refresh")

    if claims is None:
        return None

    user_id, session_id = claims
    now = datetime.now(timezone.utc)

    session = db.scalar(
        select(UserSession)
        .where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
        )
        .with_for_update()
    )

    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or not hmac.compare_digest(
            session.refresh_token_hash,
            _hash_token(raw_token),
        )
    ):
        return None

    user = db.get(User, user_id)

    if (
        user is None
        or user.status != "active"
        or user.email_verified_at is None
    ):
        return None

    new_token = create_refresh_token(user.id, session.id)
    session.refresh_token_hash = _hash_token(new_token)
    session.expires_at = now + timedelta(days=settings.refresh_token_days)
    session.last_used_at = now

    db.commit()

    return user, session.id, new_token


def revoke_user_session(db: Session, session: UserSession) -> None:
    """Revoke a login session."""
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
