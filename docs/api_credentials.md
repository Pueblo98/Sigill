# Sigil Credential Checklist

This document consolidates every credential, API key, and auth artifact mentioned in the PRD so we can request access up front. Costs are indicative and pulled from the PRD; confirm before purchase.

> **Scope:** Internal/personal use only — these integrations power Sigil's private workflows and the supporting website, not a commercial resale offering.

## Exchanges & Trading Venues

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| Kalshi | API key + secret | Required for REST/WebSocket trading (market data, order placement). Needed immediately for Phase 1. |
| Polymarket | (1) API key for CLOB reads, (2) Ethereum wallet private key (EIP-712 signing) | Wallet signs Polygon orders; API key covers authenticated data endpoints. Coordinate secure key storage + Polygon gas funding. |
| PredictIt | Logged-in session cookies | No key-based API; scrape using authenticated browser session. Keep cookies fresh and throttle requests. |
| Metaculus | Session token from login endpoint | Used for authenticated POSTs and downloading community prediction histories. |

## Sports Vertical

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| The Odds API | Paid API key (~$50+/mo tier) | Live sportsbook line movements, sharp money proxy. Phase 1 P0 dependency. |
| Sportradar | Enterprise API subscription | Optional high-fidelity stats/play-by-play feed. Explore startup/academic pricing before committing. |
| Opta / Genius Sports | Commercial license + API credentials | Deep soccer data (event-level touches, expected goals, tracking). Industry standard but expensive; requires NDAs and data use agreement. |
| StatsBomb | Commercial API key (Open Data limited) | Rich soccer event data (pressures, xThreat, shot quality). Open Data covers select leagues; full coverage needs paid license + API token. |
| SportMonks / API-Football | Subscription API key | Faster-to-onboard soccer feed (fixtures, player stats, odds). Useful bridge while negotiating Opta/StatsBomb access. |
| Twitter / X | API key, secret, access token, bearer token (Basic $100/mo) | Real-time injury/news ingestion for sports plus cross-vertical sentiment. |
| OpenWeatherMap | API key (free tier OK) | Game-day weather adjustments for outdoor events. |

## Politics & Economics Data

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| FRED | API key | Macro-economic time series for both politics and economics verticals. |
| Congress.gov | API key | Bill status / votes feed for politics models. |
| OpenSecrets & FEC | API keys | Campaign finance data (quarterly filings + transaction feed). |
| BLS | API key | CPI, PPI, employment datasets used in macro releases. |
| Trading Economics | Paid API subscription | Consensus forecasts for upcoming releases; cited as $$ cost. |

## Entertainment & Culture

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| Spotify Charts API | Client ID/secret | Streaming counts and chart positions. |
| TMDb / OMDb | API keys (free tier) | Film/TV metadata and ratings for awards markets. |

## Weather & Climate

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| Visual Crossing | API key (free tier up to 1k calls/day) | Historical + 15-day forecast data supplementing NOAA/Open-Meteo feeds. |

## Aviation & Mobility Intelligence

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| FlightAware AeroAPI | API key + billing account | Global flight status, filed flight plans, historical tracks. Paid per request; covers both commercial and private flights where ADS-B is available. |
| FlightRadar24 Business API | Business subscription + API token | Live flight positions, airport departures/arrivals, equipment metadata. Requires enterprise agreement. |
| ADS-B Exchange API | API key (free for light use, paid tiers for bulk) | Unfiltered ADS-B data for private jet tracking and bespoke analytics. Self-host option if contributing receiver data. |
| OpenSky Network | Account credentials / API token | Community-sourced ADS-B feed with historical queries (rate-limited). Useful supplementary dataset. |
| Aviationstack | API key | Cost-effective REST API aggregating schedules, routes, and airline metadata. Good for prototyping before committing to premium vendors. |

## Crypto & Web3 Data

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| Glassnode | API key (paid tier, $30–800/mo) | On-chain metrics (MVRV, SOPR, exchange flows). |
| Dune Analytics | API key | Custom SQL queries for blockchain datasets. |
| Binance | API key/secret | Authenticated endpoints if we need more than public order book data. |
| Coinbase | API key/secret | Same as Binance; plan for optional authenticated usage. |
| LunarCrush | API key (free tier) | Social sentiment/volume metrics. |
| Coinglass | API key (free tier) | Funding rates, open interest, liquidation stats. |

## Attention, News & Narrative Data

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| GDELT | API key (optional, register for higher quotas) | Global news/event graph, tone, and actor metadata for spotting narrative trends impacting markets. |
| NewsAPI / Bloomberg Alpaca News* | API keys (paid for Bloomberg) | Structured article metadata and full-text headlines for building media sentiment scores. (*Bloomberg feed requires enterprise contract.) |
| Reddit API | OAuth app (client ID/secret) | Community chatter (WallStreetBets, politics subs) for attention and rumor tracking. |
| Pushshift replacement (e.g., metacad/proprietary) | API key / subscription | Historical Reddit/comment archives post-Pushshift API shutdown. Needed for backfilling training data. |
| Google Trends (pytrends) | Google account (no key) | Already free but include account-level access for quota tracking; use service account if automated heavily. |

## LLM & Alerting

| Service | Credential(s) Needed | Purpose / Notes |
|---------|---------------------|-----------------|
| Anthropic Claude API | API key | LLM-assisted injury/debate transcript analysis (Phase 3). |
| Telegram Bot API | Bot token from BotFather | Alert delivery for drawdowns, execution failures, high-edge signals. |

## Public / No-Key Sources (For reference)

The PRD lists several data feeds that do **not** require credentials beyond respectful rate limiting: ESPN, Pro Football Reference, RealClearPolitics scraping, NOAA/NWS, Open-Meteo, Google Trends (`pytrends`), Gold Derby, Box Office Mojo, Wikipedia Pageviews, CME FedWatch, CoinGecko, DeFi Llama, etc. Only monitor for ToS changes.

## Next Steps

1. Kick off onboarding with Kalshi and provision a secure Polygon wallet for Polymarket signing.
2. Submit requests/purchase orders for paid APIs (`The Odds API`, Twitter Basic, Trading Economics, Glassnode tiers`).
3. Register for the remaining free keys (FRED, BLS, Congress.gov, OpenWeatherMap, OpenSecrets/FEC, Visual Crossing, TMDb/OMDb, Spotify, Dune, LunarCrush, Coinglass, Telegram bot, Claude).
4. Start enterprise conversations for deep soccer and aviation feeds (Opta/StatsBomb, FlightAware/FlightRadar24) and secure interim access via SportMonks/API-Football + Aviationstack while contracts finalize.
