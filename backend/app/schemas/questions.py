from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


QuestionType = Literal[
    "single_choice", "multi_select", "yes_no", "rating",
    "short_text", "long_text", "dropdown", "date",
]


class AnswerOptionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    value: str = Field(min_length=1, max_length=500)

    @field_validator("label", "value")
    @classmethod
    def clean_text(cls, value):
        return value.strip()


class AnswerOptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_index: int
    label: str
    value: str


class QuestionCreate(BaseModel):
    question_type: QuestionType
    prompt: str = Field(min_length=1, max_length=5000)
    help_text: str | None = Field(default=None, max_length=2000)
    is_required: bool = False
    order_index: int | None = Field(default=None, ge=0)
    config: dict = Field(default_factory=dict)
    options: list[AnswerOptionCreate] = Field(default_factory=list)

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value):
        return value.strip()


class QuestionUpdate(BaseModel):
    question_type: QuestionType | None = None
    prompt: str | None = Field(default=None, min_length=1, max_length=5000)
    help_text: str | None = Field(default=None, max_length=2000)
    is_required: bool | None = None
    order_index: int | None = Field(default=None, ge=0)
    config: dict | None = None
    options: list[AnswerOptionCreate] | None = None

    @field_validator("prompt")
    @classmethod
    def clean_prompt(cls, value):
        return value.strip() if value is not None else value


class QuestionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    survey_id: UUID
    order_index: int
    question_type: str
    prompt: str
    help_text: str | None
    is_required: bool
    config: dict
    options: list[AnswerOptionPublic] = Field(default_factory=list)
