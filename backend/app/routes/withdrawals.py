"""Respondent withdrawal and admin payout processing endpoints."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.schemas.withdrawals import (
    WithdrawalCreate,
    WithdrawalDecision,
    WithdrawalPage,
    WithdrawalPublic,
)
from app.security.dependencies import get_admin_user, get_current_user
from app.services.withdrawals import (
    approve_withdrawal,
    cancel_withdrawal,
    create_withdrawal,
    list_admin_withdrawals,
    list_user_withdrawals,
    mark_withdrawal_paid,
    mark_withdrawal_processing,
    reject_withdrawal,
)

router = APIRouter(tags=["withdrawals"])


@router.post(
    "/api/wallet/me/withdrawals",
    response_model=WithdrawalPublic,
    status_code=status.HTTP_201_CREATED,
)
def request_withdrawal(
    data: WithdrawalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_withdrawal(
            db,
            user,
            data.amount,
            data.currency,
            data.method,
            data.destination_masked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/api/wallet/me/withdrawals",
    response_model=WithdrawalPage,
)
def my_withdrawals(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = list_user_withdrawals(db, user.id, limit, offset)
    return WithdrawalPage(
        items=items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/api/wallet/me/withdrawals/{withdrawal_id}/cancel",
    response_model=WithdrawalPublic,
)
def cancel_my_withdrawal(
    withdrawal_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return cancel_withdrawal(db, withdrawal_id, user)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/api/admin/withdrawals",
    response_model=WithdrawalPage,
)
def admin_withdrawal_queue(
    status_filter: Literal[
        "requested", "approved", "processing", "paid", "rejected", "cancelled"
    ] | None = Query(default="requested", alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    items, total = list_admin_withdrawals(
        db, status_filter, limit, offset
    )
    return WithdrawalPage(
        items=items, total=total, limit=limit, offset=offset
    )


@router.post(
    "/api/admin/withdrawals/{withdrawal_id}/approve",
    response_model=WithdrawalPublic,
)
def admin_approve_withdrawal(
    withdrawal_id: UUID,
    data: WithdrawalDecision,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return approve_withdrawal(
            db, withdrawal_id, admin, data.notes
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/admin/withdrawals/{withdrawal_id}/reject",
    response_model=WithdrawalPublic,
)
def admin_reject_withdrawal(
    withdrawal_id: UUID,
    data: WithdrawalDecision,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        if not data.notes:
            raise ValueError("A rejection reason is required.")
        return reject_withdrawal(
            db, withdrawal_id, admin, data.notes
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/admin/withdrawals/{withdrawal_id}/processing",
    response_model=WithdrawalPublic,
)
def admin_process_withdrawal(
    withdrawal_id: UUID,
    data: WithdrawalDecision,
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return mark_withdrawal_processing(
            db, withdrawal_id, admin, data.notes
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/api/admin/withdrawals/{withdrawal_id}/paid",
    response_model=WithdrawalPublic,
)
def admin_mark_withdrawal_paid(
    withdrawal_id: UUID,
    payment_reference: str = Query(min_length=3, max_length=120),
    admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    try:
        return mark_withdrawal_paid(
            db, withdrawal_id, admin, payment_reference.strip()
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
