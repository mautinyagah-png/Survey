"""Subscription plan and current entitlement endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.identity import User
from app.models.subscriptions import SubscriptionPlan
from app.schemas.subscriptions import (
    CurrentSubscriptionPublic,
    SubscriptionMe,
    SubscriptionPlanPublic,
)
from app.security.dependencies import get_current_user
from app.services.subscriptions import get_effective_subscription

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/plans", response_model=list[SubscriptionPlanPublic])
def list_subscription_plans(db: Session = Depends(get_db)):
    return db.scalars(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.tier_rank)
    ).all()


@router.get("/me", response_model=SubscriptionMe)
def my_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entitlement = get_effective_subscription(db, user.id)
    subscription = entitlement["subscription"]

    current = None
    if subscription is not None:
        current = CurrentSubscriptionPublic(
            tier=entitlement["tier"],
            tier_rank=entitlement["tier_rank"],
            status=subscription.status,
            starts_at=subscription.starts_at,
            ends_at=subscription.ends_at,
        )

    return SubscriptionMe(
        tier=entitlement["tier"],
        tier_rank=entitlement["tier_rank"],
        subscription=current,
    )
