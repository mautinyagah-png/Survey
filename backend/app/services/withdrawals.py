"""Atomic withdrawal reservations, reviews and payout recording."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.administration import AuditLog, WithdrawalRequest
from app.models.identity import User
from app.models.rewards import Wallet, WalletTransaction

MIN_WITHDRAWAL = Decimal("2500.00")
WITHDRAWAL_FEE_RATE = Decimal("0.10")


def _now():
    return datetime.now(timezone.utc)


def _audit(
    db: Session,
    actor_id: UUID,
    action: str,
    withdrawal: WithdrawalRequest,
    metadata: dict | None = None,
):
    db.add(
        AuditLog(
            actor_user_id=actor_id,
            action=action,
            entity_type="withdrawal",
            entity_id=withdrawal.id,
            metadata_json=metadata or {},
        )
    )


def create_withdrawal(
    db: Session,
    user: User,
    amount: Decimal,
    currency: str,
    method: str,
    destination_masked: str,
) -> WithdrawalRequest:
    """Reserve available wallet funds and create a withdrawal request."""

    try:
        wallet = db.scalar(
            select(Wallet)
            .where(
                Wallet.user_id == user.id,
                Wallet.currency == currency,
            )
            .with_for_update()
        )

        if wallet is None:
            raise ValueError("You do not have a wallet in this currency.")

        if amount <= Decimal("0.00"):
            raise ValueError("Withdrawal amount must be greater than zero.")

        if amount < MIN_WITHDRAWAL:
            raise ValueError(
                f"Minimum withdrawal is KES {MIN_WITHDRAWAL:,.2f}."
            )

        if wallet.available_balance < amount:
            raise ValueError("Insufficient withdrawable balance.")

        fee = (amount * WITHDRAWAL_FEE_RATE).quantize(Decimal("0.01"))
        net = (amount - fee).quantize(Decimal("0.01"))

        now = _now()
        wallet.available_balance -= amount
        wallet.updated_at = now

        withdrawal = WithdrawalRequest(
            user_id=user.id,
            amount=amount,
            currency=currency,
            method=method,
            destination_masked=destination_masked,
            status="requested",
            requested_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(withdrawal)
        db.flush()

        db.add(
            WalletTransaction(
                user_id=user.id,
                type="hold",
                amount=amount,
                currency=currency,
                reference_type="withdrawal",
                reference_id=withdrawal.id,
                description=(
                f"Withdrawal hold. Fee: KES {fee:,.2f} "
                f"(10%). Net payout: KES {net:,.2f}."
            ),
            )
        )

        _audit(
            db,
            user.id,
            "withdrawal.requested",
            withdrawal,
            {"amount": str(amount), "currency": currency, "method": method},
        )

        db.commit()
        db.refresh(withdrawal)
        return withdrawal

    except Exception:
        db.rollback()
        raise


def list_user_withdrawals(
    db: Session,
    user_id: UUID,
    limit: int,
    offset: int,
):
    filters = WithdrawalRequest.user_id == user_id
    total = db.scalar(
        select(func.count())
        .select_from(WithdrawalRequest)
        .where(filters)
    ) or 0

    items = db.scalars(
        select(WithdrawalRequest)
        .where(filters)
        .order_by(
            WithdrawalRequest.requested_at.desc(),
            WithdrawalRequest.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return items, total


def list_admin_withdrawals(
    db: Session,
    status_filter: str | None,
    limit: int,
    offset: int,
):
    filters = []
    if status_filter:
        filters.append(WithdrawalRequest.status == status_filter)

    query = select(WithdrawalRequest)
    count_query = select(func.count()).select_from(WithdrawalRequest)

    if filters:
        query = query.where(*filters)
        count_query = count_query.where(*filters)

    total = db.scalar(count_query) or 0
    items = db.scalars(
        query.order_by(
            WithdrawalRequest.requested_at.asc(),
            WithdrawalRequest.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()

    return items, total


def _lock_withdrawal(db: Session, withdrawal_id: UUID):
    withdrawal = db.scalar(
        select(WithdrawalRequest)
        .where(WithdrawalRequest.id == withdrawal_id)
        .with_for_update()
    )
    if withdrawal is None:
        raise LookupError("Withdrawal request not found.")
    return withdrawal


def _lock_wallet(db: Session, withdrawal: WithdrawalRequest):
    wallet = db.scalar(
        select(Wallet)
        .where(
            Wallet.user_id == withdrawal.user_id,
            Wallet.currency == withdrawal.currency,
        )
        .with_for_update()
    )
    if wallet is None:
        raise ValueError("The respondent wallet could not be found.")
    return wallet


def approve_withdrawal(
    db: Session,
    withdrawal_id: UUID,
    admin: User,
    notes: str | None = None,
):
    try:
        withdrawal = _lock_withdrawal(db, withdrawal_id)
        if withdrawal.status != "requested":
            raise ValueError("Only requested withdrawals can be approved.")

        now = _now()
        withdrawal.status = "approved"
        withdrawal.reviewed_by = admin.id
        withdrawal.reviewed_at = now
        withdrawal.notes = notes
        withdrawal.updated_at = now

        _audit(db, admin.id, "withdrawal.approved", withdrawal)
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception:
        db.rollback()
        raise


def reject_withdrawal(
    db: Session,
    withdrawal_id: UUID,
    admin: User,
    notes: str | None = None,
):
    try:
        withdrawal = _lock_withdrawal(db, withdrawal_id)
        if withdrawal.status not in {"requested", "approved"}:
            raise ValueError(
                "Only requested or approved withdrawals can be rejected."
            )

        wallet = _lock_wallet(db, withdrawal)
        now = _now()

        wallet.available_balance += withdrawal.amount
        wallet.updated_at = now

        withdrawal.status = "rejected"
        withdrawal.reviewed_by = admin.id
        withdrawal.reviewed_at = now
        withdrawal.notes = notes
        withdrawal.updated_at = now

        db.add(
            WalletTransaction(
                user_id=withdrawal.user_id,
                type="release",
                amount=withdrawal.amount,
                currency=withdrawal.currency,
                reference_type="withdrawal",
                reference_id=withdrawal.id,
                description="Reserved funds released after withdrawal rejection.",
            )
        )

        _audit(db, admin.id, "withdrawal.rejected", withdrawal)
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception:
        db.rollback()
        raise


def mark_withdrawal_processing(
    db: Session,
    withdrawal_id: UUID,
    admin: User,
    notes: str | None = None,
):
    try:
        withdrawal = _lock_withdrawal(db, withdrawal_id)
        if withdrawal.status != "approved":
            raise ValueError("Only approved withdrawals can be processed.")

        withdrawal.status = "processing"
        if notes:
            withdrawal.notes = notes
        withdrawal.updated_at = _now()

        _audit(db, admin.id, "withdrawal.processing", withdrawal)
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception:
        db.rollback()
        raise


def mark_withdrawal_paid(
    db: Session,
    withdrawal_id: UUID,
    admin: User,
    payment_reference: str,
):
    """Record an externally completed payout; does not send money."""

    try:
        withdrawal = _lock_withdrawal(db, withdrawal_id)
        if withdrawal.status != "processing":
            raise ValueError(
                "Only processing withdrawals can be marked as paid."
            )

        now = _now()
        withdrawal.status = "paid"
        withdrawal.paid_at = now
        withdrawal.updated_at = now
        withdrawal.notes = (
            f"{withdrawal.notes}\n" if withdrawal.notes else ""
        ) + f"Payment reference: {payment_reference}"

        db.add(
            WalletTransaction(
                user_id=withdrawal.user_id,
                type="debit",
                amount=withdrawal.amount,
                currency=withdrawal.currency,
                reference_type="withdrawal",
                reference_id=withdrawal.id,
                description=(
                    f"Withdrawal payout recorded. Reference: {payment_reference}"
                ),
            )
        )

        _audit(
            db,
            admin.id,
            "withdrawal.paid",
            withdrawal,
            {"payment_reference": payment_reference},
        )

        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception:
        db.rollback()
        raise


def cancel_withdrawal(
    db: Session,
    withdrawal_id: UUID,
    user: User,
):
    try:
        withdrawal = _lock_withdrawal(db, withdrawal_id)
        if withdrawal.user_id != user.id:
            raise LookupError("Withdrawal request not found.")
        if withdrawal.status != "requested":
            raise ValueError(
                "Only withdrawal requests awaiting review can be cancelled."
            )

        wallet = _lock_wallet(db, withdrawal)
        now = _now()

        wallet.available_balance += withdrawal.amount
        wallet.updated_at = now
        withdrawal.status = "cancelled"
        withdrawal.updated_at = now

        db.add(
            WalletTransaction(
                user_id=user.id,
                type="release",
                amount=withdrawal.amount,
                currency=withdrawal.currency,
                reference_type="withdrawal",
                reference_id=withdrawal.id,
                description="Reserved funds released after user cancellation.",
            )
        )

        _audit(db, user.id, "withdrawal.cancelled", withdrawal)
        db.commit()
        db.refresh(withdrawal)
        return withdrawal
    except Exception:
        db.rollback()
        raise
