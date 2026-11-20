"""Subscription API response schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SubscriptionPlanPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    tier_rank: int
    price_amount: Decimal | None
    currency: str
    billing_period: str


class CurrentSubscriptionPublic(BaseModel):
    tier: str
    tier_rank: int
    status: str
    starts_at: datetime | None
    ends_at: datetime | None


class SubscriptionMe(BaseModel):
    tier: str
    tier_rank: int
    subscription: CurrentSubscriptionPublic | None
