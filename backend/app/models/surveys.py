"""Survey categories, surveys, questions, and answer option models."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SurveyCategory(Base):
    __tablename__ = "survey_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="surveys_estimated_minutes_check",
        ),
        CheckConstraint(
            "reward_amount >= 0",
            name="surveys_reward_amount_check",
        ),
        CheckConstraint(
            "status IN ('draft', 'published', 'closed', 'archived')",
            name="surveys_status_check",
        ),
        CheckConstraint(
            "participant_target IS NULL OR participant_target > 0",
            name="surveys_participant_target_check",
        ),
        CheckConstraint(
            "participant_count >= 0",
            name="surveys_participant_count_check",
        ),
        Index("surveys_category_idx", "category_id"),
        Index("surveys_status_idx", "status"),
        Index("surveys_published_at_idx", text("published_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("survey_categories.id", ondelete="SET NULL"),
    )
    target_audience: Mapped[str | None] = mapped_column(Text)
    country_code: Mapped[str | None] = mapped_column(CHAR(2))
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)
    reward_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )
    reward_currency: Mapped[str] = mapped_column(
        CHAR(3), nullable=False, server_default=text("'KES'")
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'draft'")
    )
    allow_repeat: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    participant_target: Mapped[int | None] = mapped_column(Integer)
    participant_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    closes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"
    __table_args__ = (
        CheckConstraint(
            "order_index >= 0",
            name="survey_questions_order_index_check",
        ),
        CheckConstraint(
            "question_type IN ('single_choice', 'multi_select', 'yes_no', "
            "'rating', 'short_text', 'long_text', 'dropdown', 'date')",
            name="survey_questions_question_type_check",
        ),
        Index("survey_questions_survey_idx", "survey_id", "order_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surveys.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    help_text: Mapped[str | None] = mapped_column(Text)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AnswerOption(Base):
    __tablename__ = "answer_options"
    __table_args__ = (
        CheckConstraint(
            "order_index >= 0",
            name="answer_options_order_index_check",
        ),
        Index("answer_options_question_idx", "question_id", "order_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("survey_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
