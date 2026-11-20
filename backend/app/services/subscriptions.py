"""Subscription entitlement and access-tier verification."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.subscriptions import SubscriptionPlan, UserSubscription

TIER_RANKS = {
    "basic": 1,
    "bronze": 2,
    "silver": 3,
    "gold": 4,
    "platinum": 5,
}


def get_effective_subscription(db: Session, user_id: UUID) -> dict:
    """Return the highest currently valid paid subscription, or Basic."""

    now = datetime.now(timezone.utc)

    result = db.execute(
        select(UserSubscription, SubscriptionPlan)
        .join(SubscriptionPlan, UserSubscription.plan_id == SubscriptionPlan.id)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == "active",
            SubscriptionPlan.is_active.is_(True),
            or_(
                UserSubscription.starts_at.is_(None),
                UserSubscription.starts_at <= now,
            ),
            or_(
                UserSubscription.ends_at.is_(None),
                UserSubscription.ends_at > now,
            ),
        )
        .order_by(SubscriptionPlan.tier_rank.desc())
    ).first()

    if result is None:
        return {
            "tier": "basic",
            "tier_rank": 1,
            "subscription": None,
        }

    subscription, plan = result

    return {
        "tier": plan.code,
        "tier_rank": plan.tier_rank,
        "subscription": subscription,
        "plan": plan,
    }


def can_access_tier(user_tier_rank: int, required_tier: str) -> bool:
    """Check whether the user's rank meets a survey's required tier."""
    required_rank = TIER_RANKS.get(required_tier)

    if required_rank is None:
        return False

    return user_tier_rank >= required_rank


def require_survey_tier(
    db: Session,
    user_id: UUID,
    required_tier: str,
) -> dict:
    """Raise no exceptions; return entitlement details for route handling."""

    entitlement = get_effective_subscription(db, user_id)
    entitlement["has_access"] = can_access_tier(
        entitlement["tier_rank"], required_tier
    )
    entitlement["required_tier"] = required_tier
    return entitlement
