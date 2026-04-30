"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30 00:00:00

Mirrors src/sigil/models.py at commit time. Schema is locked per
REVIEW-DECISIONS.md — only NEW tables may be added in subsequent migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("taxonomy_l1", sa.String(), nullable=False),
        sa.Column("taxonomy_l2", sa.String(), nullable=True),
        sa.Column("taxonomy_l3", sa.String(), nullable=True),
        sa.Column("market_type", sa.String(), nullable=True),
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_source", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("settlement_value", sa.Numeric(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("platform", "external_id"),
    )
    op.create_index("idx_markets_taxonomy", "markets", ["taxonomy_l1", "taxonomy_l2", "status"])
    op.create_index("idx_markets_platform", "markets", ["platform", "status"])

    op.create_table(
        "market_prices",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("market_id", sa.Uuid(), sa.ForeignKey("markets.id"), primary_key=True),
        sa.Column("source", sa.String(), primary_key=True),
        sa.Column("bid", sa.Numeric(), nullable=True),
        sa.Column("ask", sa.Numeric(), nullable=True),
        sa.Column("last_price", sa.Numeric(), nullable=True),
        sa.Column("volume_24h", sa.Numeric(), nullable=True),
        sa.Column("open_interest", sa.Numeric(), nullable=True),
    )

    op.create_table(
        "predictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("market_id", sa.Uuid(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("predicted_prob", sa.Numeric(), nullable=False),
        sa.Column("confidence", sa.Numeric(), nullable=True),
        sa.Column("market_price_at_prediction", sa.Numeric(), nullable=True),
        sa.Column("edge", sa.Numeric(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("predicted_prob BETWEEN 0 AND 1", name="ck_predicted_prob_range"),
        sa.CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_confidence_range"),
    )
    op.create_index("idx_predictions_market", "predictions", ["market_id", "created_at"])
    op.create_index("idx_predictions_model", "predictions", ["model_id", "model_version", "created_at"])

    op.create_table(
        "prediction_features",
        sa.Column("prediction_id", sa.Uuid(), sa.ForeignKey("predictions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("feature_name", sa.String(), primary_key=True),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index("idx_prediction_features_name", "prediction_features", ["feature_name", "version"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_order_id", sa.String(), nullable=False, unique=True),
        sa.Column("external_order_id", sa.String(), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("market_id", sa.Uuid(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("prediction_id", sa.Uuid(), sa.ForeignKey("predictions.id"), nullable=True),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("order_type", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("filled_quantity", sa.Integer(), nullable=True),
        sa.Column("avg_fill_price", sa.Numeric(), nullable=True),
        sa.Column("fees", sa.Numeric(), nullable=True),
        sa.Column("edge_at_entry", sa.Numeric(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="ck_orders_mode"),
        sa.CheckConstraint("side IN ('buy', 'sell')", name="ck_orders_side"),
        sa.CheckConstraint("outcome IN ('yes', 'no')", name="ck_orders_outcome"),
        sa.CheckConstraint("order_type IN ('limit', 'market', 'ioc')", name="ck_orders_type"),
    )
    op.create_index("idx_orders_status", "orders", ["status", "created_at"])
    op.create_index("idx_orders_market", "orders", ["market_id", "created_at"])
    op.create_index("idx_orders_mode_status", "orders", ["mode", "status"])

    op.create_table(
        "positions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("market_id", sa.Uuid(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(), nullable=False),
        sa.Column("current_price", sa.Numeric(), nullable=True),
        sa.Column("unrealized_pnl", sa.Numeric(), nullable=True),
        sa.Column("realized_pnl", sa.Numeric(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("platform", "market_id", "outcome", "mode"),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="ck_positions_mode"),
    )
    op.create_index("idx_positions_open", "positions", ["status", "mode"])

    op.create_table(
        "source_health",
        sa.Column("check_time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("source_name", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=True),
    )
    op.create_index("idx_source_health_name_time", "source_health", ["source_name", "check_time"])

    op.create_table(
        "reconciliation_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("market_id", sa.Uuid(), sa.ForeignKey("markets.id"), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("exchange_qty", sa.Integer(), nullable=False),
        sa.Column("local_qty", sa.Integer(), nullable=False),
        sa.Column("is_match", sa.Boolean(), nullable=True),
        sa.Column("consecutive_matches", sa.Integer(), nullable=True),
    )
    op.create_index("idx_reconciliation_market", "reconciliation_observations", ["platform", "market_id", "observed_at"])

    op.create_table(
        "bankroll_snapshots",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("mode", sa.String(), primary_key=True),
        sa.Column("equity", sa.Numeric(), nullable=False),
        sa.Column("realized_pnl_total", sa.Numeric(), nullable=False),
        sa.Column("unrealized_pnl_total", sa.Numeric(), nullable=False),
        sa.Column("settled_trades_total", sa.Integer(), nullable=False),
        sa.Column("settled_trades_30d", sa.Integer(), nullable=False),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="ck_bankroll_mode"),
    )


def downgrade() -> None:
    op.drop_table("bankroll_snapshots")
    op.drop_index("idx_reconciliation_market", table_name="reconciliation_observations")
    op.drop_table("reconciliation_observations")
    op.drop_index("idx_source_health_name_time", table_name="source_health")
    op.drop_table("source_health")
    op.drop_index("idx_positions_open", table_name="positions")
    op.drop_table("positions")
    op.drop_index("idx_orders_mode_status", table_name="orders")
    op.drop_index("idx_orders_market", table_name="orders")
    op.drop_index("idx_orders_status", table_name="orders")
    op.drop_table("orders")
    op.drop_index("idx_prediction_features_name", table_name="prediction_features")
    op.drop_table("prediction_features")
    op.drop_index("idx_predictions_model", table_name="predictions")
    op.drop_index("idx_predictions_market", table_name="predictions")
    op.drop_table("predictions")
    op.drop_table("market_prices")
    op.drop_index("idx_markets_platform", table_name="markets")
    op.drop_index("idx_markets_taxonomy", table_name="markets")
    op.drop_table("markets")
