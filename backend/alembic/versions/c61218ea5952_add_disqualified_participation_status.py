"""Add disqualified participation status."""

from alembic import op


revision = "c61218ea5952"
down_revision = "a91c7e4b2d60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "participations_status_check",
        "participations",
        type_="check",
    )
    op.create_check_constraint(
        "participations_status_check",
        "participations",
        "status IN ('in_progress', 'submitted', 'under_review', "
        "'approved', 'rejected', 'cancelled', 'disqualified')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE participations "
        "SET status = 'rejected' "
        "WHERE status = 'disqualified'"
    )
    op.drop_constraint(
        "participations_status_check",
        "participations",
        type_="check",
    )
    op.create_check_constraint(
        "participations_status_check",
        "participations",
        "status IN ('in_progress', 'submitted', 'under_review', "
        "'approved', 'rejected', 'cancelled')",
    )
