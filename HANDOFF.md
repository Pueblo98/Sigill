# Sigil — Context Handoff for Next Session

**Date written:** 2026-04-30 (post Phase 5.0 + framework polish). Branch: `main`.
Working dir: `C:\Users\simon\OneDrive\Desktop\Gamblerr`. Platform: Windows 11,
bash shell, Python 3.12.

Paste the METAPROMPT section below into a fresh Claude Code session. Don't replay
the conversation — read the docs it references.

---

## METAPROMPT — copy this to the next agent

> You are continuing work on **Sigil**, a Python prediction-market trading
> platform (Kalshi + Polymarket-as-reference). Working dir
> `C:\Users\simon\OneDrive\Desktop\Gamblerr`. Python 3.12, bash on Windows.
>
> Wave 1, Wave 2, Phase 5.0 (read-only Python dashboard) are landed and tagged.
> The Next.js frontend at `sigil-frontend/` is still running for parity
> verification — **don't delete it**; that's Phase 5.2 work and needs operator
> sign-off.
>
> **READ FIRST, IN ORDER:**
>
> 1. `REVIEW-DECISIONS.md` — 23 architectural decisions. The contract.
> 2. `HANDOFF.md` — this doc.
> 3. `TODOS.md` — open follow-ups.
> 4. `RUNBOOK.md` — how to bring the system up + smoke procedures.
> 5. `git log --oneline -15` for current state.
> 6. `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md` — Phase 5
>    plan (5.0 done; 5.1 + 5.2 pending).
>
> **Auto mode is OFF by default.** Use `AskUserQuestion` for taste calls; ask
> before destructive or shared-state actions (force-push, mass deletes, schema
> changes affecting prod, anything cross-system).
>
> **Don't:** redesign anything in `REVIEW-DECISIONS.md` without explicit user
> approval. Don't add Polymarket order placement (1C). Don't commit secrets.
> Don't delete `sigil-frontend/` until 5.2.

---

## Current state

**Tests:** 350/350 passing under `.venv/Scripts/python.exe -m pytest`.
**Tags:** `wave-1-verified`, `wave-2-complete`, `phase-5-0-complete`.

```
d460f43 phase 5.0: log framework follow-ups (TODO 6/7/8)
0a01046 phase 5 lane F2: 6 chart/data widgets + matplotlib SVG helpers
405907d phase 5 lane F3: jinja2 templates, CSS, mount points, dashboard.yaml
d2e0f80 phase 5 lane F1: widget framework + 6 read-only widgets
7bfdc48 close TODO-4 + TODO-5 from W2.4 smoke
dc0f919 wave 2: reconcile + verify + smoke + critical-path tests
8040a4f wave 1 verify: clear reconciliation freeze on exchange recovery
```

Plus `phase 5 framework polish` commit (TODO-6 + TODO-7) on top.

### What's where

- **`src/sigil/dashboard/`** — Phase 5 framework. `widget.py`,
  `cache.py` (per-widget TTL), `loader.py`, `refresh.py`, `config.py`,
  `mount.py` (FastAPI mount).
- **`src/sigil/dashboard/widgets/`** — 12 widgets (F1: bankroll_summary,
  signal_queue, system_health_strip, recent_activity, market_list,
  open_positions; F2: model_brier, model_calibration, model_roi_curve,
  source_health_table, error_log, backtest_results) + `charts.py`
  matplotlib SVG helpers.
- **`src/sigil/dashboard/templates/`** + `static/` — Jinja2 templates,
  dashboard.css (dark theme), relative-time.js (~30 LOC client JS).
- **`dashboard.yaml`** at repo root — operator-editable widget config. 4
  pages: command-center (default), markets, models, health.
- **`scripts/smoke_paper_flow.py`** + `smoke_api.py` — in-process smoke tests.
- **`sigil-frontend/`** — Next.js dashboard, still running. Don't touch
  until 5.2.

---

## What works

- Wave 1: ingest, OMS (with Position writeback on fill), risk, Kelly sizing,
  decision engine, backtest engine + metrics.
- Wave 2: settlement WS handler + hourly fallback (gated by
  `SETTLEMENT_WS_ENABLED`), Telegram severity routing, all critical-path
  tests covered.
- Phase 5.0: server-rendered Python dashboard at `/`, `/page/{name}`,
  `/dashboard/static/*`. Per-widget TTL cache. Theme injected by loader.
  4 pages render (command-center, markets, models, health).
- All four `BankrollSnapshot` paths (periodic, on-trade, on-settlement,
  manual) write monotonic timestamps even on Windows.

---

## What's open (priority order)

### Operator-gated (don't act unsupervised)

1. **Phase 5.1 cutover**: DNS / Tailscale routing changes so Python
   dashboard is canonical. Operational; needs operator action.
2. **Phase 5.2 frontend deletion**: `git rm -r sigil-frontend/`. Only
   after operator confirms parity by hitting both UIs side-by-side.

### Code work, scope-clear

- **TODO-1**: Archive Kalshi order book snapshots to disk for replay.
  Promoted to in-scope by the eng review but never started. Disjoint
  from dashboard work.
- **TODO-3**: Quarterly DB backup + restore drill. Operational
  (cron/CI/runbook) more than code.
- **TODO-8**: Persist `BacktestResult` so the F2 `backtest_results`
  widget shows data. Schema change: add `BacktestResult` ORM table +
  alembic migration + `persist_backtest_result(session, result)` helper
  in `src/sigil/backtesting/`. Widget already falls back gracefully on
  `OperationalError ("no such table")`.

### Polish / nice-to-have

- HTMX configuration panel (Phase 5.1 territory; user gate-kept).
- Backtest Lab UI (deferred per Phase 5 plan; CLI-only for now).
- The aiosqlite SQLite datetime adapter deprecation warning fires on a
  couple of tests — Python 3.12 cosmetic. Suppress or fix when
  convenient.

### Verification gap (small, ~10 min)

- Run a real `uvicorn` smoke (background-launch + curl every page +
  static asset). Phase 5 was verified via FastAPI TestClient
  (in-process). `RUNBOOK.md` has the steps; never executed live.

---

## Architectural notes that aren't obvious from the code

- **Auto mode**: the user runs interactive most of the time. Use
  `AskUserQuestion` for taste calls; don't auto-pick the "first option."
- **Worktree / Agent tool quirk on Windows**: dispatching `isolation:
  "worktree"` agents in parallel races on the parent dir mkdir. Run
  one agent at a time, OR run the second one without isolation and
  cherry-pick. F2 ran in worktree with stale base (`b9cdb61`) — the
  worktree was created from the wrong ref; we cherry-picked its commit
  onto `main`. Be wary.
- **`_active_theme` is gone**: `charts.py` previously had a module-level
  `_active_theme` and `set_theme()`. TODO-6 removed both. Widgets carry
  `self.theme` (set by the loader); chart helpers accept `theme=` per
  call and default to `_DEFAULT_THEME`. If you see legacy `set_theme`
  calls anywhere, they're stale.
- **`WidgetCache` is per-widget-type**: not a single global TTLCache.
  `set(key, value, ttl=...)` records the TTL on first write per
  widget_type. Use `invalidate_type(widget_type)` on YAML hot-reload to
  pick up a new TTL.
- **Dashboard lifespan is gated** by `DASHBOARD_ENABLED` (default
  False). Existing FastAPI tests don't pay the load cost; production
  flips it on.
- **Settlement subscriber is gated** by `SETTLEMENT_WS_ENABLED` (default
  False). Paper-only laptops without Kalshi creds skip it.
- **OMS opens Positions on fill** in both paper and live modes.
  Settlement reconciliation expects Positions to exist.
- **`scripts/smoke_*.py`** use repo-relative `./sigil_smoke.db`. Don't
  use bash `/tmp` — Cygwin `/tmp` and Python `%TEMP%` resolve to
  different paths on Windows.
- **F2's `backtest_results` widget** queries a hypothetical
  `backtest_results` table via raw SQL and treats `OperationalError`
  as the empty state. Lights up automatically when TODO-8 lands the
  table.
- **Existing `sigil_dev.db`** is from before Wave 0's schema changes;
  don't migrate it forward.

---

## How to bring the system up locally

See `RUNBOOK.md`. TL;DR:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e '.[dev]'

# In-process smoke (no external services)
rm -f ./sigil_smoke.db
ALEMBIC_DATABASE_URL='sqlite:///./sigil_smoke.db' \
    .venv/Scripts/python.exe -m alembic upgrade head
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_paper_flow.py
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_api.py

# Full suite
.venv/Scripts/python.exe -m pytest

# Live dashboard (manual, not yet automated in tests)
DATABASE_URL='sqlite+aiosqlite:///./sigil_dev.db' \
DASHBOARD_ENABLED=true \
    .venv/Scripts/python.exe -m sigil.api.server
# then browse to http://127.0.0.1:8000/
```

---

## Files the next agent will most often touch

- `REVIEW-DECISIONS.md` — never modify; reference only.
- `src/sigil/models.py` — add new tables, never modify existing
  columns/PKs (alembic baseline is locked).
- `src/sigil/config.py` — add new params at the bottom.
- `src/sigil/dashboard/widgets/` — net-new widgets land here.
- `src/sigil/dashboard/widget.py` + `cache.py` + `loader.py` — framework
  contract; touch with care.
- `dashboard.yaml` — operator config; both code agents and humans edit.
- `tests/dashboard/` — colocated tests for the dashboard.
- `RUNBOOK.md` — keep current with new flags and procedures.
- `TODOS.md` — log new follow-ups; don't silently delete old ones.

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
