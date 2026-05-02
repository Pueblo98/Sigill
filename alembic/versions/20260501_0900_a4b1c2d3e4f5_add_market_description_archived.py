"""add description + archived to markets

Revision ID: a4b1c2d3e4f5
Revises: 7e992ada302b
Create Date: 2026-05-01 09:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4b1c2d3e4f5"
down_revision: Union[str, None] = "7e992ada302b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.add_column(
        "markets",
        sa.Column(
            "archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "idx_markets_archived", "markets", ["archived"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_markets_archived", table_name="markets")
    op.drop_column("markets", "archived")
    op.drop_column("markets", "description")
