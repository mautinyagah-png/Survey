"""add required access tier to surveys

Revision ID: a91c7e4b2d60
Revises: e32e3dda40f3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a91c7e4b2d60"
down_revision: Union[str, None] = "e32e3dda40f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "surveys",
        sa.Column(
            "required_tier",
            sa.Text(),
            server_default=sa.text("'basic'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "surveys_required_tier_check",
        "surveys",
        "required_tier IN ('basic', 'bronze', 'silver', 'gold', 'platinum')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "surveys_required_tier_check",
        "surveys",
        type_="check",
    )
    op.drop_column("surveys", "required_tier")
