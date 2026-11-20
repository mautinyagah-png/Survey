from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


PlanTier = Literal["basic", "bronze", "silver", "gold", "platinum"]


QuestionType = Literal[
    "single_choice", "multi_select", "yes_no", "rating",
    "short_text", "long_text", "dropdown", "date",
]


class BankTitleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    slug: str | None = Field(default=None, max_length=350)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int = Field(default=0, ge=0)
    access_tier: PlanTier = "platinum"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        return value.strip()


class BankTitleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    access_tier: PlanTier | None = None


class BankTitlePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    slug: str
    description: str | None
    sort_order: int
    is_active: bool
    access_tier: PlanTier
    question_count: int = 0


class BankOptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    value: str = Field(min_length=1, max_length=500)

    @field_validator("label", "value")
    @classmethod
    def clean_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Answer option cannot be empty.")
        return value


class BankOptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_index: int
    label: str
    value: str


class BankQuestionCreate(BaseModel):
    question_type: QuestionType
    prompt: str = Field(min_length=1, max_length=5000)
    help_text: str | None = Field(default=None, max_length=2000)
    is_required: bool = False
    order_index: int | None = Field(default=None, ge=0)
    config: dict = Field(default_factory=dict)
    options: list[BankOptionCreate] = Field(default_factory=list)

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be empty.")
        return value


class BankQuestionUpdate(BaseModel):
    question_type: QuestionType | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    help_text: str | None = Field(default=None, max_length=2000)
    is_required: bool | None = None
    order_index: int | None = Field(default=None, ge=0)
    config: dict | None = None
    options: list[BankOptionCreate] | None = None


class BankQuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title_id: UUID
    order_index: int
    question_type: str
    prompt: str
    help_text: str | None
    is_required: bool
    config: dict
    options: list[BankOptionPublic] = Field(default_factory=list)


class BankSurveyGenerate(BaseModel):
    title_ids: list[UUID] = Field(min_length=1, max_length=30)
    question_count: int = Field(default=10, ge=1, le=100)
    shuffle: bool = True
