"""Add per-question first-shown records for dwell enforcement."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e9f3a7b2c5d4"
down_revision = "c4e91a7b2d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "participation_question_views",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "participation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("participations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("survey_questions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "first_shown_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "participation_id",
            "question_id",
            name="participation_question_views_unique",
        ),
    )
    op.create_index(
        "participation_question_views_lookup_idx",
        "participation_question_views",
        ["participation_id", "question_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "participation_question_views_lookup_idx",
        table_name="participation_question_views",
    )
    op.drop_table("participation_question_views")
