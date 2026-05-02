from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean, Integer, String, Numeric, DateTime, JSON, ForeignKey,
    Index, Text, UniqueConstraint, func, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import false as sa_false
from sigil.db import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    taxonomy_l1: Mapped[str] = mapped_column(String, nullable=False)
    taxonomy_l2: Mapped[Optional[str]] = mapped_column(String)
    taxonomy_l3: Mapped[Optional[str]] = mapped_column(String)
    market_type: Mapped[str] = mapped_column(String, default="binary")
    resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolution_source: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="open")
    settlement_value: Mapped[Optional[float]] = mapped_column(Numeric)
    description: Mapped[Optional[str]] = mapped_column(Text)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=sa_false())
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("platform", "external_id"),
        Index("idx_markets_taxonomy", "taxonomy_l1", "taxonomy_l2", "status"),
        Index("idx_markets_platform", "platform", "status"),
        Index("idx_markets_archived", "archived"),
    )


class MarketPrice(Base):
    __tablename__ = "market_prices"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    bid: Mapped[Optional[float]] = mapped_column(Numeric)
    ask: Mapped[Optional[float]] = mapped_column(Numeric)
    last_price: Mapped[Optional[float]] = mapped_column(Numeric)
    volume_24h: Mapped[Optional[float]] = mapped_column(Numeric)
    open_interest: Mapped[Optional[float]] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(String, primary_key=True)


class MarketOrderbook(Base):
    """Latest top-N orderbook snapshot per (market, source).

    One row per (market_id, source). Updated every time an upstream WS
    adapter yields a tick that carries ``bids`` and ``asks`` lists. The
    market-detail page renders depth from this table when it has data;
    when empty (e.g. OddsPipe REST polling — no ladder), the page falls
    back to the top-of-book scalars in MarketPrice and shows an
    explainer.

    Stored as JSON arrays so we don't have to model each ladder level.
    Each entry is ``[price: float, size: float]`` — matches what the
    Polymarket gamma WS and Kalshi WS adapters yield. Truncate to the
    top 25 levels at write time (writer's responsibility) to keep row
    size bounded.
    """

    __tablename__ = "market_orderbooks"

    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String, primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    bids_json: Mapped[list] = mapped_column(JSON, default=list)
    asks_json: Mapped[list] = mapped_column(JSON, default=list)

    __table_args__ = (
        Index("idx_market_orderbooks_updated", "updated_at"),
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    predicted_prob: Mapped[float] = mapped_column(Numeric, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric)
    market_price_at_prediction: Mapped[Optional[float]] = mapped_column(Numeric)
    edge: Mapped[Optional[float]] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    features = relationship("PredictionFeature", back_populates="prediction", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("predicted_prob BETWEEN 0 AND 1", name="ck_predicted_prob_range"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_confidence_range"),
        Index("idx_predictions_market", "market_id", "created_at"),
        Index("idx_predictions_model", "model_id", "model_version", "created_at"),
    )


class PredictionFeature(Base):
    __tablename__ = "prediction_features"

    prediction_id: Mapped[UUID] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"), primary_key=True)
    feature_name: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    prediction = relationship("Prediction", back_populates="features")

    __table_args__ = (
        Index("idx_prediction_features_name", "feature_name", "version"),
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_order_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    external_order_id: Mapped[Optional[str]] = mapped_column(String)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    prediction_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("predictions.id"))
    mode: Mapped[str] = mapped_column(String, nullable=False, default="paper")
    side: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    order_type: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[Optional[float]] = mapped_column(Numeric)
    fees: Mapped[float] = mapped_column(Numeric, default=0)
    edge_at_entry: Mapped[Optional[float]] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("mode IN ('paper', 'live')", name="ck_orders_mode"),
        CheckConstraint("side IN ('buy', 'sell')", name="ck_orders_side"),
        CheckConstraint("outcome IN ('yes', 'no')", name="ck_orders_outcome"),
        CheckConstraint("order_type IN ('limit', 'market', 'ioc')", name="ck_orders_type"),
        Index("idx_orders_status", "status", "created_at"),
        Index("idx_orders_market", "market_id", "created_at"),
        Index("idx_orders_mode_status", "mode", "status"),
    )


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False, default="paper")
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric)
    unrealized_pnl: Mapped[Optional[float]] = mapped_column(Numeric)
    realized_pnl: Mapped[float] = mapped_column(Numeric, default=0)
    status: Mapped[str] = mapped_column(String, default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("platform", "market_id", "outcome", "mode"),
        CheckConstraint("mode IN ('paper', 'live')", name="ck_positions_mode"),
        Index("idx_positions_open", "status", "mode"),
    )


class SourceHealth(Base):
    __tablename__ = "source_health"

    check_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source_name: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(String)
    records_fetched: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (
        Index("idx_source_health_name_time", "source_name", "check_time"),
    )


class ReconciliationObservation(Base):
    """Tracks consecutive matching observations of exchange-vs-local position state.
    See REVIEW-DECISIONS.md 1D: 3 consecutive matches required before applying override."""

    __tablename__ = "reconciliation_observations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    platform: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    exchange_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    local_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    is_match: Mapped[bool] = mapped_column(default=False)
    consecutive_matches: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        Index("idx_reconciliation_market", "platform", "market_id", "observed_at"),
    )


class BankrollSnapshot(Base):
    """Periodic snapshots used for drawdown circuit breaker.
    See REVIEW-DECISIONS.md 2F: drawdown gate requires ≥20 settled trades total + ≥5 in window."""

    __tablename__ = "bankroll_snapshots"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    mode: Mapped[str] = mapped_column(String, primary_key=True)
    equity: Mapped[float] = mapped_column(Numeric, nullable=False)
    realized_pnl_total: Mapped[float] = mapped_column(Numeric, nullable=False)
    unrealized_pnl_total: Mapped[float] = mapped_column(Numeric, nullable=False)
    settled_trades_total: Mapped[int] = mapped_column(Integer, nullable=False)
    settled_trades_30d: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("mode IN ('paper', 'live')", name="ck_bankroll_mode"),
    )


class BacktestResult(Base):
    """Persisted summary of one Backtester.run() result.

    Lights up the F2 `backtest_results` dashboard widget. The widget queries
    this table by `created_at DESC LIMIT 1` and degrades to an empty state
    if the table is missing — so adding rows here is fully optional.

    Column shape mirrors the widget's documented expectations
    (src/sigil/dashboard/widgets/backtest_results.py); add columns here
    rather than renaming so the widget keeps rendering older rows.
    """

    __tablename__ = "backtest_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[Optional[str]] = mapped_column(String)
    model_id: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    initial_capital: Mapped[float] = mapped_column(Numeric, nullable=False)
    final_equity: Mapped[float] = mapped_column(Numeric, nullable=False)
    roi: Mapped[float] = mapped_column(Numeric, nullable=False)
    sharpe: Mapped[Optional[float]] = mapped_column(Numeric)
    max_drawdown: Mapped[Optional[float]] = mapped_column(Numeric)
    win_rate: Mapped[Optional[float]] = mapped_column(Numeric)
    n_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brier: Mapped[Optional[float]] = mapped_column(Numeric)
    log_loss: Mapped[Optional[float]] = mapped_column(Numeric)
    calibration_error: Mapped[Optional[float]] = mapped_column(Numeric)

    __table_args__ = (
        Index("idx_backtest_results_created", "created_at"),
        Index("idx_backtest_results_model", "model_id", "created_at"),
    )
