"""Authenticated respondent wallet endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.models.rewards import Wallet, WalletTransaction
from app.schemas.wallet import (
    WalletBalancePublic,
    WalletTransactionPage,
)
from app.security.dependencies import get_current_user

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("/me", response_model=list[WalletBalancePublic])
def my_wallets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all currency wallets belonging to the authenticated user."""

    return db.scalars(
        select(Wallet)
        .where(Wallet.user_id == user.id)
        .order_by(Wallet.currency.asc())
    ).all()


@router.get("/me/transactions", response_model=WalletTransactionPage)
def my_wallet_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return paginated wallet transactions belonging to the current user."""

    filters = WalletTransaction.user_id == user.id

    total = db.scalar(
        select(func.count())
        .select_from(WalletTransaction)
        .where(filters)
    ) or 0

    transactions = db.scalars(
        select(WalletTransaction)
        .where(filters)
        .order_by(
            WalletTransaction.created_at.desc(),
            WalletTransaction.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return WalletTransactionPage(
        items=transactions,
        total=total,
        limit=limit,
        offset=offset,
    )
