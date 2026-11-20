"""Encrypt stored M-Pesa phone numbers."""

import os

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op
from cryptography.fernet import Fernet

revision = "c4e91a7b2d60"
down_revision = "8b7d2f91c6a4"
branch_labels = None
depends_on = None


def _cipher():
    key = os.environ.get("MPESA_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "MPESA_ENCRYPTION_KEY must be loaded before running this migration."
        )
    return Fernet(key.encode())


def upgrade() -> None:
    cipher = _cipher()
    op.add_column(
        "payments",
        sa.Column("phone_number_encrypted", sa.Text(), nullable=True),
    )

    connection = op.get_bind()
    payments = sa.table(
        "payments",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("phone_number", sa.Text()),
        sa.column("phone_number_encrypted", sa.Text()),
    )

    rows = connection.execute(
        sa.select(payments.c.id, payments.c.phone_number)
    ).all()

    for payment_id, phone in rows:
        if not phone:
            raise RuntimeError(
                f"Payment {payment_id} has no phone number; migration stopped."
            )
        encrypted = cipher.encrypt(phone.encode()).decode()
        connection.execute(
            payments.update()
            .where(payments.c.id == payment_id)
            .values(phone_number_encrypted=encrypted)
        )

    op.alter_column(
        "payments",
        "phone_number_encrypted",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("payments", "phone_number")


def downgrade() -> None:
    cipher = _cipher()
    op.add_column(
        "payments",
        sa.Column("phone_number", sa.Text(), nullable=True),
    )

    connection = op.get_bind()
    payments = sa.table(
        "payments",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("phone_number", sa.Text()),
        sa.column("phone_number_encrypted", sa.Text()),
    )

    rows = connection.execute(
        sa.select(payments.c.id, payments.c.phone_number_encrypted)
    ).all()

    for payment_id, encrypted in rows:
        phone = cipher.decrypt(encrypted.encode()).decode()
        connection.execute(
            payments.update()
            .where(payments.c.id == payment_id)
            .values(phone_number=phone)
        )

    op.alter_column(
        "payments", "phone_number", existing_type=sa.Text(), nullable=False
    )
    op.drop_column("payments", "phone_number_encrypted")
