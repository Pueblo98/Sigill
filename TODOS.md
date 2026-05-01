# TODOs

Captured from /plan-eng-review on 2026-04-30. Each entry has the context a future maintainer needs to pick it up cold.

---

## TODO-1: ~~Archive Kalshi order book snapshots~~ — DONE

**Status:** Shipped. `OrderbookArchive` writes per-market per-day JSONL
at `<ORDERBOOK_ARCHIVE_DIR>/kalshi/<external_id>/<YYYY-MM-DD>.jsonl`,
hooked into `StreamProcessor._flush_once()` and gated by
`config.ORDERBOOK_ARCHIVE_ENABLED` (default `False`). Kalshi WS payloads
now carry the raw `bids`/`asks` ladder so depth survives. Reader =
TODO-9.

See `RUNBOOK.md` ("Enabling the orderbook archive") for the operator
recipe.

---

## TODO-2: Calibration scorecard dashboard

**What:** A `/calibration` dashboard view that plots model-predicted probabilities vs. observed frequencies (calibration curve), with rolling 30/90/365-day Brier and log-loss decomposed by vertical and model.

**Why:** P&L over short windows is dominated by variance. A miscalibrated model can still post good P&L for months by luck. The lived KPI for the system is whether predictions are well-calibrated. Without surfacing calibration as a first-class metric, attribution between skill and luck is impossible.

**Pros:**
- Catches model degradation before P&L does
- Makes champion/challenger comparisons meaningful (challenger may have worse short-window P&L but better calibration → more durable)
- Separates "we got unlucky" from "model is broken"

**Cons:**
- Requires meaningful sample size to be informative (~100+ settled trades per model)
- Requires UI build-out

**Context:** PRD §4 already specifies Brier score / calibration error as backtest metrics, but the dashboard's `Model Performance` view (§7.1.5) lumps them with ROI. They deserve their own surface. Build after 30+ days of paper-trading data accumulates so there's something to render.

**Depends on / blocked by:** Paper trading infrastructure (Phase 1 wk 6). Settles ~50+ trades per active vertical.

**Estimated effort:** ~3 days CC-paced. Requires `predictions` + `markets` tables joined on `settlement_value`.

---

## TODO-3: Quarterly DB backup + restore drill

**What:** (a) Set up automated daily Postgres backup to S3 with WAL archiving for PITR. (b) Schedule a quarterly calendar reminder to restore from backup on a fresh VM and verify integrity. Document each drill in `runbooks/backup-restore.md`.

**Why:** Untested backups fail >50% of the time when they're actually needed (industry observation). Sigil is a money-bearing system; data loss = trade history loss = tax problem + recovery problem. PRD §11.4 mentions "automated daily backups to S3" but specifies no restore drill, no encryption, no test plan.

**Pros:**
- Catches backup misconfig (wrong DB, bad credentials, missing tables) before you actually need it
- Forces documentation of restore procedure
- Cheap quarterly cadence — ~30 min per drill

**Cons:**
- Calendar discipline required
- Quarterly drill needs a fresh VM each time (small cost)

**Context:** This is a classic "systems over heroes" gap. The 3am-tired version of you doesn't remember backup config; the documented restore drill does. Add to setup runbook + recurring quarterly task tracker.

**Depends on / blocked by:** Postgres + alembic migrations exist (Phase 1 wk 1-2).

**Estimated effort:** ~1 day to set up automated backups + WAL archiving + first drill. ~30 min per subsequent drill.

---

## TODO-4: OMS does not open a Position row on paper-fill

**What:** When `OMS.submit()` short-circuits to FILLED in paper mode, it
updates the `Order` row but never inserts/updates a `Position` row. The
smoke script (`scripts/smoke_paper_flow.py`) has to mirror a Position by
hand for settlement to have something to close.

**Why:** Settlement handler, reconciliation, and the drawdown bankroll
snapshot all read from `Position`. Without OMS writing it, a green order
flow can't progress to a green close-out without manual SQL.

**Where to fix:** `src/sigil/execution/oms.py` — after `_simulate_paper_fill`
returns, upsert a `Position` keyed on (platform, market_id, outcome, mode).
Same logic should run on live fills too (currently no live-fill code path
opens positions either; reconciliation backfills them on the periodic
sweep, which is later than ideal).

**Discovered:** Wave 2 W2.4 smoke test, 2026-04-30.

---

## TODO-5: Settlement subscriber not wired into main.py

**What:** `run_ws_subscriber()` is implemented, tested end-to-end, and
ready, but `src/sigil/main.py` only runs `MarketManager.sync_source()` +
the bankroll snapshot job. A second `asyncio.create_task` is needed for
the WS settlement loop, plus the hourly polling fallback.

**Discovered:** Wave 2 W2.4, 2026-04-30.

---

## TODO-6: Dashboard widget theming via WidgetBase context

**What:** F2's chart widgets (`charts.py`) use a module-level `set_theme()` to
get accent/positive/negative colors into matplotlib. Cleaner: F1's loader
sets the active theme on the registry once at startup, and `WidgetBase`
exposes `self.theme` for child widgets that need it (charts, anything with
color-coded states).

**Why:** module-level state is hard to test in isolation and prevents per-
page theme overrides if we ever want them.

**Discovered:** Phase 5 Lane F2 report, 2026-04-30. Not blocking 5.0.

---

## TODO-7: Per-widget TTL in DashboardCache

**What:** F1's `DashboardCache` uses a single `cachetools.TTLCache` with one
global TTL. Each widget already declares its own `cache_ttl`, and
`requires_update()` enforces per-widget timing — but the LRU eviction can
drop a `1h` entry as fast as a `30s` one because the cache itself doesn't
know about per-key TTLs.

**Fix sketch:** maintain per-widget-type TTLCache instances inside
`DashboardCache`, or use `cachetools.LRUCache` plus an explicit (key, expiry)
tuple.

**Discovered:** F2 report, 2026-04-30. Subtle correctness issue, not a 5.0
blocker.

---

## TODO-8: Persist BacktestResult so the widget has data

**What:** Lane D's `Backtester.run()` returns an in-memory `BacktestResult`;
nothing persists it. F2's `backtest_results` widget queries a hypothetical
`backtest_results` table via raw SQL and treats `OperationalError ("no such
table")` as the empty state.

**Fix:** add a `BacktestResult` ORM table (id, model_id, run_at, brier,
roi, max_drawdown, sharpe, equity_curve_json, trades_json), an alembic
migration, and a `persist_backtest_result(session, result)` helper.

**Discovered:** F2 report, 2026-04-30.

---

## TODO-9: Replay reader — orderbook archive → Backtester

**What:** A reader that streams `<ORDERBOOK_ARCHIVE_DIR>/kalshi/<ext>/<date>.jsonl`
files into `Iterable[PriceTick]` for `Backtester(data_iter=...)`. Resolve
`(platform, external_id) → Market.id` (UUID) once per market per run,
cache it, then yield ticks chronologically. Filter by date range / market
list at the file-glob layer.

**Why:** TODO-1 just shipped the writer; the format is the contract. The
reader unlocks "did this strategy work last week" against the live
Kalshi tape instead of synthetic fixtures.

**Where to put it:** `src/sigil/backtesting/replay.py`. The backtester
takes `Iterable[Event]` (`engine.py:132-149`); a generator that yields
`PriceTick` is enough — no new framework needed.

**Format reminder:** each JSONL line has `external_id`, `time` (ISO UTC),
`bid`, `ask`, `last_price`, `volume_24h`, `bids`, `asks`, `source`.
Reader pulls `bid`/`ask`/`last_price`/`volume_24h` into `PriceTick`;
`bids`/`asks` are reserved for a future depth-aware backtester.

**Discovered:** TODO-1 ship, 2026-05-01.

---

## Decisions deferred but logged (not actioned)

- **15-25% monthly ROI target:** held as PRD-stated; reviewer flagged as fantasy but user chose hold-scope.
- **Outside voice (codex/claude subagent):** offered, skipped. Run `/codex review` separately if independent challenge desired before implementation.

---

## Decisions implemented per review (not TODOs — captured here for traceability)

| Decision | Source |
|---|---|
| `VerticalModule` narrowed to data + features only | 1A |
| Drop TimescaleDB, Redis, Dagster | 1B |
| Polymarket: read-only adapter, no order placement | 1C |
| Reconciliation hysteresis (3 consecutive matches) | 1D |
| Client-side `client_order_id` idempotency + retry-on-timeout | 1E |
| sops + age for secrets | 1F |
| Settlement: WS-driven + hourly polling fallback | 1G |
| Tailscale-only binding for FastAPI/Next.js | 1H |
| §15 directory layout removed from PRD; pointer to repo | 2A |
| UUIDs for entity tables, composite PK on time-series | 2B |
| Normalize features_snapshot to prediction_features child | 2C |
| Rename + scope `max_market_slippage_cents` to market/IOC | 2D |
| `mode` (paper/live) column at order/position level | 2E |
| Drawdown gate: ≥20 settled total + ≥5 in window | 2F |
| pytest + pytest-asyncio (PY); vitest (TS) | 3A |
| Coverage policy: 100% on 12 critical paths, 70% overall | 3B |
| Conservative backtest fill modeling | 3C |
| LLM eval suite alongside first LLM signal | 3D |
| Odds API: 5-min freshness on $50/mo tier | 4A |
| Add 5 missing schema indexes upfront | 4B |
| Pool sizes documented in `config.py` | 4C |
| 5-second polling for dashboard (no WS) | 4D |
| Drop <5 min backtest SLA | 4E |
