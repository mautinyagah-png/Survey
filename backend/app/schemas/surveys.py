"""Validation schemas for survey management."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SurveyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=200)
    required_tier: Literal[
        "basic", "bronze", "silver", "gold", "platinum"
    ] = "basic"
    slug: str | None = Field(default=None, min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    instructions: str | None = Field(default=None, max_length=10000)
    category_id: UUID | None = None
    target_audience: str | None = Field(default=None, max_length=500)
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    estimated_minutes: int | None = Field(default=None, gt=0, le=1440)
    reward_amount: Decimal = Field(default=Decimal("0"), ge=0, le=9999999999)
    reward_currency: str = Field(default="KES", pattern=r"^[A-Za-z]{3}$")
    allow_repeat: bool = False
    participant_target: int | None = Field(default=None, gt=0)
    closes_at: datetime | None = None

    @field_validator("title", "slug", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value):
        return value.upper() if value else value

    @field_validator("reward_currency")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper()


class SurveyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=200)
    required_tier: Literal[
        "basic", "bronze", "silver", "gold", "platinum"
    ] = "basic"
    slug: str | None = Field(default=None, min_length=3, max_length=220)
    description: str | None = Field(default=None, max_length=5000)
    instructions: str | None = Field(default=None, max_length=10000)
    category_id: UUID | None = None
    target_audience: str | None = Field(default=None, max_length=500)
    country_code: str | None = Field(default=None, pattern=r"^[A-Za-z]{2}$")
    estimated_minutes: int | None = Field(default=None, gt=0, le=1440)
    reward_amount: Decimal | None = Field(default=None, ge=0)
    reward_currency: str | None = Field(default=None, pattern=r"^[A-Za-z]{3}$")
    allow_repeat: bool | None = None
    participant_target: int | None = Field(default=None, gt=0)
    closes_at: datetime | None = None

    @field_validator("title", "slug", mode="before")
    @classmethod
    def clean_text(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value):
        return value.upper() if value else value

    @field_validator("reward_currency")
    @classmethod
    def normalize_currency(cls, value):
        return value.upper() if value else value


class SurveyPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    required_tier: str
    description: str | None
    instructions: str | None
    category_id: UUID | None
    target_audience: str | None
    country_code: str | None
    estimated_minutes: int | None
    reward_amount: Decimal
    reward_currency: str
    status: str
    allow_repeat: bool
    participant_target: int | None
    participant_count: int
    published_at: datetime | None
    closes_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SurveyCatalogueItem(BaseModel):
    id: UUID
    title: str
    required_tier: str
    is_locked: bool
    category_id: UUID | None
    estimated_minutes: int | None
    reward_amount: Decimal
    reward_currency: str


class SurveyListResponse(BaseModel):
    items: list[SurveyCatalogueItem]
    total: int
    page: int
    page_size: int
