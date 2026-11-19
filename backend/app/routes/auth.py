"""HTTP endpoints for user authentication."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.identity import User, UserSession
from app.schemas.auth import (
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UserPublic,
)
from app.security.dependencies import get_current_session, get_current_user
from app.security.tokens import create_access_token
from app.services.sessions import (
    create_user_session,
    rotate_refresh_token,
    revoke_user_session,
)
from app.services.auth import (
    AccountNotActive,
    EmailAlreadyRegistered,
    InvalidVerificationToken,
    InvalidPasswordResetToken,
    authenticate_user,
    register_user,
    request_password_reset,
    reset_user_password,
    verify_email,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
settings = get_settings()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        user, verification_token = register_user(db, data)
    except EmailAlreadyRegistered:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    response = {
        "message": "Account created. Verify your email to activate it.",
        "user": UserPublic.model_validate(user).model_dump(mode="json"),
    }

    if settings.environment == "development":
        response["verification_token"] = verification_token

    return response


@router.post("/verify-email")
def verify(
    token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    try:
        user = verify_email(db, token)
    except InvalidVerificationToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or expired.",
        )

    return {
        "message": "Email verified successfully. Your account is now active.",
        "user": UserPublic.model_validate(user).model_dump(mode="json"),
    }


@router.post("/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        user = authenticate_user(db, str(data.email), data.password)
    except AccountNotActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in.",
        )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    session_id, refresh_token = create_user_session(db, user)

    return {
        **TokenResponse(
            access_token=create_access_token(user.id, session_id),
            refresh_token=refresh_token,
            expires_in=settings.access_token_minutes * 60,
        ).model_dump(),
        "user": UserPublic.model_validate(user).model_dump(mode="json"),
    }


@router.post("/refresh")
def refresh_access_token(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    result = rotate_refresh_token(db, refresh_token)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or already-used refresh token.",
        )

    user, session_id, new_refresh_token = result

    return {
        "access_token": create_access_token(user.id, session_id),
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_minutes * 60,
    }


@router.get("/me", response_model=UserPublic)
def get_me(
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated user's public profile."""
    return current_user




@router.post("/password-reset/request")
def request_password_reset_route(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    """Request a password reset without revealing whether an email exists."""
    token = request_password_reset(db, str(data.email))

    response = {
        "message": (
            "If an eligible account exists, password reset instructions "
            "have been generated."
        )
    }

    if token and settings.environment == "development":
        response["reset_token"] = token

    return response


@router.post("/password-reset/confirm")
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    """Set a new password using a valid reset token."""
    try:
        reset_user_password(db, data.token, data.new_password)
    except InvalidPasswordResetToken:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token is invalid, expired, or already used.",
        ) from None

    return {"message": "Password updated successfully."}



@router.post("/logout")
def logout(
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Revoke the current login session."""
    revoke_user_session(db, current_session)
    return {"message": "Logged out successfully."}
