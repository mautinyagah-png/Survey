"""Administrator-only respondent account management."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import Role, User
from app.schemas.admin_users import (
    AdminUserPage,
    AdminUserPublic,
    AdminUserStatusUpdate,
)
from app.security.dependencies import get_admin_user

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])

def public_user(user: User, role_name: str) -> AdminUserPublic:
    return AdminUserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=role_name,
        status=user.status,
        preferred_currency=user.preferred_currency,
        email_verified_at=user.email_verified_at,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )

@router.get("/", response_model=AdminUserPage)
def list_respondents(
    search: str | None = Query(default=None, max_length=120),
    status_filter: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|active|suspended|deleted)$",
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """List respondent accounts only; never expose administrator accounts."""
    filters = [Role.name == "respondent"]

    if status_filter:
        filters.append(User.status == status_filter)

    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                User.email.ilike(term),
                User.full_name.ilike(term),
            )
        )

    total = db.scalar(
        select(func.count(User.id))
        .join(Role, Role.id == User.role_id)
        .where(*filters)
    ) or 0

    rows = db.execute(
        select(User, Role.name)
        .join(Role, Role.id == User.role_id)
        .where(*filters)
        .order_by(User.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    return AdminUserPage(
        items=[public_user(user, role_name) for user, role_name in rows],
        total=total,
        limit=limit,
        offset=offset,
    )

@router.patch("/{user_id}/status", response_model=AdminUserPublic)
def update_respondent_status(
    user_id: UUID,
    data: AdminUserStatusUpdate,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """Activate or suspend a respondent without changing account roles."""
    user = db.get(User, user_id)

    if user is None:
        raise HTTPException(status_code=404, detail="User account not found.")

    role_name = db.scalar(
        select(Role.name).where(Role.id == user.role_id)
    )

    if role_name != "respondent":
        raise HTTPException(
            status_code=403,
            detail="Administrator accounts cannot be changed here.",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=403,
            detail="You cannot change your own account status here.",
        )

    user.status = data.status
    db.commit()
    db.refresh(user)

    return public_user(user, role_name)
