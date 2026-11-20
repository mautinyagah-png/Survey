from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParticipationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    survey_id: UUID
    status: str
    started_at: datetime
    submitted_at: datetime | None = None


class AnswerInput(BaseModel):
    question_id: UUID
    answer_text: str | None = None
    rating_value: int | None = Field(default=None, ge=1, le=10)
    selected_option_ids: list[UUID] | None = None


class ResponseBatch(BaseModel):
    answers: list[AnswerInput] = Field(min_length=1, max_length=500)


class ResponseSaveResult(BaseModel):
    saved: int
    cleared: int
    status: str
    message: str | None = None


class ParticipationSubmitResult(BaseModel):
    participation_id: UUID
    status: str
    submitted_at: datetime


class ParticipationHistoryItem(BaseModel):
    id: UUID
    survey_id: UUID
    survey_title: str
    reward_amount: float
    reward_currency: str
    status: str
    started_at: datetime
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None


class ParticipationHistoryResponse(BaseModel):
    items: list[ParticipationHistoryItem]
    total: int
    page: int
    page_size: int
