# SIGIL — Product Requirements Document

**Prediction Market Trading Platform**
**Version:** 1.0
**Date:** 2026-03-29
**Classification:** Internal — Confidential

---

## Executive Summary

Prediction markets are structurally inefficient. They are dominated by retail participants who trade on vibes, anchoring bias, and stale information. Markets on Kalshi routinely misprice binary events by 5–15 cents relative to model-fair value. Polymarket's thin order books allow informed participants to extract edge that would evaporate in milliseconds on traditional exchanges.

**Sigil** is a modular, data-driven prediction market trading platform that systematically identifies, quantifies, and exploits mispricings across Kalshi, Polymarket, Metaculus, PredictIt, and any future prediction exchange. It aggregates cross-market data from dozens of sources per vertical — sports stats, polling data, weather models, on-chain metrics, economic indicators — and transforms that data into calibrated probability estimates. When those estimates diverge from market-implied prices by more than the cost of trading, Sigil executes.

The platform is built for a solo operator scaling to a small team. Every architectural decision optimizes for iteration speed, operational simplicity, and signal quality — not enterprise scalability. The initial deployment targets Sports and Politics verticals on Kalshi, with Polymarket as the secondary venue.

**Target financial performance:** 15–25% monthly ROI on deployed capital within 6 months of live trading, with max drawdown under 20% and a prediction Brier score below 0.20 across tracked categories.

---

## Table of Contents

1. [System Identity & Vision](#1-system-identity--vision)
2. [Target Platforms & Market Structure](#2-target-platforms--market-structure)
3. [Data Aggregation Engine](#3-data-aggregation-engine)
4. [Modeling & Signal Generation](#4-modeling--signal-generation)
5. [Execution Engine](#5-execution-engine)
6. [System Architecture](#6-system-architecture)
7. [Dashboard & User Interface](#7-dashboard--user-interface)
8. [Modularity & Extensibility](#8-modularity--extensibility)
9. [Competitive Edge & Moat Analysis](#9-competitive-edge--moat-analysis)
10. [Development Roadmap](#10-development-roadmap)
11. [Risk & Compliance](#11-risk--compliance)
12. [Success Metrics & KPIs](#12-success-metrics--kpis)
13. [Decision Logs](#13-decision-logs)
14. [Glossary](#14-glossary)
15. [Appendices](#15-appendices)

---

## 1. System Identity & Vision

**Product Name:** Sigil

> *Sigil* — a symbol believed to have magical power. In markets, the signal is the spell.

**One-Liner:** A modular prediction market trading system that aggregates cross-market data, generates calibrated probability estimates, and executes trades where edge exceeds cost.

### 1.1 Core Thesis

Prediction markets are inefficient because:

1. **Retail-dominated order flow.** Most participants are entertainment bettors, not calibrated forecasters. They anchor to round numbers, overweight narratives, and underreact to base rates.
2. **Fragmented information.** A Kalshi politics market might misprice because no participant has bothered to pull the latest Marist poll. A Polymarket weather contract ignores the ECMWF ensemble.
3. **No systematic players (yet).** Traditional quant firms ignore these markets — the capital is too small. That is the window.
4. **Thin liquidity amplifies edge.** A $500 limit order on Polymarket can move the market 3 cents. That same mispricing, correctly identified, is free money.

Sigil exists to be the systematic player that exploits these inefficiencies before the window closes.

### 1.2 Design Philosophy

| Principle | Meaning |
|-----------|---------|
| **Modular by default** | Each betting vertical (sports, politics, etc.) is a self-contained module with its own data pipelines, features, and models. Adding a new vertical never requires touching core infrastructure. |
| **Data-first** | The platform's moat is data breadth and freshness. Data aggregation is a first-class engineering problem — not a script that runs on a cron job. |
| **Model-agnostic** | The architecture supports logistic regression through transformers through LLM-based reasoning. Models are swappable per-market. |
| **Execution-aware** | Edge without execution is an academic exercise. Every signal carries liquidity context, fee impact, and position-limit awareness. |
| **Solo-operator optimized** | Every component must be runnable on a single machine (16GB RAM, 8 cores) with cloud burst for training jobs. No microservice sprawl. |

---

## 2. Target Platforms & Market Structure

### 2.1 Primary Target Exchanges

#### 2.1.1 Kalshi

| Property | Detail |
|----------|--------|
| **API** | REST API v2 + WebSocket for market data streaming. Well-documented at `trading-api.kalshi.com`. |
| **Authentication** | API key + secret, passed as headers. OAuth2 not required for personal accounts. |
| **Rate limits** | 10 requests/second for REST, 1 WebSocket connection with subscription limits per channel. |
| **Order types** | Limit, market. No IOC or FOK natively — implement client-side with cancel-after-fill logic. |
| **Fee structure** | No maker fees. Taker fee: 7 cents per contract on fill (capped). No withdrawal fees for USD. Settlement fee: none. |
| **Position limits** | $25,000 per event for most markets. Some events have lower limits ($5,000). Verified accounts required for higher tiers. |
| **Settlement** | Binary (Yes/No resolving to $1.00 or $0.00). Multi-outcome via linked binary markets. Settlement source specified per market (e.g., AP for elections, NWS for weather). |
| **Exchange data** | Order book snapshots, trade tape, volume, open interest. Historical data available via REST. |
| **Regulatory status** | CFTC-regulated designated contract market (DCM). Legal for US persons. |

#### 2.1.2 Polymarket

| Property | Detail |
|----------|--------|
| **API** | REST API + WebSocket (CLOB API). Runs on Polygon (Ethereum L2). Order placement requires on-chain signatures. Uses the CTF (Conditional Token Framework). |
| **Authentication** | Ethereum wallet signature (EIP-712). API key for read endpoints. Private key required for order signing. |
| **Rate limits** | 100 requests/minute for REST. WebSocket rate limits undocumented — respect 1 connection, batch subscriptions. |
| **Order types** | Limit (GTC, GTD), market (FOK). Native IOC support. |
| **Fee structure** | Maker: 0%. Taker: ~2% (varies). Gas fees on Polygon (~$0.01). Withdrawal to Ethereum L1 has bridge fees. |
| **Position limits** | None enforced by protocol. Practical limits from liquidity depth. |
| **Settlement** | Binary ($1/$0) and scalar (range markets). Resolved by UMA optimistic oracle or designated resolution source. |
| **Exchange data** | Full order book via CLOB API, trade history, on-chain settlement data. Richer historical data than Kalshi. |
| **Regulatory status** | Not CFTC-regulated. Blocked for US persons (geo-fenced). Accessible via non-US jurisdiction or with legal considerations. |

#### 2.1.3 PredictIt

| Property | Detail |
|----------|--------|
| **API** | No official REST API. Unofficial API exists via reverse-engineering the web app. Fragile — breaks on UI updates. Web scraping is the reliable fallback. |
| **Authentication** | Session cookies from browser auth. No API keys. |
| **Rate limits** | Undocumented. Aggressive polling gets IP-banned. Recommend ≤1 req/5s. |
| **Order types** | Limit only. No market orders. |
| **Fee structure** | 10% on profits per share. 5% withdrawal fee. These fees are brutal — minimum edge to trade must be higher here. |
| **Position limits** | 850 shares per contract ($850 max investment per outcome). Severe constraint. |
| **Settlement** | Binary. Resolved by PredictIt staff (opaque process, occasionally controversial). |
| **Exchange data** | Current prices, trade history (limited). No order book depth. |
| **Regulatory status** | Operated under CFTC no-action letter (expired/under review). US-accessible but future uncertain. |

**Recommendation:** Deprioritize PredictIt. Fees destroy edge, position limits cap returns, and the API is unreliable. Monitor only — trade here only for extreme mispricings (>15 cent edge after fees).

#### 2.1.4 Metaculus

| Property | Detail |
|----------|--------|
| **API** | REST API at `metaculus.com/api2/`. Read-only for questions, community predictions, and resolution data. Prediction submission via authenticated POST. |
| **Authentication** | Session token via login endpoint. |
| **Role** | Metaculus is not a trading venue — it's a calibration benchmark and signal source. Use community median/mean predictions as features, not as a place to deploy capital. Track personal Brier score against community as a model validation tool. |
| **Data value** | Community prediction time series, question metadata, resolution outcomes. Gold standard for calibration benchmarking. |

#### 2.1.5 Generic Future Exchange Adapter

Define an abstract interface that any new platform must implement:

```python
class ExchangeAdapter(Protocol):
    def get_markets(self, filters: MarketFilter) -> list[Market]: ...
    def get_orderbook(self, market_id: str) -> OrderBook: ...
    def get_trades(self, market_id: str, since: datetime) -> list[Trade]: ...
    def place_order(self, order: Order) -> OrderResult: ...
    def cancel_order(self, order_id: str) -> CancelResult: ...
    def get_positions(self) -> list[Position]: ...
    def get_balance(self) -> Balance: ...
    def stream_orderbook(self, market_id: str) -> AsyncIterator[OrderBookUpdate]: ...
    def stream_trades(self, market_id: str) -> AsyncIterator[Trade]: ...
```

### 2.2 Market Taxonomy

A universal taxonomy normalizes events across exchanges:

**Level 1 → Level 2 → Level 3:**

```
Sports
├── NFL → Game Winner, Point Spread, Total Points, Player Props, Season Futures, MVP, Draft
├── NBA → Game Winner, Spread, Total, Player Props, MVP, Champion
├── MLB → Game Winner, Run Line, Total, Player Props, World Series
├── Soccer → Match Result, Goals O/U, UCL/World Cup Winner, Transfer Markets
├── Tennis → Match Winner, Set Spread, Grand Slam Winner
├── Golf → Tournament Winner, Top 5/10/20, Head-to-Head
├── Esports → Match Winner, Map Winner, Tournament Winner
├── MMA/Boxing → Fight Winner, Method of Victory, Round Betting
└── Olympics → Medal Winners, Country Medal Count

Politics
├── US Federal → Presidential Election, Senate Races, House Control, Legislation Passage
├── US State → Governor Races, Ballot Measures
├── International → UK Elections, EU Parliament, Leadership Changes
├── Policy → Fed Rate Decisions, Executive Orders, Treaty Ratification
└── Judicial → Supreme Court Rulings, Confirmations

Economics/Macro
├── Employment → NFP Number, Unemployment Rate, Initial Claims
├── Inflation → CPI, PCE, PPI
├── Growth → GDP, ISM, PMI
├── Central Bank → Fed Funds Rate, ECB Rate, BOJ Policy
└── Markets → S&P 500 Level, VIX Range, Treasury Yields

Entertainment/Culture
├── Awards → Oscars, Emmys, Grammys, Golden Globes
├── Box Office → Opening Weekend, Total Gross
├── Music → Billboard #1, Spotify Records
├── TV → Reality Show Winners (Survivor, Bachelor, etc.)
└── Viral/Misc → Celebrity Events, Viral Moments

Weather/Climate
├── Temperature → Monthly Records, Seasonal Averages
├── Hurricanes → Named Storm Count, Landfall Location, Category
├── Precipitation → Snowfall Totals, Drought Declarations
└── Records → Hottest Year, Sea Ice Extent

Crypto/Web3
├── Price → BTC/ETH Price Ranges, Altcoin Milestones
├── DeFi → TVL Milestones, Protocol Events
├── Regulatory → ETF Approvals, Enforcement Actions
└── Technical → Merge/Upgrade Dates, Hash Rate

Geopolitics
├── Conflicts → Ceasefire Dates, Territory Control
├── Diplomacy → Summit Outcomes, Sanctions
└── Organizations → UN Votes, NATO Expansion
```

**Market Properties Schema:**

```json
{
  "market_id": "sigil_internal_uuid",
  "external_ids": {
    "kalshi": "KXBTC-26MAR30-50000",
    "polymarket": "0x1a2b3c..."
  },
  "taxonomy": {
    "l1": "crypto",
    "l2": "price",
    "l3": "btc_price_range"
  },
  "type": "binary",
  "resolution_date": "2026-03-30T00:00:00Z",
  "resolution_source": "CoinGecko BTC/USD spot at 00:00 UTC",
  "liquidity_profile": "medium",
  "historical_analogs": ["KXBTC-26FEB28-45000", "KXBTC-26JAN31-42000"]
}
```

### 2.3 Cross-Platform Arbitrage

**Event matching logic:**

1. **Fuzzy text matching** on market titles using `rapidfuzz` (token_sort_ratio > 85).
2. **Resolution date alignment** — events must resolve within the same 24-hour window.
3. **Resolution source consistency** — verify both platforms use compatible resolution sources.
4. **Manual override** — flag uncertain matches for human review. Never auto-trade an arb on an uncertain match.

**Arbitrage identification:**

```
If Platform_A price (Yes) + Platform_B price (No on equivalent) < $1.00:
    Arb = $1.00 - Platform_A(Yes) - Platform_B(No) - fees_A - fees_B
    If Arb > $0.02 (minimum after all fees):
        Flag for execution
```

**Execution coordination:**

- Place the less liquid side first (harder to fill).
- If one side fills and the other doesn't within 30 seconds, unwind or accept the directional position if the standalone edge justifies it.
- Track arb-specific P&L separately from directional trading P&L.

**Reality check:** True cross-platform arbs are rare and usually fleeting. Build the detection system but don't overinvest in arb-specific infrastructure. Directional edge is where the money is.

---

## 3. Data Aggregation Engine

### 3.1 Data Source Catalog by Vertical

#### 3.1.1 Sports

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **ESPN API** | REST (undocumented, public) | Scores, schedules, rosters, standings | Real-time during games | Free |
| **The Odds API** | REST | Lines from 40+ sportsbooks, line movement | < 30s | $50–500/mo depending on tier |
| **Sportradar** | REST + Push | Player stats, play-by-play, injury reports | Real-time | $$$ (enterprise pricing, explore academic/startup tiers) |
| **Pro Football Reference / Basketball Reference** | Scraping | Historical stats, advanced metrics (PER, WAR, DVOA, EPA) | Daily | Free (respect robots.txt) |
| **Twitter/X API** | REST + Streaming | Injury report breaks, beat reporter tweets, sentiment | Real-time | $100/mo (Basic tier) |
| **OpenWeatherMap** | REST | Game-day weather for outdoor sports | 10-min updates | Free tier sufficient |
| **Rotowire / Fantasylabs** | Scraping | Lineup confirmations, injury updates | ~15 min | Free/low-cost tiers |

**Key features to compute:** Elo ratings (custom), home/away splits, rest days, ATS record, over/under tendency, recent form (rolling 5/10 games), strength of schedule, sharp money indicator (line movement vs. ticket count divergence).

#### 3.1.2 Politics & Geopolitics

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **FiveThirtyEight / 538** | CSV/JSON downloads | Polling averages, forecast models | Daily | Free |
| **RealClearPolitics** | Scraping | Polling averages, aggregated polls | Daily | Free |
| **FRED (Federal Reserve)** | REST API | Economic indicators (GDP, unemployment, CPI) | Per release schedule | Free |
| **Congress.gov API** | REST | Bill status, votes, cosponsors | Daily | Free |
| **OpenSecrets / FEC API** | REST | Campaign finance, fundraising | Quarterly filings + daily transactions | Free |
| **Metaculus** | REST API | Community forecasts on political events | Continuous | Free |
| **Good Judgment Open** | Scraping | Superforecaster consensus | Weekly | Free |
| **Google Trends** | `pytrends` library | Search interest as proxy for public attention | ~4hr lag | Free |

**Key features:** Polling average (weighted by recency + pollster quality), fundamentals model inputs (GDP growth, presidential approval, incumbency), generic ballot, fundraising velocity, prediction market consensus (Metaculus median), media narrative momentum (sentiment delta over 7 days).

#### 3.1.3 Entertainment & Culture

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **Gold Derby** | Scraping | Expert Oscar/Emmy/Grammy predictions, odds | Daily during awards season | Free |
| **Box Office Mojo / The Numbers** | Scraping | Box office grosses, projections | Daily | Free |
| **Spotify Charts API** | REST | Streaming counts, chart positions | Daily | Free |
| **Billboard** | Scraping | Chart positions, historical data | Weekly | Free |
| **Wikipedia Pageviews API** | REST | Page view counts as attention proxy | Daily | Free |
| **Google Trends** | `pytrends` | Search interest for nominees/contenders | ~4hr | Free |
| **TMDb / OMDb** | REST API | Film metadata, ratings, reviews | Daily | Free tier |

**Key features:** Expert consensus probability (Gold Derby odds conversion), nominee historical win rate by category, campaign spend proxy (media mentions), audience attention momentum (Wikipedia + Google Trends velocity), precursor award correlation (who won SAG → Oscar prediction).

#### 3.1.4 Economics & Macro

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **FRED API** | REST | 800K+ economic time series | Per release | Free |
| **BLS API** | REST | Employment, CPI, PPI raw data | Per release | Free |
| **Atlanta Fed GDPNow** | Scraping/REST | Real-time GDP estimate | ~Weekly updates | Free |
| **NY Fed Nowcast** | Download | GDP nowcast | Weekly | Free |
| **Trading Economics** | Scraping/API | Consensus forecasts for upcoming releases | Pre-release | $$ (API is paid) |
| **CME FedWatch** | Scraping | Implied fed funds rate probabilities | Real-time | Free |
| **Treasury.gov** | REST/Download | Yield curves, auction results | Daily | Free |
| **Bloomberg Terminal** | If available | Consensus estimates, real-time | Real-time | $$$ — skip if solo |

**Recommendation:** Skip Bloomberg. FRED + BLS + Atlanta Fed + CME FedWatch covers 90% of what you need for macro markets at zero cost.

**Key features:** Consensus forecast vs. actual (surprise factor), trend direction (3-month rolling), nowcast deviation from consensus, Fed dot plot implied path, yield curve shape metrics (2-10 spread, inversion indicator).

#### 3.1.5 Weather & Climate

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **NWS/NOAA API** | REST | Forecasts, observations, alerts, historical | Hourly forecasts | Free |
| **Open-Meteo** | REST | Global weather forecasts, historical, ensemble models | Hourly | Free (open-source!) |
| **ECMWF (via Open-Meteo)** | REST | European model ensemble (gold standard) | 6-hourly runs | Free via Open-Meteo |
| **Visual Crossing** | REST | Historical weather, 15-day forecast | Daily | Free tier (1000 calls/day) |
| **NHC (hurricanes)** | RSS/REST | Tropical cyclone advisories, track forecasts | Per advisory (~6hr) | Free |
| **SPC** | REST/Scraping | Severe weather outlooks, tornado probabilities | Daily | Free |

**Key features:** Ensemble model spread (confidence proxy), forecast vs. climatological normal, trend direction (warming/cooling over forecast window), probability of threshold exceedance (e.g., P(temp > 100°F)), historical analog matching (same date/location base rates).

#### 3.1.6 Crypto & Web3

| Source | API/Method | Data | Freshness | Cost |
|--------|-----------|------|-----------|------|
| **CoinGecko API** | REST | Price, volume, market cap for 10K+ coins | 1-min granularity | Free (rate-limited) |
| **Glassnode** | REST API | On-chain metrics (MVRV, SOPR, exchange flows) | Daily/hourly | $30–800/mo |
| **Dune Analytics** | REST API | Custom SQL on blockchain data | Query-dependent | Free tier + paid |
| **Binance/Coinbase APIs** | REST + WebSocket | Order books, trades, funding rates | Real-time | Free |
| **LunarCrush** | REST API | Social sentiment, social volume | Hourly | Free tier |
| **DeFi Llama** | REST API | TVL by protocol, chain, category | ~10 min | Free |
| **Coinglass** | Scraping/API | Funding rates, open interest, liquidation data | Real-time | Free tier |

**Key features:** Funding rate z-score, exchange net flow (7d), social sentiment momentum, TVL delta by chain, BTC dominance trend, NVT ratio, MVRV deviation from mean.

### 3.2 Data Pipeline Architecture

**Design principle:** Monolith-first. No microservices. One Python process with async concurrency handles all ingestion. Graduate to workers only when a single process can't keep up.

```
┌─────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER                         │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ API      │  │WebSocket │  │ Scraper  │  │  RSS/     │  │
│  │ Pollers  │  │ Clients  │  │ Workers  │  │  Manual   │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       └──────────────┴─────────────┴──────────────┘        │
│                          │                                  │
│                    ┌─────▼──────┐                           │
│                    │ Normalizer │  Schema validation,       │
│                    │ & Validator│  dedup, timezone → UTC    │
│                    └─────┬──────┘                           │
└──────────────────────────┼──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL │  Normalized, structured
                    │ (TimescaleDB│  time-series data
                    │  extension) │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │Feature Store│  Computed features,
                    │  (in-DB +   │  versioned, queryable
                    │   Redis)    │
                    └─────────────┘
```

**Ingestion layer implementation:**

- **API pollers:** `asyncio` + `httpx` with configurable per-source polling intervals. Each source is a `DataSource` class with `fetch()`, `normalize()`, and `validate()` methods.
- **WebSocket clients:** `websockets` library. Auto-reconnect with exponential backoff. Used for Kalshi market data, Polymarket CLOB, and crypto exchange feeds.
- **Scrapers:** `httpx` + `selectolax` (faster than BeautifulSoup). Respect `robots.txt`. Implement politeness delays (min 2s between requests to same domain). Headless browser (`playwright`) only for JS-rendered pages that absolutely require it.
- **RSS/Manual:** RSS via `feedparser`. Manual entry through a simple CLI command or dashboard form for niche events.

**Normalization rules:**

- All timestamps → UTC ISO 8601.
- All prices → USD decimal (Decimal type, not float).
- All probabilities → [0.0, 1.0] range.
- Deduplication: hash(source + event_id + timestamp) as unique key. Upsert on conflict.
- Source reliability score: 1.0 (official API) → 0.7 (scraped) → 0.5 (social media) → 0.3 (manual).

**Storage:**

| Store | Tech | Purpose |
|-------|------|---------|
| Primary DB | **PostgreSQL 16 + TimescaleDB** | All structured data — markets, prices, features, trades, P&L. TimescaleDB hypertables for time-series (price ticks, odds snapshots). Single DB, not multiple stores. |
| Cache | **Redis 7** | Hot feature cache, current positions, real-time state. TTLs per key type. |
| Raw data lake | **Local filesystem → S3** | Raw API responses archived as gzipped JSON. Cheap insurance for reprocessing. Start local, move to S3 when storage exceeds 100GB. |

**Why not a separate time-series DB (InfluxDB, QuestDB)?** TimescaleDB gives you time-series performance with full PostgreSQL compatibility. One database to manage, one query language, one backup strategy. As a solo operator, operational simplicity is worth more than marginal time-series performance gains.

**Freshness requirements:**

| Data type | Max acceptable staleness |
|-----------|------------------------|
| Exchange order books (Kalshi, Polymarket) | 5 seconds |
| Odds feeds (The Odds API) | 30 seconds |
| Sports scores (live games) | 30 seconds |
| Polling data | 1 hour |
| Economic data releases | 1 minute (on release day), 1 hour otherwise |
| Weather forecasts | 15 minutes |
| Crypto prices | 1 minute |
| Social sentiment | 5 minutes |
| Static reference data (schedules, rosters) | 1 hour |

**Data quality:**

- Validation rules per source (e.g., probability must be in [0, 1], price must be positive).
- Anomaly detection: flag data points > 3σ from rolling 24hr mean. Don't auto-reject — flag for review.
- Source health tracking: if a source fails 3 consecutive fetches, alert. If 10 consecutive, disable and alert urgently.
- Missing data: forward-fill for up to 2 intervals, then mark as stale and exclude from feature computation.

### 3.3 Feature Store

**Implementation:** In-database feature store using PostgreSQL materialized views + Redis cache. No Feast or Tecton — those are overengineered for a solo operator.

**Feature computation pipeline:**

```python
class FeatureExtractor(Protocol):
    name: str
    version: str  # Bump on logic change
    refresh_interval: timedelta
    dependencies: list[str]  # Other features this depends on

    def compute(self, raw_data: pd.DataFrame) -> pd.Series: ...
```

**Feature types:**

1. **Batch features** — Recomputed on schedule (hourly/daily). Stored in PostgreSQL tables. Examples: Elo ratings, polling averages, season statistics.
2. **Near-real-time features** — Recomputed on data arrival. Stored in Redis with TTL. Examples: live odds movement, injury report flags, score state.
3. **On-demand features** — Computed at inference time. Not stored. Examples: time-to-resolution, current market spread.

**Feature versioning:** Features are identified by `{name}_v{version}`. When a feature's computation logic changes, bump the version. Old versions are retained for backtesting reproducibility.

**Standard feature templates per vertical:**

| Vertical | Template Features |
|----------|------------------|
| Sports | `elo_rating`, `rolling_win_pct_N`, `ats_record_N`, `rest_days`, `home_away_split`, `sharp_line_movement`, `weather_impact_score` |
| Politics | `polling_avg_weighted`, `polling_trend_7d`, `fundamentals_index`, `fundraising_velocity`, `prediction_market_consensus`, `media_sentiment_7d` |
| Economics | `consensus_forecast`, `nowcast_deviation`, `surprise_factor_history`, `trend_3m`, `fedwatch_implied_prob` |
| Weather | `ensemble_mean`, `ensemble_spread`, `climatological_normal`, `forecast_trend`, `analog_match_score` |
| Crypto | `funding_rate_zscore`, `exchange_netflow_7d`, `social_sentiment_delta`, `nvt_ratio`, `btc_dominance` |
| Entertainment | `expert_consensus_prob`, `precursor_award_signal`, `attention_momentum`, `historical_category_winrate` |

---

## 4. Modeling & Signal Generation

### 4.1 Model Architecture by Vertical

#### 4.1.1 Sports

**Baseline model: Custom Elo + Logistic Regression**

Start with Elo ratings (calibrated per sport — NFL K-factor ~20, NBA ~15) as the primary power rating. Feed Elo difference, home advantage, rest days, and recent form into logistic regression. This alone beats the average Kalshi sports bettor.

**Advanced models:**

- **Gradient Boosted Trees (LightGBM):** Full feature vector (50+ features per game). Fast training, handles missing data natively. Train on 3+ seasons of historical data. This is the workhorse.
- **Player-prop specific model:** Per-player regression models for props (points, rebounds, assists). Features: recent game log, opponent defensive rating, minutes projection, home/away.
- **In-game model:** For live markets. Uses current score, time remaining, and pre-game model probability to update win probability in real-time. Logistic regression on score differential × time remaining is sufficient and fast.

**LLM-augmented signals:**

- Parse injury report language: "questionable (knee)" vs "questionable (rest)" have very different implications. Use Claude API to classify injury severity (1–5 scale) from report text.
- Beat reporter tweet interpretation: "X is going through warmups" → probability of playing.

**Model output:** `P(home_win)`, 95% CI, recommended bet size (Kelly), expected value per contract.

#### 4.1.2 Politics

**Baseline model: Weighted Polling Average**

Weight polls by: recency (exponential decay, half-life 14 days), pollster quality rating (FiveThirtyEight grades), sample size, and methodology (live caller > online panel > IVR). This is the starting point that beats most Kalshi political traders.

**Advanced models:**

- **Fundamentals + Polls Ensemble:** Combine polling average with structural factors (incumbency, GDP growth, presidential approval, generic ballot). Use Bayesian regression with informative priors from historical elections.
- **Time-Series Forecast:** Model polling average trajectory over time. Use Gaussian process regression to project where polls will be on election day given current trends.
- **LLM-augmented reasoning:** Feed debate transcripts, major news events, and expert commentary to Claude. Prompt: "Given this debate transcript, estimate the probability and direction of a polling shift of >2 points within 7 days. Output as JSON: {shift_probability, direction, magnitude_estimate}."

**Model output:** `P(candidate_wins)`, `P(party_controls_chamber)`, confidence interval, edge vs. market price.

#### 4.1.3 Economics & Macro

**Baseline model: Consensus-Based**

For data release markets (CPI, NFP, etc.), the baseline is: what does the Bloomberg/Trading Economics consensus say? Markets price in consensus. Edge comes from knowing when the consensus is wrong.

**Advanced models:**

- **Nowcast deviation model:** When Atlanta Fed GDPNow disagrees with consensus, that's a signal. Historical hit rate: GDPNow within 0.5pp of actual ~65% of the time.
- **Leading indicator model:** Use leading indicators (initial claims → NFP, ISM new orders → GDP) to predict release surprise direction.
- **Calendar-aware model:** Some releases have seasonal patterns in surprise direction (e.g., January CPI tends to surprise high due to annual adjustment effects).

#### 4.1.4 Weather

**Baseline model: Ensemble Model Consensus**

NWS and ECMWF ensemble models are already highly calibrated for 1–7 day forecasts. The baseline is: convert ensemble probability (e.g., 30 of 50 ensemble members predict >100°F) to calibrated market probability.

**Advanced model:**

- **Ensemble model blending:** Weight ECMWF higher (better skill scores) for days 3–10. Weight NWS/NAM higher for days 0–2. Blend with inverse-variance weighting.
- **Climatological anchor:** For longer-range markets (monthly records), anchor to base rates and update with forecast information. Markets tend to underweight base rates.

#### 4.1.5 Entertainment

**Baseline model: Expert Consensus**

Gold Derby aggregates expert predictions with calibrated odds. Convert these to probabilities. Markets often deviate from expert consensus during periods of "narrative momentum" — that deviation is the edge.

**Advanced model:**

- **Precursor correlation model:** For Oscars — model P(Best Picture win | SAG Ensemble win, PGA win, DGA win). Historical correlations are strong and stable.
- **Attention momentum model:** Track Wikipedia pageview velocity + Google Trends for nominees. Rapid attention increases correlate with "surprise" wins in categories where name recognition matters.

#### 4.1.6 Crypto

**Baseline model: Funding Rate Mean Reversion**

When perpetual funding rates exceed ±0.1% (8hr), there's a statistically significant tendency for price to mean-revert. Use this as a directional signal for short-term crypto price markets.

**Advanced models:**

- **On-chain flow model:** Exchange net inflow (7d rolling) > 2σ historically precedes selling pressure. Combine with open interest and liquidation levels.
- **Social sentiment momentum:** LunarCrush social volume spike + positive sentiment shift → short-term price momentum signal.

### 4.2 Edge Quantification

**Definition:**

```
Edge = P_model - P_market

Where:
  P_model  = Model-estimated probability of outcome (calibrated)
  P_market = Market-implied probability = market_price / $1.00
```

**Minimum edge to trade (by platform):**

| Platform | Fees | Min Edge to Trade | Rationale |
|----------|------|-------------------|-----------|
| Kalshi | ~7¢/contract | 10¢ (10 percentage points) | 7¢ fee + 3¢ buffer for model uncertainty |
| Polymarket | ~2% taker | 5¢ | Lower fees allow tighter thresholds |
| PredictIt | 10% profit + 5% withdrawal | 18¢ | Fee drag is enormous |

**Confidence-weighted edge:**

```python
def weighted_edge(p_model, p_market, model_confidence):
    """
    model_confidence: float [0, 1] based on:
      - training data volume (more data → higher)
      - prediction interval width (narrower → higher)
      - model agreement (ensemble disagreement → lower)
    """
    raw_edge = p_model - p_market
    return raw_edge * model_confidence
```

Trade only when `weighted_edge > min_edge_threshold`.

**Edge decay modeling:**

- Sports: Edge half-life ~2–6 hours (injury news) to ~30 minutes (in-game).
- Politics: Edge half-life ~1–7 days (polls take days to reflect events).
- Economics: Edge half-life ~minutes (on release day) to ~days (structural macro).
- Weather: Edge half-life ~6–12 hours (new model runs every 6–12 hours).
- Entertainment: Edge half-life ~1–3 days during awards season.

### 4.3 Backtesting Framework

**Design: Event-driven backtester.**

```python
class Backtester:
    def __init__(self, strategy: Strategy, data: HistoricalData, config: BacktestConfig):
        self.strategy = strategy
        self.data = data
        self.config = config

    def run(self) -> BacktestResult:
        portfolio = Portfolio(initial_capital=config.initial_capital)
        for event in self.data.events_chronological():
            signals = self.strategy.generate_signals(event, portfolio)
            for signal in signals:
                if self.config.execution_model.can_fill(signal, event):
                    portfolio.execute(signal, event)
            portfolio.mark_to_market(event.timestamp)
        return BacktestResult(portfolio)
```

**Metrics:**

| Metric | Target | Description |
|--------|--------|-------------|
| Brier Score | < 0.20 | Mean squared error of probability predictions vs. outcomes |
| Log Loss | < 0.60 | Penalizes confident wrong predictions harshly |
| Calibration Error | < 0.03 | Mean absolute deviation from perfect calibration curve |
| ROI | > 10%/month | Net return on capital deployed |
| Sharpe Equivalent | > 1.5 | Return / volatility, annualized |
| Max Drawdown | < 20% | Worst peak-to-trough P&L decline |
| Win Rate | > 55% | Percentage of settled trades that profit |
| Average Edge Captured | > 5¢ | Mean edge per executed trade |

**Validation approach:**

- **Walk-forward:** Train on expanding window, test on next month, roll forward. Minimum 12 months of walk-forward for any model to go live.
- **Purged K-Fold:** For cross-validation during model development. Purge 7-day buffer between train and test folds to prevent leakage from correlated events.
- **Paper trading:** Mandatory 30-day paper trading period for any new model or significant model change before live capital deployment.

**Backtest-to-live gap analysis:**

Track the ratio of live performance to backtest performance per model. If live/backtest < 0.5 for any model over 60 days, investigate for overfitting and consider deactivation.

### 4.4 Model Lifecycle Management

**Training pipeline:**

- **Scheduled retraining:** Sports models retrain daily (new game results). Politics models retrain on new poll release. Econ models retrain on data release.
- **Trigger-based retraining:** If feature drift (PSI > 0.2) or prediction drift (KL divergence > 0.1 from recent actual outcomes) is detected, force retrain.
- **Implementation:** `dagster` for pipeline orchestration. Jobs defined in Python, scheduled via dagster's built-in scheduler. Dagster over Airflow because: Python-native, better local development experience, asset-based mental model fits feature computation.

**Model registry:**

Use **MLflow** (self-hosted, SQLite backend for solo operation). Track:
- Model artifacts (serialized model files)
- Training metrics (loss, calibration, feature importances)
- Training data hash (for reproducibility)
- Model version and lineage

**Champion/challenger:**

- Each market category has one "champion" model (production) and optionally one "challenger" (shadow mode — generates signals, doesn't trade).
- Challenger promotes to champion if: (a) paper trading Brier score < champion for 30 consecutive days, AND (b) ROI improvement > 2 percentage points.

**Monitoring alerts:**

- Brier score 30-day rolling average exceeds 0.25: warning.
- Calibration error exceeds 0.05: warning.
- Model hasn't been retrained in > 2× scheduled interval: warning.
- Any model with 30-day ROI < -10%: auto-deactivate, alert.

---

## 5. Execution Engine

### 5.1 Order Management System (OMS)

**Pre-trade checks (all must pass):**

1. Sufficient balance on target platform (including fee reservation).
2. Position would not exceed per-market limit.
3. Position would not exceed per-category exposure limit.
4. Position would not exceed per-platform exposure limit.
5. Drawdown circuit breaker is not active.
6. Model that generated signal is healthy (no active warnings).
7. Market is open for trading (not in settlement/halted state).

**Order state machine:**

```
CREATED → SUBMITTED → [PENDING_ON_EXCHANGE]
  PENDING_ON_EXCHANGE → FILLED (full)
  PENDING_ON_EXCHANGE → PARTIALLY_FILLED → FILLED (remaining) or CANCELLED (unfilled portion)
  PENDING_ON_EXCHANGE → REJECTED
  PENDING_ON_EXCHANGE → CANCELLED (by us or exchange)
  SUBMITTED → FAILED (network/API error)
```

**Order record schema:**

```json
{
  "order_id": "sigil_ord_20260329_001",
  "external_order_id": "kalshi_abc123",
  "platform": "kalshi",
  "market_id": "KXNFL-26SEP-NYG",
  "side": "buy",
  "outcome": "yes",
  "type": "limit",
  "price": 0.42,
  "quantity": 50,
  "filled_quantity": 50,
  "avg_fill_price": 0.42,
  "fees": 3.50,
  "status": "filled",
  "signal_id": "sig_20260329_nfl_001",
  "model_id": "nfl_lgbm_v3",
  "model_probability": 0.58,
  "edge_at_entry": 0.16,
  "created_at": "2026-09-29T16:45:00Z",
  "filled_at": "2026-09-29T16:45:02Z"
}
```

**Reconciliation:**

Every 5 minutes (and on each order state change), reconcile local order/position state with exchange state. Flag discrepancies immediately. On discrepancy: trust exchange state, update local, alert.

### 5.2 Execution Strategies

| Strategy | When to Use | Implementation |
|----------|-------------|----------------|
| **Passive (limit)** | Edge is large, time horizon > 1 hour, thick book | Post limit order at model fair value minus buffer. Capture maker rebate on Polymarket. Rest order for up to 1 hour, cancel if unfilled. |
| **Aggressive (market/IOC)** | Breaking news edge, rapid decay expected | Hit best available price immediately. Accept up to 2¢ slippage. Used for injury reports, data releases. |
| **Scaled** | Order size > 10% of visible book depth | Split into 3–5 chunks, spaced 30 seconds apart. Monitor fill rate and adjust pricing. Prevents moving the market against yourself. |
| **Conditional** | Position management, hedging | If market moves past threshold after entry, execute hedge or exit. Implemented as persistent rules in the decision engine, not resting exchange orders. |

### 5.3 Position & Risk Management

**Position limits:**

| Scope | Limit | Rationale |
|-------|-------|-----------|
| Per-market | 5% of bankroll | No single event should matter too much |
| Per-category (L1) | 25% of bankroll | Diversify across verticals |
| Per-platform | 50% of bankroll | Platform risk — don't have all capital on one exchange |
| Correlated events | 15% of bankroll | E.g., multiple NFL games on same Sunday — weather or injury news affects all |

**Kelly Criterion sizing:**

```python
def kelly_size(p_model: float, p_market: float, bankroll: float, fraction: float = 0.25) -> float:
    """
    Fractional Kelly (default 25% Kelly — full Kelly is too aggressive).
    """
    odds = (1.0 / p_market) - 1.0  # decimal odds minus 1
    edge = p_model - p_market
    kelly_pct = (edge * (odds + 1) - (1 - p_model)) / odds
    kelly_pct = max(0, kelly_pct)  # Never negative (never bet against our signal)
    return bankroll * kelly_pct * fraction
```

**Why 25% Kelly?** Full Kelly maximizes long-run growth but has ~50% chance of 50%+ drawdown. Quarter Kelly reduces growth rate by ~44% but reduces max expected drawdown to ~12%. For a solo operator, survival (not blowing up) matters more than growth optimization.

**Drawdown circuit breakers:**

| Trigger | Action |
|---------|--------|
| 10% drawdown from peak (rolling 7 days) | Reduce position sizes to 50% of normal |
| 15% drawdown from peak (rolling 14 days) | Halt all new trades. Existing positions run to settlement. |
| 20% drawdown from peak (rolling 30 days) | Full system halt. Manual review required before resuming. |

**Correlation tracking:**

Maintain a correlation matrix of active positions. For events that are obviously correlated (e.g., same-game props), apply a correlation penalty: combined position size for correlated events must not exceed the single-event position limit × 1.5.

### 5.4 Settlement & P&L Tracking

**Settlement detection:**

- Poll exchange APIs every 5 minutes for settlement status.
- On settlement, record: outcome, settlement price, P&L per contract, total P&L.
- Update portfolio state: close position, realize P&L, free capital.

**P&L attribution dimensions:**

```sql
-- P&L queryable by any combination of:
SELECT
    vertical,           -- sports, politics, etc.
    model_id,           -- which model generated the signal
    platform,           -- kalshi, polymarket, etc.
    date_trunc('month', settled_at) as month,
    SUM(realized_pnl) as total_pnl,
    SUM(fees_paid) as total_fees,
    SUM(realized_pnl - fees_paid) as net_pnl,
    COUNT(*) as trade_count,
    AVG(edge_at_entry) as avg_edge
FROM trades
WHERE status = 'settled'
GROUP BY 1, 2, 3, 4;
```

**Tax tracking:**

Record every settled trade with: entry date, exit/settlement date, cost basis, proceeds, net gain/loss, platform. Export to CSV compatible with TurboTax or accountant import. Prediction market gains are taxed as ordinary income (short-term capital gains) in the US — not as gambling losses (Kalshi is a CFTC-regulated exchange, so Section 1256 treatment may apply — consult a tax professional).

---

## 6. System Architecture

### 6.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         SIGIL SYSTEM                            │
│                                                                 │
│  ┌─────────────┐     ┌──────────────┐     ┌─────────────────┐  │
│  │   Data       │     │  Feature     │     │  Model          │  │
│  │   Ingestion  │────▶│  Computation │────▶│  Inference      │  │
│  │   Service    │     │  (Dagster)   │     │  Service        │  │
│  └──────┬──────┘     └──────┬───────┘     └───────┬─────────┘  │
│         │                   │                     │             │
│         ▼                   ▼                     ▼             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           PostgreSQL + TimescaleDB                       │   │
│  │  (Markets, Prices, Features, Trades, P&L, Models)       │   │
│  └──────────────────────────────────────────────────────────┘   │
│         │                                         │             │
│         ▼                                         ▼             │
│  ┌──────────────┐                        ┌─────────────────┐   │
│  │    Redis     │                        │  Decision       │   │
│  │  (Hot Cache, │                        │  Engine         │   │
│  │   State)     │                        │  (Edge → Trade) │   │
│  └──────────────┘                        └───────┬─────────┘   │
│                                                  │              │
│                                                  ▼              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Execution Services                          │   │
│  │  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │   │
│  │  │ Kalshi   │  │  Polymarket  │  │  Future Exchange  │  │   │
│  │  │ Adapter  │  │  Adapter     │  │  Adapter          │  │   │
│  │  └──────────┘  └──────────────┘  └───────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Dashboard   │  │  Monitoring  │  │  CLI Admin Tool     │  │
│  │  (Next.js)   │  │  & Alerting  │  │  (Click/Typer)      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key design choices:**

1. **Monolith with clean boundaries, not microservices.** All Python services run as modules within a single process (or 2–3 processes max: ingestion, inference+decision, dashboard). They communicate via function calls and shared database, not HTTP/gRPC. This eliminates network overhead, simplifies deployment, and reduces operational burden.

2. **One database.** PostgreSQL handles everything. TimescaleDB extension for time-series. JSONB columns for semi-structured data. No MongoDB, no InfluxDB, no Elasticsearch. One backup strategy, one connection pool, one set of migrations.

3. **Process separation only where necessary.** The dashboard (Next.js) is a separate process because it's a different runtime. The ingestion service may run as a separate process if its event loop conflicts with model inference CPU usage. Everything else: one Python process.

### 6.2 Tech Stack

| Component | Choice | Justification |
|-----------|--------|---------------|
| **Primary language** | **Python 3.12** | ML ecosystem (scikit-learn, LightGBM, PyTorch), async support, rapid development. Performance-critical paths are in library code (numpy, pandas), not application code. |
| **Database** | **PostgreSQL 16 + TimescaleDB 2.x** | One DB for everything. TimescaleDB compression reduces time-series storage 10×. Full SQL, JSONB, CTEs, window functions. Mature, reliable, free. |
| **Cache/State** | **Redis 7** | Sub-ms reads for hot data. Used for: current positions, latest prices, feature cache, rate limit tracking. |
| **Pipeline orchestration** | **Dagster** | Python-native, asset-based, excellent local dev experience. Better than Airflow for solo operator (no separate scheduler process needed in dev). |
| **ML framework** | **LightGBM** (primary), **scikit-learn** (utilities), **PyTorch** (if needed for deep learning experiments) | LightGBM: fast training, handles missing data, categorical features native. scikit-learn for preprocessing and baseline models. |
| **LLM integration** | **Claude API** (Anthropic Python SDK) | Qualitative signal extraction. Better reasoning than GPT-4 for nuanced text analysis (injury reports, debate transcripts). |
| **Model tracking** | **MLflow** (SQLite backend) | Lightweight, self-hosted. No MLflow server needed — just the tracking library writing to local SQLite. |
| **HTTP client** | **httpx** | Async support, HTTP/2, connection pooling. Drop-in replacement for requests with async capability. |
| **Web scraping** | **httpx + selectolax** | selectolax is 10× faster than BeautifulSoup for HTML parsing. Playwright only for JS-rendered pages. |
| **Frontend** | **Next.js 14 + TypeScript** | React ecosystem, SSR for initial load, WebSocket support for real-time updates. shadcn/ui for component library. |
| **Charts** | **Recharts** (dashboard) + **Plotly** (backtesting analysis) | Recharts: lightweight, React-native. Plotly: interactive, great for exploratory analysis in notebooks. |
| **Deployment** | **Docker Compose** on a single VPS (Hetzner or DigitalOcean) | No Kubernetes. Docker Compose manages: Python app, PostgreSQL, Redis, Next.js dashboard. One `docker compose up` and everything runs. |
| **CI/CD** | **GitHub Actions** | Run tests, type checks, linting on push. Auto-deploy to VPS on merge to main via SSH. |
| **Monitoring** | **Prometheus + Grafana** (via Docker) | Prometheus scrapes app metrics (custom `/metrics` endpoint). Grafana dashboards for system health. |
| **Alerting** | **Telegram Bot API** | Instant mobile alerts. Simpler than PagerDuty/Opsgenie for a solo operator. Send critical alerts (drawdown, system failure, high-edge opportunity) to a private Telegram channel. |

### 6.3 Latency Requirements

| Path | SLA | Critical? |
|------|-----|-----------|
| Data ingestion → feature available | < 10 seconds (batch), < 2 seconds (real-time) | Yes for real-time sources |
| Feature available → model inference | < 1 second | Yes |
| Model inference → trade decision | < 500 ms | Yes |
| Trade decision → order submitted to exchange | < 500 ms | Yes |
| **End-to-end: data event → order on exchange** | **< 15 seconds** | **Target for time-sensitive events** |
| Dashboard data refresh | < 5 seconds | No — UX, not execution |
| Backtest full vertical (1 year) | < 5 minutes | No — batch job |

**Latency reality check:** Prediction markets are not HFT. A 15-second end-to-end pipeline is more than fast enough. The edge comes from having better *information* and *models*, not faster *execution*. Don't over-optimize latency at the expense of code simplicity.

---

## 7. Dashboard & User Interface

### 7.1 Core Views

#### 7.1.1 Command Center (Home)

The primary view. Displays:

- **Active P&L:** Real-time unrealized + realized P&L for the day, week, month.
- **Position summary:** Count of open positions by vertical, total capital deployed, capital available.
- **System health bar:** Green/yellow/red for each component (data ingestion, model inference, execution, DB, exchange connections).
- **Signal queue:** Top 5 pending signals ranked by weighted edge. One-click approve or dismiss for semi-auto mode.
- **Recent activity feed:** Last 20 events (orders placed, positions settled, alerts triggered).

#### 7.1.2 Market Explorer

- Browse all tracked markets by category (L1/L2/L3 taxonomy).
- Filter by: edge (min/max), liquidity (min volume), time to expiry, platform.
- Sort by: edge magnitude, confidence, liquidity, expiry date.
- Each market card shows: title, current price, model probability, edge, volume, time to expiry.
- Click to expand: full model details, feature values, order book snapshot, price history chart.

#### 7.1.3 Signal Feed

- Chronological feed of all model-generated signals.
- Each signal card: market title, model source, edge, confidence, recommended position size, action taken (traded/skipped/pending), timestamp.
- Filter by: vertical, model, edge threshold, action status.
- Bulk approve/dismiss for semi-auto mode.

#### 7.1.4 Position Manager

- All open positions with: entry price, current price, unrealized P&L, model current probability, edge remaining, time to expiry.
- Close/hedge actions available per position.
- Exposure breakdown by vertical, platform, and correlation group.
- Risk metrics: current drawdown, Kelly utilization, largest position.

#### 7.1.5 Model Performance

- Per-model dashboards: Brier score (rolling 30/90/365 days), calibration plot, ROI curve, win rate.
- Per-vertical aggregate performance.
- Champion vs. challenger comparison.
- Feature importance plots (top 20 features per model).

#### 7.1.6 Data Health Monitor

- Table of all data sources: name, last fetch time, freshness status (green/yellow/red), error count (24hr), reliability score.
- Click to see fetch history, error logs, latency chart.
- Bulk actions: retry failed, disable source, reset error count.

#### 7.1.7 Backtesting Lab

- Select model, date range, parameters.
- Run backtest (async — shows progress bar).
- Results: P&L curve, metrics table, trade log, calibration plot, drawdown chart.
- Compare two backtest runs side-by-side.

#### 7.1.8 Configuration Panel

- Model weights and activation toggles per vertical.
- Risk parameters: position limits, Kelly fraction, drawdown thresholds.
- Execution preferences: passive/aggressive mode per vertical, minimum edge threshold.
- Data source configuration: enable/disable, polling intervals.
- Alert thresholds.

### 7.2 Alerts & Notifications (via Telegram)

| Alert | Severity | Trigger |
|-------|----------|---------|
| High-edge opportunity | Info | Weighted edge > 2× minimum threshold |
| Trade executed | Info | Order filled |
| Position settled | Info | Market resolved, P&L realized |
| Drawdown warning | Warning | 10% drawdown trigger hit |
| Drawdown critical | Critical | 15% drawdown trigger hit |
| Data source failure | Warning | 3 consecutive fetch failures |
| Data source down | Critical | 10 consecutive failures or > 1 hour stale |
| Model degradation | Warning | Brier score 30d > 0.25 |
| Model auto-deactivated | Critical | 30-day ROI < -10% |
| Platform connection lost | Critical | Cannot reach exchange API |
| Arb detected | Info | Cross-platform arbitrage > 2¢ net |
| System error | Critical | Unhandled exception, DB down, OOM |

---

## 8. Modularity & Extensibility

### 8.1 Vertical Module Interface

Every betting vertical implements this interface:

```python
@dataclass
class VerticalModule:
    name: str  # e.g., "sports_nfl"
    taxonomy_prefix: tuple[str, str]  # e.g., ("sports", "nfl")

    # Data layer
    data_sources: list[DataSource]
    feature_extractors: list[FeatureExtractor]

    # Model layer
    models: list[Model]
    ensemble_strategy: EnsembleStrategy  # How to combine multiple models

    # Market matching
    market_mapper: MarketMapper  # Maps exchange market IDs → internal taxonomy

    # Execution rules
    min_edge_threshold: float  # Minimum edge to trade (after fees)
    max_position_pct: float  # Max bankroll % per market in this vertical
    max_category_exposure_pct: float  # Max bankroll % total in this vertical
    kelly_fraction: float  # Kelly fraction for this vertical (may differ by confidence level)
    execution_mode: Literal["passive", "aggressive", "scaled"]

    # Backtest
    backtest_config: BacktestConfig  # Historical data range, walk-forward params
```

**Adding a new vertical requires:**

1. Define `DataSource` implementations for each data feed.
2. Define `FeatureExtractor` implementations.
3. Train at least one model, register in MLflow.
4. Implement `MarketMapper` to match exchange markets to the taxonomy.
5. Configure execution rules.
6. Run backtests meeting minimum criteria (Brier < 0.22, ROI > 5% in walk-forward).
7. Paper trade for 30 days.

**No core infrastructure changes required.** The vertical registers itself on startup, and the system discovers its data sources, models, and execution rules automatically.

### 8.2 Plugin Architecture

For experimental or third-party models:

- Models implement the `Model` protocol: `train(data) → None`, `predict(features) → Prediction`, `evaluate(data) → Metrics`.
- Models run in a subprocess with resource limits (max 4GB RAM, 60-second inference timeout).
- Model I/O is serialized JSON — no shared memory or direct DB access from plugins.
- Plugin models can only be deployed in "shadow" mode (no live trading) until manually promoted.

### 8.3 New Exchange Adapter

Implementing the `ExchangeAdapter` protocol (defined in §2.1.5) requires:

1. **Market data methods:** `get_markets`, `get_orderbook`, `get_trades` — can return cached data with stated freshness.
2. **Execution methods:** `place_order`, `cancel_order` — must handle exchange-specific auth, signing, rate limiting.
3. **Account methods:** `get_positions`, `get_balance` — must reconcile with local state.
4. **Streaming methods:** `stream_orderbook`, `stream_trades` — optional but recommended for real-time data.

**Testing before going live:**

- Unit tests for all methods with mocked API responses.
- Integration tests against exchange sandbox/testnet (if available).
- 7 days of data collection without trading (verify market data accuracy).
- 7 days of paper trading (verify order submission/cancellation/fill logic).
- Manual review of all test results before live activation.

---

## 9. Competitive Edge & Moat Analysis

### 9.1 Sources of Edge

| Edge Source | Durability | Description |
|-------------|-----------|-------------|
| **Data breadth** | **High** | Aggregating 30+ sources per vertical vs. a retail trader checking one or two. This is cumulative — each new source adds signal that's hard to replicate manually. |
| **Model sophistication** | **Medium** | ML/statistical models vs. gut feel. Medium durability because models can be replicated by others — but the ensemble and calibration are hard to copy without the same data. |
| **Speed** | **Medium** | Reacting to information in seconds vs. minutes/hours. Medium because truly latency-sensitive edges are rare in prediction markets, and faster players will eventually arrive. |
| **Systematic discipline** | **High** | No emotional trading, no tilt, no FOMO, no anchoring. The system trades its edge and nothing else. This is the most underrated advantage — most prediction market participants are entertainment bettors who trade for fun. |
| **Cross-vertical pattern recognition** | **Low-Medium** | Insights from one vertical informing another (e.g., weather impacting sports). Novel but unproven; may not materialize into significant edge. |
| **Market microstructure awareness** | **High** | Understanding thin books, wide spreads, settlement risk, fee drag. Building fee-aware execution that most retail traders ignore. |

### 9.2 Edge Erosion Timeline

- **Years 1–2:** Window is wide open. Few systematic players in prediction markets. Data aggregation alone provides significant edge.
- **Years 2–4:** Early competition arrives. Simple models get arbitraged away. Advantage shifts to: unique data sources, better feature engineering, superior calibration.
- **Years 4+:** Prediction markets mature. Edge narrows to: proprietary data, execution optimization, and capital efficiency. Margins compress toward traditional sports betting (~2–5% ROI).

**Defensive strategy:** Continuously expand data source breadth and develop proprietary features that are hard to replicate. Invest in calibration quality — being the most calibrated forecaster is a durable advantage because it requires discipline and infrastructure, not just a better algorithm.

---

## 10. Development Roadmap

### Phase 1: Foundation (Weeks 1–6)

**Goal:** First live trade on Kalshi with model-generated signal.

| Week | Deliverable |
|------|-------------|
| 1–2 | Project scaffolding: repo structure, Docker Compose (Postgres + Redis + app), DB schema, exchange adapter interface. Kalshi adapter with auth, market listing, order placement. |
| 3 | Data ingestion for Sports (NFL/NBA): ESPN API, The Odds API. Basic feature extractors: Elo, rolling win%, home/away. |
| 4 | Data ingestion for Politics: FiveThirtyEight, RealClearPolitics polling data, FRED. Feature extractors: weighted polling average, fundamentals index. |
| 5 | Baseline models: Elo + LR for sports, weighted poll average for politics. Edge calculation. Paper trading mode. CLI for viewing signals and approving trades. |
| 6 | Paper trading validation. Fix bugs. First live trade (small size — $10–50 per market). Basic P&L tracking. Telegram alerts. |

### Phase 2: Scale (Weeks 7–14)

**Goal:** Automated trading with risk management. Multiple verticals live.

| Week | Deliverable |
|------|-------------|
| 7–8 | LightGBM models for sports. Backtesting framework. Walk-forward validation. Expand sports data sources (injury reports, weather). |
| 9–10 | Polymarket adapter. Cross-platform market matching. Add Economics/Macro vertical (FRED, GDPNow, FedWatch). Weather vertical (NWS, Open-Meteo). |
| 11–12 | Automated execution engine (no more manual approval for signals above confidence threshold). Kelly sizing. Drawdown circuit breakers. Position limit enforcement. |
| 13–14 | Next.js dashboard: Command Center, Position Manager, Signal Feed. Real-time WebSocket updates. Model Performance view. |

### Phase 3: Optimize (Weeks 15–22)

**Goal:** LLM integration, advanced models, full analytics.

| Week | Deliverable |
|------|-------------|
| 15–16 | Claude API integration for qualitative signal extraction: injury report parsing, debate transcript analysis, press conference sentiment. |
| 17–18 | Entertainment vertical (Gold Derby, awards season). Crypto vertical (CoinGecko, Glassnode, DeFi Llama). Advanced ensemble strategies. |
| 19–20 | Correlation-aware risk management. P&L attribution dashboard. Model A/B testing framework. Champion/challenger deployment. |
| 21–22 | Feature drift detection and auto-retraining triggers. Backtest Lab in dashboard. Performance optimization (query tuning, caching). |

### Phase 4: Dominate (Weeks 23+)

**Goal:** Full modularity, edge everywhere, operational excellence.

- New verticals addable in < 1 week (plug-and-play module system proven).
- Cross-platform arbitrage execution.
- Proprietary data sources (build scraping infrastructure for niche data).
- Multi-strategy portfolio optimization (allocate bankroll across verticals based on recent edge quality).
- Advanced execution: time-weighted scaling, adaptive passive/aggressive switching.
- Consider hiring: one data engineer or quant researcher to expand coverage.

---

## 11. Risk & Compliance

### 11.1 Regulatory Landscape

| Platform | Regulatory Status | Key Considerations |
|----------|------------------|--------------------|
| Kalshi | CFTC-regulated DCM | Legal for US persons. Automated trading permitted (they provide an API for this purpose). Must comply with position limits. |
| Polymarket | Unregulated (crypto) | Geo-blocked for US persons. If operating from outside US or via legal structure, verify compliance with local jurisdiction. |
| PredictIt | CFTC no-action letter (status uncertain) | Automated trading exists in a gray area. Their ToS doesn't explicitly prohibit API access, but they ban accounts at their discretion. |
| Metaculus | N/A | Not a trading venue. No regulatory concerns for prediction submission. |

### 11.2 Platform ToS Compliance

- **API usage:** Only use documented/official APIs. Do not reverse-engineer undocumented endpoints (exception: PredictIt, where the unofficial API is widely used and tolerated).
- **Rate limits:** Hard-enforce rate limits in the adapter layer. Never exceed documented limits. Implement exponential backoff on 429 responses.
- **Multi-accounting:** One account per platform. Period.
- **Market manipulation:** Never place orders intended to mislead other participants. All orders must represent genuine trading intent.

### 11.3 Tax Implications

- Kalshi trades: likely Section 1256 contracts (60% long-term / 40% short-term capital gains). Consult a CPA.
- Polymarket trades: crypto capital gains rules apply (short-term if held < 1 year).
- Track all trades with full audit trail (entry date, exit date, cost basis, proceeds).
- Generate Form 8949 compatible export at tax time.

### 11.4 Operational Risk

| Risk | Mitigation |
|------|-----------|
| Exchange API downtime | Graceful degradation — stop placing new orders, maintain existing positions. Redundant data sources where possible. |
| Data source failure | Source health monitoring with fallback sources. Feature computation handles missing data gracefully (forward-fill or exclude). |
| Model malfunction (outputs garbage) | Output validation (probabilities must be in [0,1], sum of multi-outcome probs must ≈ 1). Auto-deactivation on performance degradation. |
| Database failure | Automated daily backups to S3. Point-in-time recovery with WAL archiving. |
| Complete system failure | All positions are on the exchange — they settle regardless of whether Sigil is running. No margin calls in prediction markets. Worst case: miss some edge while system is down. |

### 11.5 Financial Risk

- **Max loss scenario:** Entire bankroll deployed, every position settles to $0. This is why position limits exist.
- **Realistic bad scenario:** 20% drawdown over 30 days due to model miscalibration. Circuit breakers halt trading. Loss is bounded and recoverable.
- **Bankroll management:** Start with capital you can afford to lose entirely. Initial deployment: $5,000–$10,000. Scale only after 3+ months of positive live performance.
- **Never use leverage or borrowed funds.** Prediction markets don't offer leverage, but don't borrow to fund the bankroll.

---

## 12. Success Metrics & KPIs

### 12.1 Model Performance

| Metric | Phase 1 Target | Phase 3 Target | Measurement |
|--------|---------------|----------------|-------------|
| Brier Score (overall) | < 0.22 | < 0.18 | Rolling 90-day across all predictions |
| Calibration Error | < 0.05 | < 0.03 | Mean absolute deviation from perfect calibration |
| Log Loss | < 0.65 | < 0.55 | Rolling 90-day |

### 12.2 Financial Performance

| Metric | Phase 1 Target | Phase 3 Target | Measurement |
|--------|---------------|----------------|-------------|
| ROI (monthly) | > 5% | > 15% | Net P&L / average deployed capital |
| Sharpe Equivalent | > 0.8 | > 1.5 | Annualized return / annualized volatility |
| Max Drawdown | < 15% | < 20% | Worst peak-to-trough over rolling 90 days |
| Win Rate | > 52% | > 57% | Settled profitable trades / total settled trades |
| Avg Edge Captured | > 3¢ | > 6¢ | Mean (model_prob - market_prob) at entry for winning trades |

### 12.3 Operational

| Metric | Target | Measurement |
|--------|--------|-------------|
| Data pipeline uptime | > 99.5% | Percentage of scheduled fetches that succeed |
| End-to-end latency (time-critical) | < 15 seconds | p95 from data event to order submission |
| Dashboard availability | > 99% | Uptime monitoring |
| Alert delivery latency | < 30 seconds | Time from trigger to Telegram delivery |

### 12.4 Coverage

| Metric | Phase 1 Target | Phase 4 Target |
|--------|---------------|----------------|
| Active verticals | 2 (Sports, Politics) | 6+ |
| Markets tracked | 100+ | 1,000+ |
| Kalshi coverage | > 30% of active markets | > 80% |
| Data sources integrated | 10 | 40+ |

---

## 13. Decision Logs

| # | Decision | Options Considered | Choice | Reasoning |
|---|----------|--------------------|--------|-----------|
| D1 | Database architecture | (a) PostgreSQL + InfluxDB + MongoDB, (b) PostgreSQL + TimescaleDB only | **(b)** | Operational simplicity wins. One database to manage, backup, and query. TimescaleDB handles time-series within PostgreSQL. A solo operator cannot afford the cognitive overhead of three databases. |
| D2 | Service architecture | (a) Microservices + Kafka, (b) Monolith with clean modules | **(b)** | Microservices add deployment complexity, network latency, and debugging difficulty. A monolith with well-defined module boundaries achieves the same code organization without the operational cost. Migrate to services only if/when load demands it. |
| D3 | ML framework | (a) PyTorch for everything, (b) LightGBM primary + PyTorch optional | **(b)** | LightGBM trains in seconds on tabular data, handles missing values, and has excellent out-of-the-box performance. PyTorch adds value only for sequence models or deep learning experiments — don't reach for it by default. |
| D4 | Pipeline orchestration | (a) Airflow, (b) Dagster, (c) Prefect, (d) Cron + scripts | **(b) Dagster** | Airflow requires a separate scheduler and webserver. Dagster runs embedded with the Python process for dev, has an asset-based model that maps well to feature computation, and scales to production without architecture changes. |
| D5 | Frontend framework | (a) Streamlit, (b) Grafana dashboards, (c) Next.js custom | **(c) Next.js** | Streamlit is fast to prototype but sluggish and limited for real-time data. Grafana is great for metrics but not for custom trading UIs. Next.js gives full control, real-time WebSocket updates, and professional UX. The investment pays off as the dashboard becomes the primary operational interface. |
| D6 | Alerting system | (a) PagerDuty, (b) Slack, (c) Email, (d) Telegram | **(d) Telegram** | Instant mobile delivery, free, simple API (one HTTP POST), supports formatting. PagerDuty is overkill for a solo operator. Slack requires a workspace. Email has unacceptable latency. |
| D7 | Deployment | (a) AWS/GCP + Kubernetes, (b) Single VPS + Docker Compose | **(b)** | The entire system fits on a $40/month Hetzner VPS (8 vCPU, 16GB RAM, 160GB NVMe). Kubernetes adds weeks of infrastructure work for zero benefit at this scale. Docker Compose gives you all the containerization benefits with `docker compose up`. |
| D8 | Kelly fraction | (a) Full Kelly, (b) Half Kelly, (c) Quarter Kelly | **(c) Quarter Kelly** | Full Kelly is mathematically optimal for long-run growth but practically dangerous — 50% drawdown probability. Quarter Kelly sacrifices ~44% of growth rate but reduces max expected drawdown to ~12%. For a solo operator whose bankroll is limited, survival matters more than growth optimization. |

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| **Binary market** | A market with two outcomes (Yes/No) that resolves to $1.00 or $0.00. |
| **Brier score** | Mean squared error between predicted probabilities and actual outcomes. Lower is better. Perfect = 0, coin-flip = 0.25. |
| **Calibration** | The property of predictions where X% confidence events actually occur X% of the time. A calibrated model's predictions match observed frequencies. |
| **Edge** | The difference between model-estimated probability and market-implied probability. Positive edge means the model believes the market is underpricing the outcome. |
| **EV (Expected Value)** | The probability-weighted average outcome of a bet. EV = P(win) × payout − P(lose) × cost. Positive EV = profitable in expectation. |
| **Kelly Criterion** | A formula for optimal bet sizing that maximizes the long-run geometric growth rate of a bankroll. Kelly fraction = edge / odds. |
| **Implied probability** | The probability derived from a market price. For a binary market priced at $0.60, the implied probability of "Yes" is 60%. |
| **Maker/taker** | Maker: places a limit order that rests on the order book (adds liquidity). Taker: places an order that immediately matches an existing order (removes liquidity). Makers often pay lower fees. |
| **Market-implied probability** | See implied probability. |
| **Multi-outcome market** | A market with more than two possible outcomes (e.g., "Who will win the election?" with 5 candidates). |
| **PSI (Population Stability Index)** | A measure of how much a variable's distribution has shifted over time. Used to detect feature drift. PSI > 0.2 indicates significant drift. |
| **Resolution** | The event of a market settling — the outcome is determined, and contracts pay out accordingly. |
| **Resolution source** | The authority or data point used to determine market resolution (e.g., "Associated Press race call" for election markets). |
| **Scalar market** | A market that resolves to a value on a continuous scale (e.g., "What will the unemployment rate be?"), not just Yes/No. |
| **Settlement** | See resolution. The process of closing out positions and distributing payouts after a market resolves. |
| **Sharp money** | Informed, professional betting activity. Sharp line movement (odds moving despite balanced action) signals where professional bettors are placing. |
| **Slippage** | The difference between the expected price of a trade and the actual fill price, usually caused by moving the order book with large orders. |
| **Walk-forward validation** | A backtesting method where the model is trained on expanding historical windows and tested on subsequent out-of-sample periods, simulating real-time deployment. |

---

## 15. Appendices

### Appendix A: Data Source Catalog

Complete list of data sources with integration priority:

| Priority | Source | Vertical | API Type | Cost | Phase |
|----------|--------|----------|----------|------|-------|
| P0 | Kalshi API | All | REST + WS | Free | 1 |
| P0 | The Odds API | Sports | REST | $50/mo | 1 |
| P0 | ESPN API | Sports | REST | Free | 1 |
| P0 | FiveThirtyEight | Politics | Download | Free | 1 |
| P0 | FRED | Economics | REST | Free | 1 |
| P1 | Polymarket CLOB | All | REST + WS | Free | 2 |
| P1 | RealClearPolitics | Politics | Scrape | Free | 2 |
| P1 | NWS/NOAA | Weather | REST | Free | 2 |
| P1 | Open-Meteo | Weather | REST | Free | 2 |
| P1 | CoinGecko | Crypto | REST | Free | 2 |
| P1 | CME FedWatch | Economics | Scrape | Free | 2 |
| P2 | Twitter/X API | Multi | REST + Stream | $100/mo | 2 |
| P2 | Gold Derby | Entertainment | Scrape | Free | 3 |
| P2 | Glassnode | Crypto | REST | $30/mo | 3 |
| P2 | DeFi Llama | Crypto | REST | Free | 3 |
| P2 | Metaculus | Multi | REST | Free | 2 |
| P2 | Google Trends | Multi | pytrends | Free | 3 |
| P2 | Wikipedia Pageviews | Entertainment | REST | Free | 3 |
| P3 | Sportradar | Sports | REST | $$$ | 3+ |
| P3 | LunarCrush | Crypto | REST | Free | 3 |
| P3 | Congress.gov | Politics | REST | Free | 3 |
| P3 | OpenSecrets/FEC | Politics | REST | Free | 3+ |
| P3 | Box Office Mojo | Entertainment | Scrape | Free | 4 |

### Appendix B: Database Schema (Key Tables)

```sql
-- Core market representation
CREATE TABLE markets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,  -- 'kalshi', 'polymarket'
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    taxonomy_l1 TEXT NOT NULL,
    taxonomy_l2 TEXT,
    taxonomy_l3 TEXT,
    market_type TEXT NOT NULL DEFAULT 'binary',  -- 'binary', 'scalar', 'multi'
    resolution_date TIMESTAMPTZ,
    resolution_source TEXT,
    status TEXT NOT NULL DEFAULT 'open',  -- 'open', 'closed', 'settled'
    settlement_value NUMERIC,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(platform, external_id)
);

-- Time-series price data (TimescaleDB hypertable)
CREATE TABLE market_prices (
    time TIMESTAMPTZ NOT NULL,
    market_id UUID NOT NULL REFERENCES markets(id),
    bid NUMERIC,
    ask NUMERIC,
    last_price NUMERIC,
    volume_24h NUMERIC,
    open_interest NUMERIC,
    source TEXT NOT NULL  -- 'exchange', 'odds_api', etc.
);
SELECT create_hypertable('market_prices', 'time');

-- Computed features
CREATE TABLE features (
    time TIMESTAMPTZ NOT NULL,
    market_id UUID REFERENCES markets(id),
    entity_id TEXT,  -- For entity-level features (team, player, candidate)
    feature_name TEXT NOT NULL,
    feature_version INT NOT NULL DEFAULT 1,
    value NUMERIC NOT NULL,
    metadata JSONB DEFAULT '{}'
);
SELECT create_hypertable('features', 'time');

-- Model predictions
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id UUID NOT NULL REFERENCES markets(id),
    model_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    predicted_prob NUMERIC NOT NULL CHECK (predicted_prob BETWEEN 0 AND 1),
    confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
    market_price_at_prediction NUMERIC,
    edge NUMERIC,  -- predicted_prob - market_price_at_prediction
    features_snapshot JSONB,  -- Key feature values at prediction time
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Orders and trades
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_order_id TEXT,
    platform TEXT NOT NULL,
    market_id UUID NOT NULL REFERENCES markets(id),
    prediction_id UUID REFERENCES predictions(id),
    side TEXT NOT NULL,  -- 'buy', 'sell'
    outcome TEXT NOT NULL,  -- 'yes', 'no'
    order_type TEXT NOT NULL,  -- 'limit', 'market'
    price NUMERIC NOT NULL,
    quantity INT NOT NULL,
    filled_quantity INT DEFAULT 0,
    avg_fill_price NUMERIC,
    fees NUMERIC DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'created',
    model_id TEXT,
    edge_at_entry NUMERIC,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Positions (derived but cached for performance)
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform TEXT NOT NULL,
    market_id UUID NOT NULL REFERENCES markets(id),
    outcome TEXT NOT NULL,
    quantity INT NOT NULL,
    avg_entry_price NUMERIC NOT NULL,
    current_price NUMERIC,
    unrealized_pnl NUMERIC,
    realized_pnl NUMERIC DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',  -- 'open', 'closed'
    opened_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ,
    UNIQUE(platform, market_id, outcome)
);

-- Data source health tracking
CREATE TABLE source_health (
    source_name TEXT NOT NULL,
    check_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL,  -- 'ok', 'error', 'timeout'
    latency_ms INT,
    error_message TEXT,
    records_fetched INT
);
SELECT create_hypertable('source_health', 'check_time');

-- Index strategy
CREATE INDEX idx_markets_taxonomy ON markets(taxonomy_l1, taxonomy_l2, status);
CREATE INDEX idx_markets_platform ON markets(platform, status);
CREATE INDEX idx_predictions_market ON predictions(market_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status, created_at DESC);
CREATE INDEX idx_positions_open ON positions(status) WHERE status = 'open';
```

### Appendix C: Model Specification Template

Each model must document:

```yaml
model_id: "nfl_game_winner_lgbm_v3"
vertical: "sports"
sub_vertical: "nfl"
market_type: "game_winner"
algorithm: "LightGBM"
training_data:
  source: "ESPN + The Odds API"
  date_range: "2020-09-01 to 2026-02-01"
  sample_size: 4200  # regular season + playoff games
features:
  - name: "elo_diff"
    description: "Home team Elo - Away team Elo"
    type: "numeric"
  - name: "home_rest_days"
    description: "Days since home team's last game"
    type: "numeric"
  - name: "away_rest_days"
    description: "Days since away team's last game"
    type: "numeric"
  - name: "home_rolling_win_pct_10"
    description: "Home team win % over last 10 games"
    type: "numeric"
  # ... (full feature list)
hyperparameters:
  n_estimators: 500
  learning_rate: 0.05
  max_depth: 6
  num_leaves: 31
  min_child_samples: 20
  subsample: 0.8
  colsample_bytree: 0.8
validation:
  method: "walk-forward"
  train_window: "expanding"
  test_window: "1 month"
  purge_gap: "7 days"
performance:
  brier_score: 0.195
  calibration_error: 0.028
  roi_backtest: 12.3
  win_rate: 56.2
  sharpe: 1.7
retrain_schedule: "daily after last game settles"
deactivation_threshold:
  brier_score_max: 0.25
  roi_30d_min: -10
```

### Appendix D: Risk Parameter Defaults

```yaml
# Position limits
max_position_per_market_pct: 5.0  # % of bankroll
max_category_exposure_pct: 25.0
max_platform_exposure_pct: 50.0
max_correlated_position_pct: 15.0

# Kelly sizing
kelly_fraction: 0.25  # Quarter Kelly
min_edge_to_trade_kalshi: 0.10  # 10 cents
min_edge_to_trade_polymarket: 0.05  # 5 cents
min_edge_to_trade_predictit: 0.18  # 18 cents
min_confidence_to_trade: 0.5  # Model confidence threshold

# Circuit breakers
drawdown_warning_pct: 10.0  # Reduce size to 50%
drawdown_halt_pct: 15.0  # Stop new trades
drawdown_shutdown_pct: 20.0  # Full system halt
drawdown_window_days: 30  # Rolling window for drawdown calc

# Execution
max_slippage_cents: 2  # Cancel order if slippage > 2 cents
order_timeout_seconds: 3600  # Cancel unfilled limit orders after 1 hour
reconciliation_interval_seconds: 300  # Check exchange state every 5 min

# Data quality
max_stale_intervals: 2  # Forward-fill for 2 missed intervals, then exclude
anomaly_zscore_threshold: 3.0  # Flag data points > 3 sigma
source_failure_warning: 3  # consecutive failures
source_failure_critical: 10

# Model health
brier_score_warning: 0.25
calibration_error_warning: 0.05
model_roi_30d_deactivation: -10.0  # Auto-deactivate at -10% 30-day ROI
```

### Appendix E: Project Directory Structure

```
sigil/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── README.md
├── docs/
│   └── prd.md                    # This document
├── src/
│   ├── sigil/
│   │   ├── __init__.py
│   │   ├── config.py             # Settings, env vars, risk params
│   │   ├── db.py                 # Database connection, migrations
│   │   ├── models.py             # SQLAlchemy/dataclass models
│   │   │
│   │   ├── ingestion/            # Data ingestion layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # DataSource protocol
│   │   │   ├── kalshi.py         # Kalshi market data
│   │   │   ├── polymarket.py     # Polymarket CLOB data
│   │   │   ├── odds_api.py       # The Odds API
│   │   │   ├── espn.py           # ESPN stats
│   │   │   ├── polls.py          # FiveThirtyEight, RCP
│   │   │   ├── fred.py           # FRED economic data
│   │   │   ├── weather.py        # NWS, Open-Meteo
│   │   │   └── scheduler.py      # Polling scheduler
│   │   │
│   │   ├── features/             # Feature computation
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # FeatureExtractor protocol
│   │   │   ├── sports.py         # Sports features (Elo, rolling stats)
│   │   │   ├── politics.py       # Polling averages, fundamentals
│   │   │   ├── economics.py      # Macro features
│   │   │   ├── weather.py        # Ensemble model features
│   │   │   └── store.py          # Feature store (DB + Redis)
│   │   │
│   │   ├── modeling/             # ML models
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Model protocol
│   │   │   ├── sports/
│   │   │   │   ├── elo.py
│   │   │   │   ├── lgbm_game.py
│   │   │   │   └── live_win_prob.py
│   │   │   ├── politics/
│   │   │   │   ├── poll_avg.py
│   │   │   │   └── fundamentals.py
│   │   │   ├── ensemble.py       # Ensemble strategies
│   │   │   ├── calibration.py    # Calibration utilities
│   │   │   └── registry.py       # MLflow integration
│   │   │
│   │   ├── execution/            # Trade execution
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # ExchangeAdapter protocol
│   │   │   ├── kalshi.py         # Kalshi order management
│   │   │   ├── polymarket.py     # Polymarket order management
│   │   │   ├── oms.py            # Order management system
│   │   │   ├── risk.py           # Risk checks, position limits
│   │   │   └── sizing.py         # Kelly criterion, position sizing
│   │   │
│   │   ├── decision/             # Signal → trade decision
│   │   │   ├── __init__.py
│   │   │   └── engine.py         # Edge evaluation, trade/no-trade logic
│   │   │
│   │   ├── verticals/            # Vertical module definitions
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # VerticalModule dataclass
│   │   │   ├── sports_nfl.py
│   │   │   ├── sports_nba.py
│   │   │   ├── politics_us.py
│   │   │   ├── economics_macro.py
│   │   │   └── weather.py
│   │   │
│   │   ├── backtesting/          # Backtesting framework
│   │   │   ├── __init__.py
│   │   │   ├── engine.py         # Event-driven backtester
│   │   │   ├── metrics.py        # Brier, calibration, ROI, etc.
│   │   │   └── visualization.py  # Plotly charts for backtest results
│   │   │
│   │   ├── alerts/               # Alerting
│   │   │   ├── __init__.py
│   │   │   └── telegram.py       # Telegram bot notifications
│   │   │
│   │   ├── api/                  # Internal API for dashboard
│   │   │   ├── __init__.py
│   │   │   └── routes.py         # FastAPI endpoints
│   │   │
│   │   └── cli.py                # CLI tool (typer)
│   │
│   └── dashboard/                # Next.js frontend
│       ├── package.json
│       ├── next.config.js
│       ├── src/
│       │   ├── app/
│       │   │   ├── page.tsx      # Command Center
│       │   │   ├── markets/
│       │   │   ├── signals/
│       │   │   ├── positions/
│       │   │   ├── models/
│       │   │   ├── data-health/
│       │   │   ├── backtest/
│       │   │   └── settings/
│       │   ├── components/
│       │   └── lib/
│       └── ...
│
├── tests/
│   ├── test_ingestion/
│   ├── test_features/
│   ├── test_models/
│   ├── test_execution/
│   └── test_backtesting/
│
├── migrations/                   # Alembic DB migrations
│   └── versions/
│
├── notebooks/                    # Jupyter notebooks for analysis
│   ├── eda/
│   └── model_development/
│
└── scripts/
    ├── seed_historical_data.py
    └── run_backtest.py
```

---

*This document is a living specification. Update it as decisions are made, models are validated, and the system evolves. The first version is always wrong — the value is in having a clear starting point to iterate from.*

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | Not run. Reviewer flagged 15-25%/mo ROI target as unrealistic; user held scope. |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | Not run. Offered, skipped. |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 23 issues across 4 sections, all decided. 8 critical failure-mode gaps logged for implementation. 49 untested codepaths in coverage diagram. |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | Not run. Frontend in-scope but no design audit performed. |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | Not run. N/A for an internal trading system. |

**UNRESOLVED:** 0 (every issue got a user answer)
**CRITICAL GAPS:** 8 (idempotency, reconciliation, settlement, drawdown gate, Kelly edge cases, risk-check fail-closed, LLM backoff, OMS state-race) — all queued in `TODOS.md` and the test plan

**VERDICT:** Eng review complete with issues_open. Implementation can proceed lane-by-lane (S1→S8) per the parallelization plan. Recommend `/plan-design-review` before frontend wiring + `/codex review` for an independent challenge before merge.

