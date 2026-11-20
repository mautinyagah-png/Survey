"""Add per-currency user wallets and pending ledger movements."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d7a2f91c4b30"
down_revision = "c61218ea5952"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wallets",
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
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column(
            "pending_balance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "available_balance",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_earned",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
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
        sa.CheckConstraint(
            "pending_balance >= 0",
            name="wallets_pending_balance_check",
        ),
        sa.CheckConstraint(
            "available_balance >= 0",
            name="wallets_available_balance_check",
        ),
        sa.CheckConstraint(
            "total_earned >= 0",
            name="wallets_total_earned_check",
        ),
        sa.UniqueConstraint(
            "user_id",
            "currency",
            name="wallets_user_currency_key",
        ),
    )
    op.create_index("wallets_user_idx", "wallets", ["user_id"])

    # Existing accounts receive an empty wallet in their preferred currency.
    op.execute("""
        INSERT INTO wallets (user_id, currency)
        SELECT id, preferred_currency
        FROM users
        ON CONFLICT (user_id, currency) DO NOTHING
    """)

    op.drop_constraint(
        "wallet_transactions_type_check",
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_transactions_type_check",
        "wallet_transactions",
        "type IN ('credit', 'debit', 'hold', 'release', "
        "'pending_credit', 'pending_debit')",
    )

    # A reward can create each accounting movement only once.
    op.create_index(
        "wallet_transactions_reward_movement_unique_idx",
        "wallet_transactions",
        ["user_id", "type", "reference_type", "reference_id"],
        unique=True,
        postgresql_where=sa.text(
            "reference_type = 'reward' AND reference_id IS NOT NULL "
            "AND type IN ('pending_credit', 'pending_debit', 'credit')"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "wallet_transactions_reward_movement_unique_idx",
        table_name="wallet_transactions",
    )
    op.drop_constraint(
        "wallet_transactions_type_check",
        "wallet_transactions",
        type_="check",
    )
    op.create_check_constraint(
        "wallet_transactions_type_check",
        "wallet_transactions",
        "type IN ('credit', 'debit', 'hold', 'release')",
    )
    op.drop_index("wallets_user_idx", table_name="wallets")
    op.drop_table("wallets")
