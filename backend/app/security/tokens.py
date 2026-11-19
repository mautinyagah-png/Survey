"""JWT creation and verification utilities."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt

from app.config import get_settings


settings = get_settings()


def create_access_token(
    user_id: UUID,
    session_id: UUID | None = None,
) -> str:
    """Create a short-lived access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }

    if session_id is not None:
        payload["sid"] = str(session_id)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(
    user_id: UUID,
    session_id: UUID | None = None,
) -> str:
    """Create a longer-lived refresh token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_days),
        "jti": str(UUID(int=__import__("secrets").randbits(128))),
    }

    if session_id is not None:
        payload["sid"] = str(session_id)

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str, expected_type: str = "access") -> UUID | None:
    """Validate a JWT and return its user ID."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != expected_type:
            return None

        subject = payload.get("sub")
        if not subject:
            return None

        return UUID(subject)

    except (JWTError, ValueError, TypeError):
        return None


def decode_token_session(
    token: str,
    expected_type: str,
) -> tuple[UUID, UUID] | None:
    """Validate a session-bound JWT and return user and session IDs."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("type") != expected_type:
            return None

        return UUID(payload["sub"]), UUID(payload["sid"])

    except (JWTError, KeyError, ValueError, TypeError):
        return None
