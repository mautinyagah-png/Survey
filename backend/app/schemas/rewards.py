"""Admin reward review schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RewardAdminPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    participation_id: UUID
    user_id: UUID
    survey_id: UUID
    amount: Decimal
    currency: str
    status: str
    approved_by: UUID | None
    approved_at: datetime | None
    rejected_reason: str | None
    created_at: datetime
    updated_at: datetime
    user_email: str | None = None
    user_full_name: str | None = None
    survey_title: str | None = None
    submitted_at: datetime | None = None


class RewardRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A rejection reason is required.")
        return value
