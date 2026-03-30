from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import (
    Column, Integer, String, Numeric, DateTime, JSON, ForeignKey, 
    Index, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
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
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint("platform", "external_id"),
        Index("idx_markets_taxonomy", "taxonomy_l1", "taxonomy_l2", "status"),
    )

class MarketPrice(Base):
    __tablename__ = "market_prices"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    bid: Mapped[Optional[float]] = mapped_column(Numeric)
    ask: Mapped[Optional[float]] = mapped_column(Numeric)
    last_price: Mapped[Optional[float]] = mapped_column(Numeric)
    volume_24h: Mapped[Optional[float]] = mapped_column(Numeric)
    open_interest: Mapped[Optional[float]] = mapped_column(Numeric)
    source: Mapped[str] = mapped_column(String, nullable=False)

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
    features_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Order(Base):
    __tablename__ = "orders"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    external_order_id: Mapped[Optional[str]] = mapped_column(String)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
    prediction_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("predictions.id"))
    side: Mapped[str] = mapped_column(String, nullable=False)  # 'buy', 'sell'
    outcome: Mapped[str] = mapped_column(String, nullable=False) # 'yes', 'no'
    order_type: Mapped[str] = mapped_column(String, nullable=False) # 'limit', 'market'
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    filled_quantity: Mapped[int] = mapped_column(Integer, default=0)
    avg_fill_price: Mapped[Optional[float]] = mapped_column(Numeric)
    fees: Mapped[float] = mapped_column(Numeric, default=0)
    status: Mapped[str] = mapped_column(String, default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Position(Base):
    __tablename__ = "positions"
    
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"), nullable=False)
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
        UniqueConstraint("platform", "market_id", "outcome"),
    )

class SourceHealth(Base):
    __tablename__ = "source_health"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    check_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    error_message: Mapped[Optional[str]] = mapped_column(String)
    records_fetched: Mapped[Optional[int]] = mapped_column(Integer)
