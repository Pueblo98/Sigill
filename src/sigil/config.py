import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class Config(BaseModel):
    DATABASE_URL: str = Field(default="postgresql+asyncpg://sigil:sigil@localhost:5432/sigil")

    DB_POOL_MIN: int = 5
    DB_POOL_MAX: int = 50
    HTTPX_PER_HOST_LIMIT: int = 10

    KALSHI_API_KEY: Optional[str] = None
    KALSHI_SECRET: Optional[str] = None
    POLYMARKET_API_KEY: Optional[str] = None

    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_CHAT_ID: Optional[str] = None
    TELEGRAM_CHAT_CRITICAL: Optional[str] = None
    TELEGRAM_CHAT_WARNING: Optional[str] = None
    TELEGRAM_CHAT_INFO: Optional[str] = None

    KELLY_FRACTION: float = 0.25
    MIN_EDGE_KALSHI: float = 0.10
    MIN_EDGE_POLYMARKET_DISPLAY: float = 0.05
    MAX_POSITION_PCT: float = 5.0
    MAX_CATEGORY_EXPOSURE_PCT: float = 25.0
    MAX_PLATFORM_EXPOSURE_PCT: float = 50.0
    MAX_CORRELATED_POSITION_PCT: float = 15.0

    MAX_MARKET_SLIPPAGE_CENTS: int = 2

    ORDER_TIMEOUT_SECONDS: int = 3600

    DRAWDOWN_WARNING_PCT: float = 10.0
    DRAWDOWN_HALT_PCT: float = 15.0
    DRAWDOWN_SHUTDOWN_PCT: float = 20.0
    DRAWDOWN_WINDOW_DAYS: int = 30
    DRAWDOWN_MIN_SETTLED_TOTAL: int = 20
    DRAWDOWN_MIN_SETTLED_IN_WINDOW: int = 5

    BRIER_SCORE_THRESHOLD: float = 0.25
    CALIBRATION_ERROR_WARNING: float = 0.05
    MODEL_ROI_30D_DEACTIVATION: float = -10.0

    RECONCILIATION_INTERVAL_SECONDS: int = 300
    RECONCILIATION_HYSTERESIS_MATCHES: int = 3

    SETTLEMENT_FALLBACK_POLL_INTERVAL_SECONDS: int = 3600

    ODDS_API_FRESHNESS_SECONDS: int = 300

    MAX_STALE_INTERVALS: int = 2
    ANOMALY_ZSCORE_THRESHOLD: float = 3.0
    SOURCE_FAILURE_WARNING: int = 3
    SOURCE_FAILURE_CRITICAL: int = 10

    API_BIND_HOST: str = Field(default="127.0.0.1")
    API_BIND_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    SOPS_AGE_KEY_FILE: str = Field(default_factory=lambda: str(Path.home() / ".config" / "sigil" / "age.key"))
    SECRETS_ENC_PATH: str = "secrets.enc.yaml"

    DEFAULT_MODE: str = "paper"

    BANKROLL_INITIAL: float = 5000.0

    SETTLEMENT_WS_ENABLED: bool = False  # off by default: needs Kalshi creds + connectivity

    # Phase 5 dashboard: gate the Jinja2 dashboard mount + APScheduler refresh
    # so existing tests (which import api/server.py) don't pay the cost of
    # loading dashboard.yaml or starting the refresh job.
    DASHBOARD_ENABLED: bool = False


config = Config()
