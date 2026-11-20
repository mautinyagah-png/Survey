"""Payment records for subscription purchases."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    CHAR,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="payments_amount_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'cancelled')",
            name="payments_status_check",
        ),
        CheckConstraint(
            "provider IN ('mpesa')",
            name="payments_provider_check",
        ),
        Index("payments_user_created_idx", "user_id", text("created_at DESC")),
        Index("payments_status_idx", "status"),
        UniqueConstraint(
            "checkout_request_id",
            name="payments_checkout_request_key",
        ),
        UniqueConstraint(
            "mpesa_receipt_number",
            name="payments_mpesa_receipt_key",
        ),
        UniqueConstraint(
            "user_id", "idempotency_key",
            name="payments_user_idempotency_key",
        ),
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
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id"),
        nullable=False,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_subscriptions.id", ondelete="SET NULL"),
    )

    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'mpesa'"),
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)

    phone_number_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    phone_number_masked: Mapped[str] = mapped_column(Text, nullable=False)

    merchant_request_id: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    checkout_request_id: Mapped[str | None] = mapped_column(Text)
    mpesa_receipt_number: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    result_code: Mapped[str | None] = mapped_column(Text)
    result_description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
