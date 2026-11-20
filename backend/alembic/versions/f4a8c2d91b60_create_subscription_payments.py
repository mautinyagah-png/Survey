"""Create subscription payment records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f4a8c2d91b60"
down_revision = "d7a2f91c4b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("subscription_plans.id"),
            nullable=False,
        ),
        sa.Column(
            "subscription_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'mpesa'"),
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("phone_number", sa.Text(), nullable=False),
        sa.Column("phone_number_masked", sa.Text(), nullable=False),
        sa.Column("merchant_request_id", sa.Text()),
        sa.Column("checkout_request_id", sa.Text()),
        sa.Column("mpesa_receipt_number", sa.Text()),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("result_code", sa.Text()),
        sa.Column("result_description", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("amount > 0", name="payments_amount_check"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'failed', 'cancelled')",
            name="payments_status_check",
        ),
        sa.CheckConstraint(
            "provider IN ('mpesa')",
            name="payments_provider_check",
        ),
        sa.UniqueConstraint(
            "checkout_request_id",
            name="payments_checkout_request_key",
        ),
        sa.UniqueConstraint(
            "mpesa_receipt_number",
            name="payments_mpesa_receipt_key",
        ),
    )

    op.create_index(
        "payments_user_created_idx",
        "payments",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index("payments_status_idx", "payments", ["status"])


def downgrade() -> None:
    op.drop_index("payments_status_idx", table_name="payments")
    op.drop_index("payments_user_created_idx", table_name="payments")
    op.drop_table("payments")
