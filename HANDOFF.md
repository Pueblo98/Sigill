# Sigil — Context Handoff for Next Session

**Date written:** 2026-05-01 (post TODO-1 + TODO-9 — Kalshi orderbook
archive writer AND replay reader). Branch: `main`. Working dir
`C:\Users\simon\OneDrive\Desktop\Gamblerr`. Platform: Windows 11, bash shell,
Python 3.12.

Paste the METAPROMPT section below into a fresh Claude Code session. Don't
replay the conversation — read the docs it references.

---

## METAPROMPT — copy this to the next agent

> You are continuing work on **Sigil**, a Python prediction-market trading
> platform (Kalshi + Polymarket-as-reference). Working dir
> `C:\Users\simon\OneDrive\Desktop\Gamblerr`. Python 3.12, bash on Windows.
>
> **What's already landed:** Wave 1 (ingestion, OMS, risk, sizing, decision
> engine, backtest engine), Wave 2 (settlement WS, Telegram routing,
> critical-path coverage), Phase 5.0 (server-rendered Python dashboard at `/`
> with 12 widgets across 4 pages, per-widget TTL cache, 60s background
> refresh). The Next.js frontend at `sigil-frontend/` is **still running**
> for parity verification — **don't delete it**, that's Phase 5.2 work and
> needs operator sign-off.
>
> **Test bar:** 374/374 passing under `.venv/Scripts/python.exe -m pytest`.
> Don't let regressions land unnoticed.
>
> **READ FIRST, IN ORDER:**
>
> 1. `REVIEW-DECISIONS.md` — 23 architectural decisions. The contract.
>    Never redesign without explicit user approval.
> 2. `HANDOFF.md` — this doc.
> 3. `TODOS.md` — open follow-ups (TODO-3 + 2 deferred decisions; TODO-1 and TODO-9 just landed).
> 4. `RUNBOOK.md` — three smoke flows (in-process, real-uvicorn, live
>    operator stack) + the `persist_backtest_result` recipe.
> 5. `git log --oneline -15` for current state.
> 6. `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md` —
>    Phase 5 plan (5.0 done; 5.1 cutover + 5.2 deletion still pending).
>
> **Auto mode is OFF by default.** Use `AskUserQuestion` for taste calls.
> Ask before destructive or shared-state actions (force-push, mass deletes,
> schema changes affecting prod, anything cross-system).
>
> **Hard rules:**
>
> - Don't redesign anything in `REVIEW-DECISIONS.md` without explicit user
>   approval.
> - Don't add Polymarket order placement (decision 1C — read-only only).
> - Don't commit secrets.
> - Don't delete `sigil-frontend/` until Phase 5.2 (operator gate).
> - Don't modify existing alembic migrations; create new ones.
> - Don't modify existing columns / PKs in `src/sigil/models.py`; add new
>   tables instead.
>
> **First action:** `git log --oneline -8 && git status --short`, then read
> the docs above. Then ask the user what to work on (the open list is in
> "What's open" below).

---

## Current state

**Tests:** 374/374 passing (357 prior + 8 archive writer + 9 archive reader).
**Tags:** `wave-1-verified`, `wave-2-complete`, `phase-5-0-complete`.

```
TODO-9 close (next commit): replay reader + 9 tests + smoke
b91e2ca TODO-1: Kalshi orderbook archive writer (per-market per-day JSONL)
fcad6c9 refresh HANDOFF.md for next session
2740c4e real uvicorn smoke + RUNBOOK refresh
778aeca TODO-8: persist BacktestResult, light up F2's backtest_results widget
4073800 phase 5 framework polish: TODO-6 + TODO-7 + HANDOFF refresh
d460f43 phase 5.0: log framework follow-ups (TODO 6/7/8)
0a01046 phase 5 lane F2: 6 chart/data widgets + matplotlib SVG helpers
405907d phase 5 lane F3: jinja2 templates, CSS, mount points, dashboard.yaml
d2e0f80 phase 5 lane F1: widget framework + 6 read-only widgets
7bfdc48 close TODO-4 + TODO-5 from W2.4 smoke
```

### What's where

- **`src/sigil/dashboard/`** — Phase 5 framework. `widget.py`, `cache.py`
  (per-widget TTL), `loader.py`, `refresh.py`, `config.py`, `mount.py`
  (FastAPI mount).
- **`src/sigil/dashboard/widgets/`** — 12 widgets. F1: bankroll_summary,
  signal_queue, system_health_strip, recent_activity, market_list,
  open_positions. F2: model_brier, model_calibration, model_roi_curve,
  source_health_table, error_log, backtest_results. Plus `charts.py`
  matplotlib SVG helpers (theme passed per-call).
- **`src/sigil/dashboard/templates/`** + `static/` — Jinja2 base/page/404/
  error templates, dashboard.css (dark theme, 12-col grid, 768px mobile),
  relative-time.js (~30 LOC client JS).
- **`src/sigil/backtesting/persistence.py`** — `persist_backtest_result()`
  helper writing to the `backtest_results` table.
- **`dashboard.yaml`** at repo root — operator-editable widget config. 4
  pages: command-center (default), markets, models, health.
- **`src/sigil/ingestion/orderbook_archive.py`** — TODO-1 writer.
  Per-market per-day JSONL at
  `<ORDERBOOK_ARCHIVE_DIR>/kalshi/<external_id>/<YYYY-MM-DD>.jsonl`.
  LRU-bounded handle cache; gated by `config.ORDERBOOK_ARCHIVE_ENABLED`.
- **`src/sigil/backtesting/replay.py`** — TODO-9 reader.
  `iter_archive_ticks()` yields chronologically-sorted `PriceTick`s
  across a date range; pure I/O. `load_market_id_map(session)` is the
  DB-resolve helper.
- **`scripts/`** — `smoke_paper_flow.py` (paper trade end-to-end),
  `smoke_api.py` (TestClient endpoint hit), `smoke_uvicorn.py` (real port-
  bound uvicorn launcher with config override),
  `smoke_orderbook_archive.py` (TODO-1 writer end-to-end through
  `StreamProcessor._flush_once`),
  `smoke_archive_replay.py` (TODO-9 writer→reader→Backtester
  round-trip).
- **`alembic/versions/`** — two migrations: `0001` (initial) and
  `7e992ada302b` (add backtest_results table). Don't edit; chain new
  ones.
- **`sigil-frontend/`** — Next.js dashboard, still running. Don't touch
  until 5.2.

---

## What works

- **Wave 1**: ingest reliability, OMS with idempotency + Position writeback
  on fill, risk pre-trade checks, Kelly sizing with edge cases, decision
  engine, backtest engine + metrics + walk-forward + purged k-fold.
- **Wave 2**: settlement WS handler + hourly fallback (gated by
  `SETTLEMENT_WS_ENABLED`), Telegram severity routing, all 12 critical
  paths covered. APScheduler 5-min `BankrollSnapshot` job in `main.py`.
- **Phase 5.0**: server-rendered Python dashboard at `/`, `/page/{name}`,
  `/dashboard/static/*`. Per-widget TTL cache. Theme injected by loader.
  4 pages, 12 widgets, all render. Verified via TestClient AND real
  uvicorn (curl every route, 200/302/404 as expected).
- **TODO-8**: BacktestResult ORM table + alembic migration + persist
  helper. F2's `backtest_results` widget now reads via SQLAlchemy ORM
  with `OperationalError` fallback.
- **TODO-1**: Kalshi orderbook archive writer. Per-market per-day JSONL,
  raw depth preserved, gated by `ORDERBOOK_ARCHIVE_ENABLED` (default
  off).
- **TODO-9**: Replay reader. `iter_archive_ticks(archive_dir, ...,
  market_id_map=...)` → chronologically sorted `PriceTick`s for
  `Backtester(data_iter=...)`. End-to-end smoke: writer → reader →
  Backtester runs cleanly.

---

## What's open (priority order)

### Operator-gated (don't act unsupervised)

1. **Phase 5.1 cutover**: DNS / Tailscale routing changes so the Python
   dashboard becomes canonical. Operational; needs operator action.
2. **Phase 5.2 frontend deletion**: `git rm -r sigil-frontend/`. Only after
   the operator confirms parity by hitting both UIs side-by-side. Plan is
   in `polished-crafting-feigenbaum.md`.

### Code work, scope-clear

- **TODO-3**: Quarterly DB backup + restore drill. Operational
  (cron/CI/runbook) more than code. Document in `RUNBOOK.md` and add a
  reminder cron.

### Polish / nice-to-have

- HTMX configuration panel (Phase 5.1 territory; user gate-kept). Plan
  notes a `config_overrides` table; out of scope for 5.0.
- Backtest Lab UI (deferred per Phase 5 plan; CLI-only for now). Could
  surface as a `/page/backtest` with a form once HTMX is in.
- aiosqlite SQLite datetime adapter deprecation warning fires on a couple
  of tests (Python 3.12 cosmetic). Suppress or migrate to a custom
  adapter when convenient.
- The legacy `tests/test_*/` empty stub directories (`test_backtesting`,
  `test_execution`, etc.) sit at the top of `tests/`. They're harmless
  but they're noise — a future agent could `rmdir` them.

### Already done since the previous handoff

- TODO-1 (Kalshi orderbook archive writer) — landed `b91e2ca`.
- TODO-9 (replay reader → Backtester) — this slice.
- TODO-4 (OMS opens Position on fill) — landed `7bfdc48`.
- TODO-5 (settlement subscriber wired into `main.py`) — landed `7bfdc48`.
- TODO-6 (theme injection via WidgetBase) — landed `4073800`.
- TODO-7 (per-widget TTL in DashboardCache) — landed `4073800`.
- TODO-8 (persist BacktestResult) — landed `778aeca`.
- Real uvicorn smoke (was a verification gap) — landed `2740c4e`.

---

## Architectural notes that aren't obvious from the code

- **`Config` doesn't read env vars.** It's a plain pydantic `BaseModel`,
  not `BaseSettings`. Setting `DATABASE_URL=...` in the shell does
  *nothing*. Either edit `config.py` or use a wrapper that mutates
  `config` before importing the app. `scripts/smoke_uvicorn.py` is the
  reference pattern.
- **Worktree / Agent tool quirk on Windows**: dispatching `isolation:
  "worktree"` agents in parallel races on the parent dir mkdir. Run one
  at a time, OR run the second one without isolation and cherry-pick.
  F2 ended up with a stale base (`b9cdb61`) from a worktree — we cherry-
  picked its commit onto current `main`. Be wary; check the worktree
  branch's base ref before relying on it.
- **`_active_theme` is gone**: `charts.py` previously had a module-level
  global. TODO-6 removed it. Widgets carry `self.theme` (set by the
  loader); chart helpers accept `theme=` per call and default to
  `_DEFAULT_THEME`. If you find legacy `set_theme()` calls anywhere,
  they're stale.
- **`WidgetCache` is per-widget-type**: not a single global TTLCache.
  `set(key, value, ttl=...)` records the TTL on first write per
  widget_type. Use `invalidate_type(widget_type)` on YAML hot-reload to
  pick up a new TTL.
- **Dashboard lifespan is gated** by `DASHBOARD_ENABLED` (default
  `False`). Existing FastAPI tests don't pay the load cost of mounting
  the dashboard or starting the refresh scheduler. Production flips it
  on. Same pattern: `SETTLEMENT_WS_ENABLED` for the settlement
  subscriber.
- **OMS opens Positions on fill** in both paper and live modes (paper:
  in `_simulate_paper_fill`; live: at the FILLED branch of `submit()`).
  Buys grow positions and recompute avg_entry_price; sells reduce and
  realize PnL; sells with no open position log + no-op (poison-message
  safe). Settlement and reconciliation both rely on this.
- **`scripts/smoke_*.py` use repo-relative paths.** Don't use bash `/tmp`
  in DB URLs — Cygwin `/tmp` and Python `%TEMP%` resolve to different
  paths on Windows, leading to confusing "no such table" errors.
- **`backtest_results` is opt-in to write.** `Backtester.run()` returns
  an in-memory dataclass; nothing auto-persists. Operators call
  `persist_backtest_result(session, result, name=..., model_id=...)`
  after a run. The widget keeps an `OperationalError` fallback so deploys
  that haven't run the migration still render the empty state.
- **Existing `sigil_dev.db`** at the repo root is from before Wave 0's
  schema. Don't migrate it forward — start from a fresh DB.
- **Legacy `tests/test_*/` directories** are empty stubs. They don't
  collect any tests. Safe to ignore or remove.
- **OrderbookArchive runs as a side effect of `StreamProcessor._flush_once()`**.
  No separate scheduler. Date in filename means rotation is lazy and
  self-healing — the LRU evicts idle handles, opens a new file when the
  date rolls over. `KalshiDataSource.stream_prices()` now yields raw
  `bids`/`asks` ladder lists alongside scalar best-bid/ask; downstream
  consumers ignore the new keys, the archive captures them.
- **Replay reader is pure I/O.** `iter_archive_ticks()` does NOT touch
  the DB. The caller resolves `(platform, external_id) -> Market.id`
  via `load_market_id_map(session)` and passes the dict in. Markets
  found in the archive but missing from the DB log a warning and skip
  — that's what lets you replay last month's tape after a market is
  dropped. The reader maps `last_price` → `PriceTick.trade_price`;
  ladder fields (`bids`/`asks`) are reserved for a future depth-aware
  engine.

---

## How to bring the system up locally

See `RUNBOOK.md` for the canonical version. Quick reference:

```bash
# Setup
python -m venv .venv
source .venv/Scripts/activate
pip install -e '.[dev]'

# Path 1: in-process smoke
rm -f ./sigil_smoke.db
ALEMBIC_DATABASE_URL='sqlite:///./sigil_smoke.db' \
    .venv/Scripts/python.exe -m alembic upgrade head
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_paper_flow.py
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_api.py

# Path 2: real uvicorn smoke (background-launch, curl, kill)
SIGIL_SMOKE_DB='./sigil_smoke.db' SIGIL_SMOKE_PORT=8765 \
    .venv/Scripts/python.exe scripts/smoke_uvicorn.py &
sleep 3
curl -s http://127.0.0.1:8765/ -o /dev/null -w "%{http_code}\n"
curl -s http://127.0.0.1:8765/page/command-center | head
# kill the background uvicorn when done

# Full suite
.venv/Scripts/python.exe -m pytest

# Live dashboard (manual, edit config.py for DB URL since env doesn't flow)
DASHBOARD_ENABLED=true \
    .venv/Scripts/python.exe -m sigil.api.server
# then browse to http://127.0.0.1:8000/
```

---

## Files the next agent will most often touch

- `REVIEW-DECISIONS.md` — never modify; reference only.
- `src/sigil/models.py` — add new tables, never modify existing
  columns/PKs (alembic baseline is locked).
- `src/sigil/config.py` — add new params at the bottom; remember it's
  `BaseModel`, not `BaseSettings` (no env auto-load).
- `src/sigil/dashboard/widgets/` — net-new widgets land here.
- `src/sigil/dashboard/widget.py` + `cache.py` + `loader.py` — framework
  contract; touch with care.
- `src/sigil/backtesting/` — engine, metrics, persistence.
- `dashboard.yaml` — operator config; both code agents and humans edit.
- `tests/dashboard/` + `tests/backtesting/` + `tests/integration/` —
  colocated tests.
- `RUNBOOK.md` — keep current with new flags and procedures.
- `TODOS.md` — log new follow-ups; don't silently delete old ones.
- `HANDOFF.md` — this doc; refresh after meaningful slices land.

---

## Eng review decisions cheat sheet

Full text in `REVIEW-DECISIONS.md`:

- **1A** Vertical interface = data + features only
- **1B** No TimescaleDB, Redis, Dagster (Postgres + cachetools + APScheduler)
- **1C** Polymarket read-only, no order placement
- **1D** Reconciliation 3-match hysteresis (clears on exchange recovery)
- **1E** Client-supplied idempotency key
- **1F** sops + age for secrets
- **1G** Settlement WS + hourly fallback
- **1H** Tailscale-only API binding
- **2A** PRD §15 dir layout retired
- **2B** Composite PKs on time-series
- **2C** prediction_features child table (not JSONB)
- **2D** `MAX_MARKET_SLIPPAGE_CENTS` only for market/IOC orders
- **2E** `mode` (paper/live) column on Order + Position
- **2F** Drawdown gate: ≥20 settled total + ≥5 in window
- **3A** pytest+pytest-asyncio (Py); vitest (TS)
- **3B** 100% coverage on 12 critical paths, 70% overall
- **3C** Conservative backtest fill modeling
- **3D** LLM eval suite alongside first LLM signal
- **4A** Odds API 5-min freshness on $50/mo tier
- **4B** 5 missing indexes added upfront
- **4C** Pool sizes documented in config.py
- **4D** Per-widget TTL + 60s background refresh (Phase 5; replaced 5s SWR)
- **4E** No <5min backtest SLA — batch jobs
