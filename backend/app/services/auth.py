"""Authentication and account registration services."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.identity import (
    EmailVerification,
    PasswordResetToken,
    Role,
    User,
    UserPreference,
    UserSession,
)
from app.models.rewards import Wallet
from app.schemas.auth import RegisterRequest
from app.security.passwords import hash_password, verify_password


class EmailAlreadyRegistered(Exception):
    """Raised when an email address is already registered."""


class AccountNotActive(Exception):
    """Raised when an account cannot authenticate."""


class InvalidVerificationToken(Exception):
    """Raised when an email verification token is invalid or expired."""


class InvalidPasswordResetToken(Exception):
    """Raised when a password reset token is invalid or expired."""


def hash_token(token: str) -> str:
    """Return a SHA-256 hash of a verification token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(
    db: Session,
    data: RegisterRequest,
) -> tuple[User, str]:
    """Create a respondent account and an email verification token."""

    email = str(data.email).lower()

    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if existing_user:
        raise EmailAlreadyRegistered

    respondent_role = db.scalar(
        select(Role).where(Role.name == "respondent")
    )

    if respondent_role is None:
        raise RuntimeError("The respondent role is missing from the database.")

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)

    user = User(
        email=email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        country_code=data.country_code,
        role_id=respondent_role.id,
        status="pending",
    )

    db.add(user)

    try:
        db.flush()

        preferences = UserPreference(user_id=user.id)
        wallet = Wallet(
            user_id=user.id,
            currency=user.preferred_currency or "KES",
        )

        verification = EmailVerification(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(hours=24),
        )

        db.add_all([preferences, verification, wallet])
        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()
        raise EmailAlreadyRegistered from None

    return user, raw_token


def verify_email(db: Session, raw_token: str) -> User:
    """Verify an email address and activate its account."""

    now = datetime.now(timezone.utc)
    token_hash = hash_token(raw_token)

    verification = db.scalar(
        select(EmailVerification).where(
            EmailVerification.token_hash == token_hash,
            EmailVerification.consumed_at.is_(None),
            EmailVerification.expires_at > now,
        )
    )

    if verification is None:
        raise InvalidVerificationToken

    user = db.get(User, verification.user_id)

    if user is None or user.status != "pending":
        raise InvalidVerificationToken

    verification.consumed_at = now
    user.email_verified_at = now
    user.status = "active"

    db.commit()
    db.refresh(user)

    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User | None:
    """Authenticate an active, email-verified user."""

    normalized_email = email.strip().lower()

    user = db.scalar(
        select(User).where(func.lower(User.email) == normalized_email)
    )

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if user.status != "active" or user.email_verified_at is None:
        raise AccountNotActive

    user.last_login_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return user


def request_password_reset(db: Session, email: str) -> str | None:
    """Create a one-hour password reset token for an active account."""
    normalized_email = email.strip().lower()
    user = db.scalar(
        select(User).where(
            func.lower(User.email) == normalized_email,
            User.status == "active",
            User.email_verified_at.is_not(None),
        )
    )

    if user is None:
        return None

    now = datetime.now(timezone.utc)

    # Invalidate any previous unused reset tokens.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    raw_token = secrets.token_urlsafe(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=now + timedelta(hours=1),
        )
    )
    db.commit()

    return raw_token


def reset_user_password(
    db: Session,
    raw_token: str,
    new_password: str,
) -> None:
    """Reset a user's password using a valid one-time token."""
    now = datetime.now(timezone.utc)

    reset_token = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(raw_token),
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )

    if reset_token is None:
        raise InvalidPasswordResetToken

    user = db.get(User, reset_token.user_id)

    if user is None or user.status != "active":
        raise InvalidPasswordResetToken

    reset_token.consumed_at = now
    user.password_hash = hash_password(new_password)

    # Invalidate every other outstanding reset token for this account.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    # Revoke all active login sessions after a password reset.
    db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    db.commit()
