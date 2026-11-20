"""Withdrawal request and administration schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WithdrawalCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="KES", min_length=3, max_length=3)
    method: Literal["mpesa", "bank_transfer", "other"]
    destination_masked: str = Field(min_length=4, max_length=120)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("destination_masked")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 4:
            raise ValueError("A valid masked payment destination is required.")
        return value


class WithdrawalDecision(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class WithdrawalPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    method: str
    destination_masked: str
    status: str
    requested_at: datetime
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    paid_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class WithdrawalPage(BaseModel):
    items: list[WithdrawalPublic]
    total: int
    limit: int
    offset: int
