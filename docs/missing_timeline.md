# Gap Analysis & Development Timeline — Sigil

## 1. Current State vs. PRD

**What's Implemented:**
- ✅ **Base Infrastructure**: Project scaffolding (`src/sigil/`), DB models (`db.py`, `models.py`), config, and basic protocol interfaces (`base.py`).
- ✅ **Execution Skeletons**: Kalshi v2 RSA signing, Polymarket adapter skeleton, ArbDetector, and Orchestrator heartbeat.
- ✅ **Dashboard Shell**: Next.js frontend (`sigil-frontend`) with "Terminal Precision" UI for all required views (Market Explorer, Health, Models, etc.) using mock data.
- ✅ **Core Engine**: Basic `MarketManager`, `TelegramAlerts`, and initial `EloRatingExtractor`.

**What's Missing (The Gap):**
1. **Data Ingestion pipelines**: No live API integrations for ESPN, The Odds API, FiveThirtyEight, RCP, FRED, Weather, or CoinGecko.
2. **Feature Store / Computation**: Missing all vertical-specific extractors beyond a stubbed Elo rater.
3. **Modeling & MLflow**: No LightGBM integration, no regression/polling average models, no LLM API (Claude) pipelines.
4. **Execution Logic**: Missing OMS state machine logic, Kelly sizing, drawdown circuit breakers, position limits tracking.
5. **Backtesting Framework**: Missing entirely (event-driven engine, metrics, walk-forward).
6. **API Layer**: FastAPI backend to feed the Next.js frontend is missing (UI currently relies on mock data).

---

## 2. Updated Development Timeline

Based on the original PRD's phases and the current repository state, here is the timeline to build the remaining missing components:

### Phase 1: Foundation Completion (Weeks 1-2)
*Goal: Complete the data ingestion layer and connect the frontend to real data.*
- **Data Ingestion (Sports & Politics)**: Implement async polling clients for ESPN, The Odds API, 538, and FRED. Store raw normalizations in PostgreSQL/TimescaleDB.
- **Backend API**: Build the FastAPI service (`src/sigil/api/`) to serve live Postgres data to the Next.js UI, linking the frontend.
- **Initial Features**: Solidify the `EloRatingExtractor` and build the weighted polling average extractor.
- **Paper Trading Engine**: Enable passive execution logging to track trades locally without exchange exposure.

### Phase 2: Modeling & Risk Management (Weeks 3-5)
*Goal: Train baseline models, validate them, and deploy safe automated execution.*
- **LightGBM & Basics**: Implement LightGBM training wrappers for NFL/NBA, and base LR for politics. Set up model tracking via MLflow.
- **Backtesting Framework**: Implement the event-driven backtesting engine (`src/sigil/backtesting/engine.py`) and standard metrics (Brier, Log Loss, Calibration error).
- **Risk System / OMS**: Finalize the Order Management System state machine. Add fractional Kelly Criterion sizing and drawdown circuit breakers (limit, halt, shutdown).
- **Automated Execution**: Graduate from paper trading to automated live execution on Kalshi with minimum sizing constraints.

### Phase 3: Expansion & LLMs (Weeks 6-8)
*Goal: Incorporate advanced qualitative signals and scale secondary exchanges.*
- **LLM Pipeline (Claude API)**: Create automated signal extraction logic for injury report severity classification and political debate analysis.
- **Polymarket Live**: Finalize the Polymarket execution adapter and enable execution of cross-platform arbitrage signals.
- **Macro & Weather Verticals**: Add ingestion for NWS, Open-Meteo, and CME FedWatch. Configure ensemble model consensus.
- **Dashboard Upgrades**: Replace static SVG charts with dynamic Recharts visualizations for model calibration and real-time active P&L tracing.

### Phase 4: Full Autonomy & Optimization (Weeks 9+)
*Goal: Operations scaling, auto-retraining, and multi-vertical coverage.*
- **Experimental Models**: Add the Crypto vertical (CoinGecko, DeFi Llama) and Entertainment vertical scraping (Gold Derby).
- **Champion/Challenger Framework**: Establish the automated A/B testing continuous loop for models. Implement feature drift auto-detection (PSI) triggering Telegram alerts.
- **Advanced Execution Strategies**: Implement scaled execution chunks (time-weighted scaling) for handling deeper liquidity moves without large slippage impacts.
