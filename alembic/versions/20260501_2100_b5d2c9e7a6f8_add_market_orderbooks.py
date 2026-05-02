"""add market_orderbooks table

Revision ID: b5d2c9e7a6f8
Revises: a4b1c2d3e4f5
Create Date: 2026-05-01 21:00:00.000000+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5d2c9e7a6f8"
down_revision: Union[str, None] = "a4b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_orderbooks",
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("bids_json", sa.JSON(), nullable=False),
        sa.Column("asks_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["market_id"], ["markets.id"]),
        sa.PrimaryKeyConstraint("market_id", "source"),
    )
    op.create_index(
        "idx_market_orderbooks_updated",
        "market_orderbooks",
        ["updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_market_orderbooks_updated", table_name="market_orderbooks")
    op.drop_table("market_orderbooks")
