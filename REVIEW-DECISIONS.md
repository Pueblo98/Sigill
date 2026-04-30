# Eng Review Decisions — Single Source of Truth

This document captures the 23 decisions made during `/plan-eng-review` on 2026-04-30. **Every agent reads this before writing code.** When in doubt, this doc wins over the PRD.

---

## Architecture decisions

| ID | Decision | Implication |
|---|---|---|
| 1A | `VerticalModule` narrowed to `data_sources + feature_extractors` only. Models, execution rules, backtest config are per-vertical concrete code, not interface methods. | No god-object dataclass. Sports, politics, etc. each define their own concrete model + execution module. |
| 1B | **Drop TimescaleDB, Drop Redis, Drop Dagster.** Use plain Postgres with monthly partitions on time-series tables, in-process `cachetools.TTLCache` (or plain dict + TTLs) for caching, APScheduler in-process for scheduling. | `config.py` removes `REDIS_URL`. No Dagster install. No TimescaleDB extension. No Docker Compose for these services. |
| 1C | **Polymarket: read-only price reference only.** No order placement, no private key on box. The `PolymarketDataSource` stays for reading; no Polymarket adapter in `src/sigil/execution/`. | All cross-platform "arb" surfaces are display-only / educational. Decision engine never generates Polymarket orders. |
| 1D | **Reconciliation hysteresis: 3 consecutive consistent observations** before applying exchange-state-overrides-local. During the disagreement window: alert + freeze new orders on that market. | Need an in-memory or persisted observation tracker per (market_id, platform). |
| 1E | **Idempotency: client-supplied `client_order_id`** passed to the exchange on every order. On network timeout, retry with the SAME key — exchanges dedupe. | `Order.client_order_id` field is REQUIRED, unique, generated client-side as `sigil_<uuid>`. |
| 1F | **Secrets: sops + age.** `secrets.enc.yaml` lives in repo encrypted. Single age key on VPS decrypts at startup. | `~/.config/sigil/age.key` on box. CI never sees plaintext. |
| 1G | **Settlement: WS event-driven + hourly polling fallback.** Subscribe to Kalshi market-status WS channel. Hourly cron sweeps for any markets where WS missed an event. | Settlement handler is event-driven, not polled-every-5-min. |
| 1H | **Auth: Tailscale-only binding.** FastAPI binds to `100.x.y.z` (Tailscale interface), NOT `0.0.0.0`. No public exposure. No app-level auth needed. | `api/server.py` reads bind address from config; defaults to localhost for dev, Tailscale IP for prod. |

## Code-quality decisions

| ID | Decision | Implication |
|---|---|---|
| 2A | PRD §15 dir layout removed; canonical layout = current repo. | Don't try to match the PRD's `src/dashboard/` — it's `sigil-frontend/`. |
| 2B | **Composite PKs on time-series tables.** `(time, market_id)` for `market_prices`, `(check_time, source_name)` for `source_health`. UUIDs only on entity tables (markets, orders, predictions, positions). | See updated `models.py`. |
| 2C | **Drop `features_snapshot` JSONB on `Prediction`.** Replace with `prediction_features` child table (`prediction_id, feature_name, value, version`). | New table. Indexable. |
| 2D | Risk param renamed `max_market_slippage_cents`, scoped to market/IOC orders only. Limit orders ignore it. | `config.py` change. OMS check gated on `order_type in {market, ioc}`. |
| 2E | **`mode` column (`'paper' \| 'live'`) on `Order` and `Position`.** Single OMS gates at submit. Paper orders simulate fills against live order book snapshot. | Migration: add `mode` to both tables. OMS branches on `mode` before calling exchange API. |
| 2F | **Drawdown gate: ≥20 settled trades total + ≥5 settled in window** before circuit breaker fires. | Drawdown calc reads from settled positions; trip only when both gates pass. |

## Test decisions

| ID | Decision | Implication |
|---|---|---|
| 3A | **pytest + pytest-asyncio (PY); vitest (TS).** | `pyproject.toml` adds them. `sigil-frontend/vitest.config.ts` added. |
| 3B | **Coverage policy: 100% on 12 critical paths, 70% overall.** Every PR ships with its own tests. | The 12: Kelly sizing, OMS state machine, risk pre-trade, reconciliation hysteresis, drawdown gate, settlement handler, order idempotency, edge calc, backtest fill, Brier/calibration math, feature versioning, Telegram routing. |
| 3C | **Conservative backtest fill modeling.** Limit fills only at next-trade-price-or-better. Market fills at next trade + size-proportional slippage estimate. | `backtesting/execution_model.py` implements this. |
| 3D | **LLM eval suite alongside first LLM signal.** When injury-severity classifier ships, ships with `evals/injury_severity.jsonl` (~100 hand-graded cases). | Phase 3 work; not blocking now. |

## Performance decisions

| ID | Decision | Implication |
|---|---|---|
| 4A | **Odds API on $50/mo tier, 5-min freshness, active-window-only polling.** | `config.py`: `ODDS_API_FRESHNESS_SECONDS = 300`. Scheduler only runs Odds API jobs during US sports windows. |
| 4B | **5 missing indexes added upfront** (see schema). | Initial migration includes all indexes. |
| 4C | **Pool sizes documented in `config.py`.** asyncpg ~20-50; httpx per-host ~10 with semaphore. | `config.py`: `DB_POOL_MIN`, `DB_POOL_MAX`, `HTTPX_PER_HOST_LIMIT`. |
| 4D | **Frontend uses 5-second polling (SWR), no WebSocket dashboard channel.** | SWR already installed. Each page: `useSWR(url, fetcher, { refreshInterval: 5000 })`. |
| 4E | **No `<5 min` backtest SLA.** Backtests are batch (30-60 min), run async, dashboard shows status only. | Don't optimize for speed at the expense of code clarity. |

---

## Existing-code awareness (must read before editing)

| File | Status | Note |
|---|---|---|
| `src/sigil/db.py` | Working: Postgres-with-SQLite-fallback + `create_all`. | Replace `create_all` with alembic migrations in Lane A. |
| `src/sigil/models.py` | Updated by Wave 0 with the schema decisions above. | Source of truth for schema. |
| `src/sigil/config.py` | Updated by Wave 0 (REDIS_URL removed, pool sizes added, slippage param renamed). | |
| `src/sigil/main.py` | References `MarketManager`, `KalshiDataSource`, `TelegramAlerts`. Heartbeat orchestrator. | Will need rework to integrate OMS + decision engine. Lane A territory. |
| `src/sigil/ingestion/manager.py` | Existing `MarketManager` with `sync_source` + `upsert_market`. | Reuse — extend with hysteresis tracking. |
| `src/sigil/ingestion/runner.py` | New (untracked): `StreamProcessor` batches WS ticks → JSONL + Postgres. **BUG: stores `external_id` in `MarketPrice.market_id` (FK to UUID). Postgres will reject; SQLite permissive.** | Lane A must fix the FK type mismatch — look up Market.id by (platform, external_id) before insert. |
| `src/sigil/ingestion/kalshi.py`, `polymarket.py` | Working stream + REST adapters. Polymarket WS + REST, Kalshi WS + REST. | Polymarket usage scoped to read-only per 1C. |
| `src/sigil/api/server.py` | FastAPI app, binds `0.0.0.0:8000`. CORS to localhost:3000. | Lane C: change bind to read from config (Tailscale IP in prod). |
| `src/sigil/api/routes.py` | `/api/portfolio` (mocked), `/api/markets`, `/api/markets/{id}`, `/api/arbitrage` (uses difflib). | Lane C: replace mock portfolio with real query, use stat_arb scanner for arbitrage endpoint. **Same FK-type bug as runner.py on the price lookup join.** |
| `src/sigil/decision/__init__.py` | Exports `ArbDetector`, `StatArbScanner`, `ArbOpportunity`. | Lane B keeps these. |
| `src/sigil/decision/arb.py` | Simple `ArbDetector` — outdated, superseded by `stat_arb.py`. | Lane B: deprecate or remove. |
| `src/sigil/decision/stat_arb.py` | Comprehensive cross-platform arb scanner with rapidfuzz fuzzy matching, per-platform fee accounting, Kelly sizing for arb + stat-edge. **Demoted to read-only display per 1C** — engine never auto-trades Polymarket leg. | Lane B: keep as feature; engine warns if user tries to auto-execute Polymarket leg. |
| `src/sigil/alerts/telegram.py` | Exists. | Telegram routing logic for severity → channel. |
| `sigil-frontend/AGENTS.md` | **Critical:** "This is NOT the Next.js you know — read `node_modules/next/dist/docs/` before writing any code." | **Lane C MUST read those docs first.** Next 16.2.1, React 19.2.4, Tailwind 4. Heed deprecation notices. |
| `sigil-frontend/package.json` | Has `swr`, `zustand`, `recharts`, `radix-ui` already. | Use SWR for the 5-sec polling per 4D. |

---

## Lane assignments (Wave 1)

| Agent | Lane | Scope | Worktree-isolated |
|---|---|---|---|
| **A** | Lane A continuation (S2 + S3) | Ingest reliability (1D hysteresis, 1E idempotency, 1G settlement WS, FK-type bug fix). OMS state machine. Risk pre-trade checks (7 conditions). Kelly sizing with edge cases. | Yes |
| **B** | Lane B (S4) | Decision engine: edge calc with confidence weighting. Drawdown circuit breaker with min-trade gate (2F). `decision/engine.py` integrates with OMS from Lane A via repo-pattern interface. Keep `stat_arb.py` as display-only per 1C. | Yes |
| **C** | Lane C (S5 + S6) | FastAPI bind from config (1H). sops/age secrets loader (1F). Next.js wire to real API. Replace mock data. SWR 5-sec polling. **Read `sigil-frontend/node_modules/next/dist/docs/` before any frontend code.** | Yes |
| **D** | Lane D (S7) | Backtest engine. Conservative fill model (3C). Brier / log-loss / calibration math. Walk-forward + purged k-fold. Self-contained against schema. | Yes |

## Style conventions (all agents)

- Python: type hints everywhere. Black formatting. Async-first where IO is involved.
- TypeScript: strict mode. Explicit prop types. SWR keys are the URL strings.
- No comments unless the **why** is non-obvious. Don't echo identifier names.
- Tests live next to code under `tests/<module>/test_*.py` for Python, `*.test.ts` colocated for TS.
- No emojis in code or commits.
- Every PR adds tests for what it changes (3B). Critical paths get 100% coverage.
- Don't add features beyond the lane scope. If something is out-of-lane, leave a `TODO(lane-X)` comment.

## Coordination (avoid merge conflicts)

- **Schema is locked** by Wave 0. Don't modify `src/sigil/models.py` unless you're adding a NEW table. Existing tables, columns, indexes are settled.
- **`config.py` is locked** by Wave 0. New params: add to bottom with a clear comment.
- **`db.py` is in Lane A's territory.** Other lanes don't touch it.
- **`api/routes.py` is in Lane C's territory** for endpoint additions. Lane B may add new endpoints but defer to C for shape.
- **`stat_arb.py` is in Lane B's territory.**
- **Frontend pages are in Lane C's territory.**

When unsure, leave a comment with `# Lane-X-question:` and let Wave 2 reconcile.
