"""Admin reward review endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.schemas.rewards import RewardAdminPublic, RewardRejectRequest
from app.security.dependencies import get_admin_user
from app.services.rewards import (
    approve_reward,
    list_pending_rewards,
    reject_reward,
)

router = APIRouter(
    prefix="/api/admin/rewards",
    tags=["admin-rewards"],
)


@router.get("/pending", response_model=list[RewardAdminPublic])
def get_pending_rewards(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items, _total = list_pending_rewards(db, limit, offset)
    return items


@router.post("/{reward_id}/approve", response_model=RewardAdminPublic)
def approve_reward_endpoint(
    reward_id: UUID,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return approve_reward(db, reward_id, admin)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/{reward_id}/reject", response_model=RewardAdminPublic)
def reject_reward_endpoint(
    reward_id: UUID,
    data: RewardRejectRequest,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return reject_reward(db, reward_id, admin, data.reason)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
