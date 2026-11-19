"""Add revocable user sessions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b8f41c2d9a60"
down_revision = "34ca668d71e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("refresh_token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "refresh_token_hash",
            name="user_sessions_refresh_token_hash_key",
        ),
    )
    op.create_index(
        "user_sessions_user_idx", "user_sessions", ["user_id"]
    )
    op.create_index(
        "user_sessions_expires_idx", "user_sessions", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_index("user_sessions_expires_idx", table_name="user_sessions")
    op.drop_index("user_sessions_user_idx", table_name="user_sessions")
    op.drop_table("user_sessions")
