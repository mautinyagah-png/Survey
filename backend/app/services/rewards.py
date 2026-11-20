"""Atomic admin review and wallet accounting for survey rewards."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.participations import Participation
from app.models.rewards import RewardRecord, Wallet, WalletTransaction
from app.models.surveys import Survey


def list_pending_rewards(
    db: Session,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return pending rewards with respondent and survey context."""

    filters = RewardRecord.status == "pending"

    total = db.query(RewardRecord).filter(filters).count()

    rows = db.execute(
        select(
            RewardRecord,
            User.email,
            User.full_name,
            Survey.title,
            Participation.submitted_at,
        )
        .join(User, User.id == RewardRecord.user_id)
        .join(Survey, Survey.id == RewardRecord.survey_id)
        .join(
            Participation,
            Participation.id == RewardRecord.participation_id,
        )
        .where(filters)
        .order_by(RewardRecord.created_at.asc(), RewardRecord.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()

    items = []
    for reward, email, full_name, survey_title, submitted_at in rows:
        item = {
            column.name: getattr(reward, column.name)
            for column in RewardRecord.__table__.columns
        }
        item.update(
            {
                "user_email": email,
                "user_full_name": full_name,
                "survey_title": survey_title,
                "submitted_at": submitted_at,
            }
        )
        items.append(item)

    return items, total


def _lock_pending_reward(db: Session, reward_id: UUID) -> RewardRecord:
    reward = db.scalar(
        select(RewardRecord)
        .where(RewardRecord.id == reward_id)
        .with_for_update()
    )

    if reward is None:
        raise LookupError("Reward not found.")

    if reward.status != "pending":
        raise ValueError(
            f"This reward has already been {reward.status}; "
            "only pending rewards can be reviewed."
        )

    return reward


def _lock_reward_wallet(db: Session, reward: RewardRecord) -> Wallet:
    wallet = db.scalar(
        select(Wallet)
        .where(
            Wallet.user_id == reward.user_id,
            Wallet.currency == reward.currency,
        )
        .with_for_update()
    )

    if wallet is None:
        raise ValueError("The respondent wallet for this reward was not found.")

    if wallet.pending_balance < reward.amount:
        raise ValueError(
            "The wallet pending balance is insufficient for this reward."
        )

    return wallet


def _record_movement(
    db: Session,
    reward: RewardRecord,
    movement_type: str,
    description: str,
) -> None:
    if reward.amount <= Decimal("0.00"):
        return

    db.add(
        WalletTransaction(
            user_id=reward.user_id,
            type=movement_type,
            amount=reward.amount,
            currency=reward.currency,
            reference_type="reward",
            reference_id=reward.id,
            description=description,
        )
    )


def approve_reward(
    db: Session,
    reward_id: UUID,
    admin: User,
) -> RewardRecord:
    """Move a pending reward into the respondent's withdrawable balance."""

    try:
        reward = _lock_pending_reward(db, reward_id)
        wallet = _lock_reward_wallet(db, reward)

        now = datetime.now(timezone.utc)

        wallet.pending_balance -= reward.amount
        wallet.available_balance += reward.amount
        wallet.total_earned += reward.amount
        wallet.updated_at = now

        reward.status = "approved"
        reward.approved_by = admin.id
        reward.approved_at = now
        reward.updated_at = now

        _record_movement(
            db,
            reward,
            "pending_debit",
            "Pending reward released after admin approval.",
        )
        _record_movement(
            db,
            reward,
            "credit",
            "Survey reward approved and added to withdrawable balance.",
        )

        db.commit()
        db.refresh(reward)
        return reward

    except Exception:
        db.rollback()
        raise


def reject_reward(
    db: Session,
    reward_id: UUID,
    admin: User,
    reason: str,
) -> RewardRecord:
    """Remove a rejected reward from pending funds without paying it."""

    reason = reason.strip()
    if not reason:
        raise ValueError("A rejection reason is required.")

    try:
        reward = _lock_pending_reward(db, reward_id)
        wallet = _lock_reward_wallet(db, reward)

        now = datetime.now(timezone.utc)

        wallet.pending_balance -= reward.amount
        wallet.updated_at = now

        reward.status = "rejected"
        reward.rejected_reason = reason
        reward.updated_at = now

        _record_movement(
            db,
            reward,
            "pending_debit",
            f"Reward rejected by admin {admin.id}. Reason: {reason}",
        )

        db.commit()
        db.refresh(reward)
        return reward

    except Exception:
        db.rollback()
        raise
