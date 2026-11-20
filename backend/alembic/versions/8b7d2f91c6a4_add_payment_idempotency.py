"""Add per-user payment checkout idempotency."""

from alembic import op
import sqlalchemy as sa

revision = "8b7d2f91c6a4"
down_revision = "f4a8c2d91b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("idempotency_key", sa.Text(), nullable=True),
    )
    op.create_unique_constraint(
        "payments_user_idempotency_key",
        "payments",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "payments_user_idempotency_key",
        "payments",
        type_="unique",
    )
    op.drop_column("payments", "idempotency_key")
