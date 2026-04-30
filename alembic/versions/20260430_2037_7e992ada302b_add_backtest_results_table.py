"""add backtest_results table

Revision ID: 7e992ada302b
Revises: 0001
Create Date: 2026-04-30 20:37:58.202467+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7e992ada302b"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("initial_capital", sa.Numeric(), nullable=False),
        sa.Column("final_equity", sa.Numeric(), nullable=False),
        sa.Column("roi", sa.Numeric(), nullable=False),
        sa.Column("sharpe", sa.Numeric(), nullable=True),
        sa.Column("max_drawdown", sa.Numeric(), nullable=True),
        sa.Column("win_rate", sa.Numeric(), nullable=True),
        sa.Column("n_trades", sa.Integer(), nullable=False),
        sa.Column("brier", sa.Numeric(), nullable=True),
        sa.Column("log_loss", sa.Numeric(), nullable=True),
        sa.Column("calibration_error", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_backtest_results_created", "backtest_results", ["created_at"], unique=False
    )
    op.create_index(
        "idx_backtest_results_model",
        "backtest_results",
        ["model_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_backtest_results_model", table_name="backtest_results")
    op.drop_index("idx_backtest_results_created", table_name="backtest_results")
    op.drop_table("backtest_results")
