"""Survey participation and response models."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Participation(Base):
    __tablename__ = "participations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('in_progress', 'submitted', 'under_review', "
            "'approved', 'rejected', 'cancelled')",
            name="participations_status_check",
        ),
        Index(
            "participations_user_idx",
            "user_id",
            text("created_at DESC"),
        ),
        Index("participations_survey_idx", "survey_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    survey_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surveys.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'in_progress'")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        CheckConstraint(
            "rating_value IS NULL OR (rating_value BETWEEN 1 AND 10)",
            name="responses_rating_value_check",
        ),
        UniqueConstraint(
            "participation_id",
            "question_id",
            name="responses_participation_id_question_id_key",
        ),
        Index("responses_participation_idx", "participation_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    participation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("participations.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("survey_questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    answer_text: Mapped[str | None] = mapped_column(Text)
    rating_value: Mapped[int | None] = mapped_column(SmallInteger)
    selected_option_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True))
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
