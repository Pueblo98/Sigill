import os
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class Config(BaseModel):
    DATABASE_URL: str = Field(default="postgresql+asyncpg://sigil:sigil@localhost:5432/sigil")

    DB_POOL_MIN: int = 5
    DB_POOL_MAX: int = 50
    HTTPX_PER_HOST_LIMIT: int = 10

    # Legacy Kalshi creds — kept for sops/env compatibility but unused by the
    # new adapter. The current Kalshi API uses RSA-PSS signed headers; provide
    # KALSHI_KEY_ID (UUID from kalshi.com → Profile → API Keys) and EITHER
    # KALSHI_PRIVATE_KEY_PEM (inline multi-line PEM) OR KALSHI_PRIVATE_KEY_PATH
    # (file containing the PEM). Without these the adapter raises on any call.
    KALSHI_API_KEY: Optional[str] = None
    KALSHI_SECRET: Optional[str] = None
    KALSHI_KEY_ID: Optional[str] = None
    KALSHI_PRIVATE_KEY_PEM: Optional[str] = None
    KALSHI_PRIVATE_KEY_PATH: Optional[str] = None
    POLYMARKET_API_KEY: Optional[str] = None

    # OddsPipe — third-party aggregator for Kalshi + Polymarket (REST only,
    # no WS). The default ingestion path: OddsPipe wraps both platforms
    # behind one X-API-Key, so a Kalshi sign-up is not required. Decision
    # 4A pegs freshness at 5 minutes. Setting ODDSPIPE_API_KEY enables the
    # source automatically; clear it to disable.
    ODDSPIPE_API_KEY: Optional[str] = None
    ODDSPIPE_BASE_URL: str = "https://oddspipe.com"
    ODDSPIPE_POLL_SECONDS: int = 300
    ODDSPIPE_MARKETS_PER_PLATFORM: int = 100

    # Direct Kalshi/Polymarket WebSocket adapters live in the codebase but
    # are off by default — OddsPipe covers both platforms. Flip this on
    # only if you want sub-second tick resolution from Polymarket and have
    # Kalshi RSA-PSS creds (KALSHI_KEY_ID + KALSHI_PRIVATE_KEY_PATH). Both
    # paths land in MarketPrice with source='exchange_ws' alongside any
    # OddsPipe ticks (source='oddspipe').
    DIRECT_EXCHANGE_WS_ENABLED: bool = False

    # Spread-arb signal — polls OddsPipe /v1/spreads and emits Predictions
    # for under-priced sides of cross-platform matches. Auto-enabled when
    # ODDSPIPE_API_KEY is set (it reuses that auth). Set
    # SPREAD_ARB_INTERVAL_SECONDS to 0 to disable while keeping OddsPipe
    # market data flowing.
    SPREAD_ARB_INTERVAL_SECONDS: int = 600   # 10 min cadence
    SPREAD_ARB_MIN_SCORE: float = 95.0       # title-match confidence; <95 is mostly noise
    SPREAD_ARB_MIN_EDGE: float = 0.05
    SPREAD_ARB_MAX_MATCHES: int = 30
    # When the two sides differ by more than this, the "match" is almost
    # certainly two different questions OddsPipe scored as similar. A real
    # cross-platform arb is usually <0.20 absolute spread.
    SPREAD_ARB_MAX_YES_DIFF: float = 0.30

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

    # Phase 1 reliability: per-market per-day Kalshi orderbook archive for
    # future replay-into-backtester (TODO-1). Off by default; live deploys
    # flip on. Reader is TODO-9.
    ORDERBOOK_ARCHIVE_ENABLED: bool = False
    ORDERBOOK_ARCHIVE_DIR: str = Field(
        default_factory=lambda: os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "orderbook_archive",
        )
    )
    ORDERBOOK_ARCHIVE_MAX_OPEN_HANDLES: int = 256


config = Config()
