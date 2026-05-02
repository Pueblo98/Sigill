# Sigil — Context Handoff for Next Session

**Date written:** 2026-05-02 (post live-ingestion + sparkline fix —
`ODDSPIPE_POLL_SECONDS` 60→300 to match decision 4A + cross_platform
spreads cache=5m, market-detail sparkline now uses bid/ask mid instead
of stale `last_traded_price`, real Kalshi/Polymarket markets render
actual SVG charts instead of falling back to "Price stable" text).
Earlier same day: markets-sub-tabs (Cross-platform spreads + Archived
collapsed into the Markets page as in-page tabs per
sigil-frontend/DESIGN.md "vertical IA" rule); morning slice
backend-dashboard-feature-parity — standalone `/markets`, `/execution`,
`/models` (card grid), `/models/{id}` (per-model detail), F2 widgets
wired into the Health page. Branch: `main`. Working dir
`C:\Users\simon\OneDrive\Desktop\Gamblerr`. Platform: Windows 11, bash
shell, Python 3.12.

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
> critical-path coverage), Phase 5.0 (server-rendered Python dashboard at
> `/` with per-widget TTL cache + 60s background refresh), markets explorer
> v3 (standalone `/markets` route with search/filter/paginate + Market
> description/archived columns), backend dashboard feature parity
> (2026-05-02 morning): standalone `/execution` (orders feed), `/models`
> (card grid mirroring the Next.js mechanic), `/models/{model_id}`
> (per-model detail with equity curve + recent trades + recent
> predictions), plus the F2 source health + error log widgets wired into
> the Health page. **Markets sub-tabs (2026-05-02 evening)**: per the
> `sigil-frontend/DESIGN.md` "vertical IA" rule, Cross-platform spreads
> and Archived markets moved into the Markets page as in-page tabs
> (`/markets?view=spreads`, `/markets?view=archived`). Topbar entry
> "Cross-platform spreads" removed; `/page/spreads` still renders
> directly for old bookmarks. The Next.js frontend at `sigil-frontend/`
> is **still running** for parity verification — **don't delete it**
> until the operator has used the backend for a few sessions and signs
> off (TODO-11).
>
> **Test bar:** 181/181 dashboard tests + 381 across the broader suite
> (excluding the slow `tests/decision/` and `tests/ingestion/` integration
> suites) passing under `.venv/Scripts/python.exe -m pytest`. Don't let
> regressions land unnoticed.
>
> **READ FIRST, IN ORDER:**
>
> 1. `REVIEW-DECISIONS.md` — 23 architectural decisions. The contract.
>    Never redesign without explicit user approval.
> 2. `HANDOFF.md` — this doc.
> 3. `TODOS.md` — open follow-ups (TODO-10 first-drill operator-gate,
>    TODO-11 frontend deletion, TODO-12 analytical-widgets re-wire,
>    plus 2 deferred decisions; TODO-1, TODO-3, TODO-9 already landed).
> 4. `RUNBOOK.md` — three smoke flows (in-process, real-uvicorn, live
>    operator stack) + the `persist_backtest_result` recipe.
> 5. `git log --oneline -15` for current state.
> 6. `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md` —
>    Phase 5 plan (5.0 done; 5.1 cutover + 5.2 deletion still pending).
> 7. `C:\Users\simon\.claude\plans\ok-so-weve-been-bright-forest.md` —
>    backend dashboard feature-parity plan (2026-05-02), executed.
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

**Tests:** 183 dashboard tests pass; 381 across the broader suite
(excluding `tests/decision/` + `tests/ingestion/`).
**Tags:** `wave-1-verified`, `wave-2-complete`, `phase-5-0-complete`.

```
TODO-3 close (next commit): backup-restore runbook + scripts
30e919f TODO-9: replay reader for the orderbook archive
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
- **`dashboard.yaml`** at repo root — operator-editable widget config. 3
  YAML-driven widget pages remain: command-center (default), spreads,
  health. **The `spreads` page is no longer surfaced in the topbar**
  (markets-sub-tabs slice, 2026-05-02 evening) — it's only kept so the
  `cross_platform_spreads` widget continues to instantiate + refresh
  on the orchestrator's 60s tick. Rendering happens on the Markets
  page under `?view=spreads`, which looks up the widget instance from
  `state.widgets` and renders its cached HTML inline. `/page/spreads`
  still works for old bookmarks. The retired YAML pages — `markets`
  (markets explorer v3) and `models` (backend dashboard feature
  parity) — are served by standalone Jinja routes that mount.py
  registers directly. See `src/sigil/dashboard/views/{markets_list,
  models_list,model_detail,execution_log}.py` + the matching
  `templates/*.html`. The four standalone routes (`/markets`,
  `/execution`, `/models`, `/models/{model_id}`) sit in
  `mount._register_routes`; the topbar builds via `_nav_pages` which
  drops YAML pages whose names collide with a standalone route or
  with an in-page sub-tab (currently `markets`, `models`, `spreads`)
  and inserts the standalone links at fixed positions.
- **F2 widgets are now wired into the Health page** (2026-05-02).
  `source_health_table` + `error_log` joined `system_health_strip` +
  `recent_activity` so Data Health renders per-source latency/errors +
  recent error feed instead of just headlines.
- **F2 model widgets (`model_brier`, `model_calibration`,
  `model_roi_curve`) stay registered in code but are NOT currently
  wired into any page.** Per-model performance lives on
  `/models/{model_id}` instead (equity curve + recent trades + recent
  predictions, served from `views/model_detail.py` calling
  `sigil.api.model_performance.model_detail`). If you build a future
  comparative-analytics page, re-add them to `dashboard.yaml`. Tracked
  as TODO-12.
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
  round-trip),
  `backup_db.sh` (cron-driven daily Postgres backup to S3 + age),
  `restore_db.sh` (quarterly-drill restore from S3).
- **`runbooks/backup-restore.md`** — TODO-3 canonical procedure: daily
  backup, quarterly drill checklist, drill log table, age-key reuse
  from decision 1F.
- **`alembic/versions/`** — three migrations: `0001` (initial),
  `7e992ada302b` (backtest_results), and `a4b1c2d3e4f5` (description +
  archived columns on markets). Don't edit; chain new ones.
- **`sigil-frontend/`** — Next.js dashboard, still running on port 3000
  for parity verification. The Python dashboard at port 8003 now has
  full feature parity (or better) for every page that ships data from
  the backend API. Don't touch the frontend until TODO-11
  (operator-gated deletion).

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
  3 YAML widget pages (command-center, spreads, health) + 4 standalone
  routes (`/markets`, `/execution`, `/models`, `/models/{id}`).
  Verified via TestClient AND real uvicorn (curl every route, 200/302/
  404 as expected).
- **Backend dashboard feature parity (2026-05-02)**: `/execution`
  (filterable orders feed: platform/mode/status filters + 50-per-page
  pagination, mode chips for paper/live, market title links into
  `/market/{external_id}`); `/models` (card grid — one card per
  registered model with display_name + version + status dot
  (live/idle/disabled) + tags + 4-stat grid + last-trade relative time
  + 24h prediction count, click-through to detail); `/models/{model_id}`
  (per-model deep dive — perf stats grid, equity curve via
  `render_roi_curve_svg`, recent trades + predictions tables); F2
  widgets `source_health_table` + `error_log` wired into the Health
  page. Topbar order: Command Center · Markets · Execution ·
  Cross-platform spreads · Models · Data Health.
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
- **TODO-3**: DB backup + restore procedure. `runbooks/backup-restore.md`
  + `scripts/backup_db.sh` + `scripts/restore_db.sh`. Pre-built for
  Postgres + S3-compatible storage + age encryption (decision 1F key
  reuse). Daily cron, quarterly drill, drill log inline. WAL/PITR
  explicitly out of scope for v1.

---

## What's open (priority order)

### Operator-gated (don't act unsupervised)

1. **TODO-10: First backup + restore drill.** The procedure +
   scripts are ready (TODO-3 ship). Needs S3 bucket + cron/timer
   install + 30-min drill on a throwaway Postgres host.
   `runbooks/backup-restore.md` is the doc.
2. **Phase 5.1 cutover**: DNS / Tailscale routing changes so the Python
   dashboard becomes canonical. Operational; needs operator action.
3. **TODO-11 / Phase 5.2 frontend deletion**: `git rm -r sigil-frontend/`.
   Backend feature parity landed 2026-05-02 — the Python dashboard now
   has every page the frontend had (and `/markets` + `/execution` go
   beyond, with server-side filtering + pagination). Operator needs to
   use the backend for a few sessions before sign-off. Plan in
   `polished-crafting-feigenbaum.md`.

### Code work, scope-clear

- **TODO-12: Re-wire analytical model widgets.** `model_brier`,
  `model_calibration`, `model_roi_curve` are registered in
  `WIDGET_REGISTRY` but no longer referenced by `dashboard.yaml`
  (the Models page is now a card grid; per-model analytics live on
  `/models/{id}`). If/when a comparative cross-model analytics page is
  needed, add a YAML page that references these widgets — they're
  ready to render. No code change required to the widgets themselves.

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

- **Live ingestion + sparkline fix** (this slice, 2026-05-02 late
  evening). Two related fixes so the dashboard *visibly moves*:
  - `ODDSPIPE_POLL_SECONDS` default in `src/sigil/config.py` flipped
    from `60` back to `300`. Aligns with decision 4A (5-min freshness
    on the $50/mo tier) and the `cross_platform_spreads` widget
    `cache=5m` in `dashboard.yaml`. The 60s default had been tripping
    OddsPipe 429s when the ingestion process restarted; 300s burns
    ~12 calls/hour, well under quota.
  - Market-detail sparkline (`src/sigil/dashboard/views/market_detail.py`)
    now prefers the bid/ask mid over `MarketPrice.last_price` for the
    7-day series. OddsPipe REST returns a stale `last_traded_price`
    on low-volume prediction markets even while the bid/ask is moving
    tick-to-tick — under the old logic those markets degraded into a
    "Price stable at X" text note. New logic gives real markets like
    `KXLAYOFFSYINFO-26-494000` an actual SVG chart. Genuinely flat
    markets still get a (now-correctly-labelled) "Mid stable" note.
  - Operator visibility: ingestion is a separate `start_ingestion.py`
    foreground process (NOT started by `python -m sigil.api.server`).
    See RUNBOOK.md path 3c. Symptom of an outage: `MarketPrice.time`
    max getting old + cross_platform_spreads widget falling to "no
    high-confidence spreads" empty state.
- **Markets sub-tabs** (prior slice, 2026-05-02 evening). Per the
  `sigil-frontend/DESIGN.md` "vertical IA" rule, two former top-level
  surfaces collapsed into the Markets page as in-page tabs:
  - `?view=all` (default) — currently-running markets.
  - `?view=spreads` — renders the cached `cross_platform_spreads`
    widget inline. The route looks up the widget instance from
    `state.widgets` and pulls cached HTML; the widget keeps refreshing
    via the YAML `spreads` page (which stays in `dashboard.yaml` but
    is dropped from `_nav_pages`).
  - `?view=archived` — non-running markets (status≠open OR
    archived=True). Replaces the old `?archived=1` checkbox; legacy
    URLs still work because the route handler translates them.
  - Tab strip at the top of the Markets page (`.markets-list__tabs` /
    `.markets-list__tab` / `.markets-list__tab--active`) — slim
    underlined-on-active labels per the DESIGN.md spec.
  - Topbar lost the "Cross-platform spreads" entry; new order:
    Command Center · Markets · Execution · Models · Data Health.
  - `views/markets_list.py::build_context` signature changed:
    `archived: Optional[str]` was replaced with `view: Optional[str]`
    (legal values: `all` (default), `archived`, `spreads`). The
    `MarketsListContext` dataclass replaced `archived: bool` with
    `view: str`. Tests updated to match.
- **Backend dashboard feature parity** (prior slice, 2026-05-02 morning).
  Operator
  prefers the Python dashboard's dark/monospace look over the Next.js
  frontend, so the missing pages migrated. Three new standalone routes
  in `mount.py` + four new view modules + four new templates:
  - `/execution` (`views/execution_log.py` +
    `templates/execution_log.html`) — filterable + paginated orders
    feed. Filters: platform, mode (paper/live), status. Mode chip styled
    via new `.markets-list__mode-chip` rules in `dashboard.css` (live =
    red border, paper = muted). Market title links into
    `/market/{external_id}`.
  - `/models` (`views/models_list.py` +
    `templates/models_list.html`) — 3-column card grid, one card per
    `ModelDef` in `sigil.models_registry`. Calls
    `sigil.api.model_performance.all_model_summaries` for the metrics.
    Status dot mechanic: enabled + ≥1 prediction in 24h → "live";
    enabled + idle → "idle"; disabled → "disabled". Each card is an
    `<a>` linking to `/models/{model_id}`. Card grid CSS lives in
    `dashboard.css` under `.models-list*`.
  - `/models/{model_id}` (`views/model_detail.py` +
    `templates/model_detail.html`) — per-model deep dive. Reuses
    `mp.model_detail()` for the data + `render_roi_curve_svg` for the
    equity SVG. Sections: header (display name + version + status +
    description + tags), 8-stat performance grid, equity curve, recent
    trades table (linkable into `/market/{external_id}`), recent
    predictions table.
  - F2 widgets `source_health_table` + `error_log` wired into the
    Health page in `dashboard.yaml`. The model F2 widgets
    (`model_brier`, `model_calibration`, `model_roi_curve`) stay
    registered but unwired — see TODO-12.
  - `_nav_pages` in `mount.py` learned to drop YAML pages named
    `models` (alongside `markets`) and to insert standalone links for
    `/markets` (pos 1), `/execution` (pos 2), and `/models` (pos 4).
    Topbar order: Command Center · Markets · Execution ·
    Cross-platform spreads · Models · Data Health.
  - Test coverage: `tests/dashboard/test_execution_log_route.py`
    (9 tests), `test_model_detail_route.py` (4 tests),
    `test_models_list_route.py` (6 tests). Updated
    `test_dashboard_yaml.py` (widget count assertion 8 → 9, page list
    `[command-center, spreads, health]`) and `test_render.py`
    (`/page/models` is now 404; nav contains `/execution` + `/models`).
- **Markets explorer v3** (prior slice). Schema gained
  `Market.description` + `Market.archived` via migration
  `a4b1c2d3e4f5_add_market_description_archived`. New standalone
  `/markets` route (search + platform/category/status filter +
  archived toggle + 50/page pagination); the old YAML widget-driven
  `/page/markets` is gone, the topbar entry now points at `/markets`.
  Ingestion captures description from Polymarket gamma + mirrors
  `archived`; Kalshi categories now come from a hardcoded ticker-prefix
  map (`_KALSHI_PREFIX_CATEGORY` in `src/sigil/ingestion/kalshi.py`)
  until /events/{ticker} auth lands. Detail page renders the
  description block + an archived badge. Backfill via
  `scripts/enrich_markets.py` filled 91 polymarket descriptions; all
  110 kalshi rows now bucket into sports/economics/politics — DB
  baseline went from 146/258 'general' to 146 (polymarket only,
  gamma's `category` is unreliable).
- **Scraper research finding** (logged so the next agent doesn't
  re-research it): no new dependency needed. Polymarket gamma already
  exposes `description` + `archived` reliably; Kalshi's per-market
  fields (rules_primary, real category) are gated behind RSA-PSS
  auth we don't have. `pykalshi` (ArshKA/pykalshi) and `kalshi-python`
  both blocked on the same auth gap. `py-clob-client` is order-placement
  oriented, not a market-data improvement. Selenium/Playwright stays
  deferred — only consider when an API truly doesn't expose the field.
- TODO-1 (Kalshi orderbook archive writer) — landed `b91e2ca`.
- TODO-9 (replay reader → Backtester) — landed `30e919f`.
- TODO-3 (backup + restore procedure + scripts) — this slice.
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
