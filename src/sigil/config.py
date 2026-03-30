import os
from pydantic import BaseModel, Field
from typing import Optional

class Config(BaseModel):
    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://sigil:sigil@localhost:5432/sigil")
    REDIS_URL: str = Field(default="redis://localhost:6379/0")

    # Platforms
    KALSHI_API_KEY: Optional[str] = None
    KALSHI_SECRET: Optional[str] = None
    POLYMARKET_API_KEY: Optional[str] = None
    POLYMARKET_PRIVATE_KEY: Optional[str] = None

    # Alerts
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None

    # Risk Parameters
    KELLY_FRACTION: float = 0.25
    MIN_EDGE_KALSHI: float = 0.10
    MIN_EDGE_POLYMARKET: float = 0.05
    MAX_POSITION_PCT: float = 5.0

    # Model Parameters
    BRIER_SCORE_THRESHOLD: float = 0.25

config = Config()
