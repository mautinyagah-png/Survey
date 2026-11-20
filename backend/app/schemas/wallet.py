"""Respondent wallet API response schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WalletBalancePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    currency: str
    pending_balance: Decimal
    available_balance: Decimal
    total_earned: Decimal
    created_at: datetime
    updated_at: datetime


class WalletTransactionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    amount: Decimal
    currency: str
    reference_type: str | None
    reference_id: UUID | None
    description: str | None
    created_at: datetime


class WalletTransactionPage(BaseModel):
    items: list[WalletTransactionPublic]
    total: int
    limit: int
    offset: int
