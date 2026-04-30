# Sigil — Context Handoff for Next Session

**Date written:** 2026-04-30. Branch: `main`. Working dir: `C:\Users\simon\OneDrive\Desktop\Gamblerr`.

Paste the section below ("METAPROMPT") into a fresh Claude Code session. The next agent should read this file plus the docs it references, NOT replay the conversation.

---

## METAPROMPT — copy this to the next agent

> You are continuing work on **Sigil**, a Python prediction-market trading platform (Kalshi + Polymarket-as-reference). The working directory is `C:\Users\simon\OneDrive\Desktop\Gamblerr`. Platform: Windows 11, bash shell, Python 3.12.
>
> A previous session ran a structured engineering review (`/plan-eng-review`) that produced 23 architectural decisions, then dispatched 4 parallel implementation agents (Wave 1 / Lanes A-D) that landed substantial code. Wave 1 is complete on `main` but **unverified by test execution** (the agents couldn't run pytest in their sandboxes; some authored tests they didn't run; one agent hit Anthropic rate limits before committing and its work was committed by the orchestrator).
>
> Your job is **Wave 2: reconcile + verify + smoke-test + critical-path tests**. After Wave 2 lands, **Phase 5** is a planned glance-inspired Python dashboard that replaces the existing Next.js frontend. The detailed Phase 5 plan is at `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md`.
>
> **READ THESE FIRST, IN ORDER:**
>
> 1. `REVIEW-DECISIONS.md` — the 23 decisions from the eng review. This is the contract. Comply with it.
> 2. `HANDOFF.md` — this document. Background context + Wave 2 task list + open issues.
> 3. `TODOS.md` — captured TODOs from the eng review.
> 4. `git log --oneline -10` to see what's landed.
> 5. The Phase 5 plan at `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md` (only relevant after Wave 2 completes).
>
> **DON'T:** redesign anything in `REVIEW-DECISIONS.md` without explicit user approval. Don't start Phase 5 until Wave 2's test suite passes. Don't commit secrets. Don't add Polymarket order-placement code (decision 1C: read-only only).
>
> **Auto mode is OFF** (the user wants interactive control). Ask before destructive or shared-state actions. Use AskUserQuestion for taste calls.
>
> First action: run `git log --oneline -8` and `git status --short`, then read `REVIEW-DECISIONS.md` and the Wave 2 task list below.

---

## Project state — what landed in Wave 1

Six commits on `main`, in order:

```
a8ff4ec lane A: ingest reliability + OMS + risk + sizing + alembic (uncommitted by agent)
b9cdb61 lane C: API tailscale binding + secrets loader + frontend rewire to real API
6b529d3 lane D: backtest engine + conservative fill model + metrics
9ad09ff lane B: decision engine + drawdown circuit breaker with min-trade gate
0fc5d35 wave 0: lock schema + decisions doc for parallel implementation
aa7df02 wip: capture in-progress implementation prior to eng review
1b3d1f3 first commit
```

### What each lane delivered

**Lane A (a8ff4ec)** — agent hit the rate limit before committing; orchestrator committed the work. **Tests authored but unverified.**
- `alembic/` initial migration auto-generated from `models.py`
- `src/sigil/db.py` rewritten: postgres-with-sqlite-fallback retained, `get_session` async context manager, `create_all` removed
- `src/sigil/execution/oms.py` (314 LOC) — order state machine, idempotent retries, paper-mode short-circuit
- `src/sigil/execution/risk.py` (268 LOC) — 7 pre-trade checks, fail-closed
- `src/sigil/execution/sizing.py` (95 LOC) — Kelly with edge cases
- `src/sigil/execution/reconciliation.py` (203 LOC) — 3-match hysteresis tracker
- `src/sigil/execution/kalshi.py` extended — client_order_id pass-through
- `src/sigil/ingestion/runner.py` rewritten — FK-type bug fixed (UUID lookup by external_id)
- `src/sigil/ingestion/settlement.py` (256 LOC) — WS settlement subscriber + hourly fallback
- `tests/conftest.py` + `tests/execution/{test_oms,test_risk,test_sizing,test_reconciliation}.py` + `tests/ingestion/{test_runner,test_settlement}.py`

**Lane B (9ad09ff)** — agent self-reviewed but couldn't execute tests. **Unverified.**
- `src/sigil/decision/engine.py` — `compute_edge`, `should_trade`, `DecisionEngine` (OMS injected via callable)
- `src/sigil/decision/drawdown.py` — `DrawdownState`, `current_state`, `position_size_multiplier`, with min-trade gate (decision 2F)
- `src/sigil/decision/__init__.py` updated; `src/sigil/decision/arb.py` deleted (superseded)
- `src/sigil/decision/stat_arb.py` got 1C display-only docstring (logic untouched)
- `tests/decision/{test_engine,test_drawdown,test_stat_arb_smoke}.py` + `tests/decision/conftest.py`

**Lane C (b9cdb61)** — **VERIFIED**: pytest 23 passed, vitest 12 passed, tsc clean.
- `src/sigil/api/server.py` — bind from `config.API_BIND_HOST/PORT`, lifespan handler runs `init_db` + `load_secrets`, exposure banner
- `src/sigil/api/routes.py` — fixed FK-type bug, real `/api/portfolio` with `state='no_data'`, new endpoints `/api/positions`, `/api/orders`, `/api/predictions`, `/api/health`, `/api/arbitrage` calling `StatArbScanner.scan()` with 60s in-process TTL cache
- `src/sigil/secrets.py` — sops/age loader, graceful no-op when sops binary missing
- `sigil-frontend/lib/api/client.ts` — SWR `useApi<T>()` 5000ms refresh
- `sigil-frontend/lib/types/api.ts` — full type set
- All 7 frontend pages rewired to real API with empty/loading/error states
- `vitest.config.ts` + `vitest.setup.ts`
- Tests: `tests/api/{test_routes,test_server,test_secrets}.py` + `sigil-frontend/{lib/api/client.test.ts,app/page.test.tsx}`

**Lane D (6b529d3)** — **VERIFIED**: 48/48 pytest passed (22 critical-marked).
- `src/sigil/backtesting/engine.py` — event-driven `Backtester`, `Strategy` Protocol, `Trade`, `Signal`
- `src/sigil/backtesting/execution_model.py` — `ConservativeFillModel` per decision 3C
- `src/sigil/backtesting/portfolio.py` — Portfolio with mark-to-market, settle
- `src/sigil/backtesting/metrics.py` — Brier, log loss, calibration, ROI, Sharpe, max drawdown, win rate, avg edge captured
- `src/sigil/backtesting/walkforward.py` — `WalkForwardSplitter` + `PurgedKFold`
- Tests: `tests/backtesting/{test_metrics,test_execution_model,test_engine,test_walkforward}.py` (hand-computed examples for every metric)

---

## Wave 2 task list — your job

### W2.1 — Verify all unverified Wave 1 code actually runs

Lanes A and B were never executed. The orchestrator committed Lane A's work without verification. **First action: install deps and run the full suite.**

```bash
python -m venv .venv
source .venv/Scripts/activate     # Windows bash
pip install -e '.[dev]'
pip install -e '.[backtest]'      # if backtest tests need lightgbm
pytest -v
```

Expected outcome: many tests pass. Some likely fail. Capture all failures into a list.

### W2.2 — Reconcile inter-lane contract issues flagged by agents

**(a) Lane B's `DecisionEngine` injects OMS via a callable.** Lane A's `oms.py` exposes a real OMS object. Reconcile: write an adapter in `src/sigil/decision/engine.py` (or a new `src/sigil/decision/wiring.py`) that converts Lane A's `OMS.submit_order(...)` into the callable shape Lane B's `DecisionEngine.evaluate(..., oms_submit=...)` expects. Verify with an integration test: a `Prediction` with positive edge → `DecisionEngine.evaluate()` → real `Order` row written.

**(b) Lane B's drawdown reads `BankrollSnapshot` but no module writes them yet.** Add a writer. Two options — pick one:
- **Periodic snapshot job**: APScheduler job in `src/sigil/main.py` that snapshots equity every N minutes (e.g., 5 min). Cleanest.
- **Snapshot-on-trade**: write a snapshot after every settled position. More granular, more rows. Probably not needed.
Recommend: periodic 5-min job.

**(c) Lane D's tests bypass the parent `tests/conftest.py` with `--noconftest`.** The conftest imports `pytest_asyncio` + `sigil.execution.reconciliation` + `sigil.ingestion.runner` at module level. If any of those fail to import, all tests fail. Make conftest imports lazy (move into fixtures) so unrelated test directories don't fail to collect.

**(d) Lane C's `_arb_cache` is module-level**. After server restart, the 60s cache is cold on first request — fine, but document.

**(e) Lane C's `/api/arbitrage` test patches `sigil.decision.stat_arb.StatArbScanner`.** If Lane B ever changes the import path (it shouldn't per 1C), the test breaks. Defensive — add a contract test that imports from the public API.

**(f) Lane D's `Portfolio.settle` zeroes positions but doesn't write back to the `Position` ORM.** Add the writeback or document it as a backtest-only Portfolio (no DB writes during backtests). Recommend: backtest portfolio is in-memory only; live positions are written by `oms.py`.

**(g) Lane D's `all_metrics(result, predictions=...)` expects objects with `predicted_prob` and `outcome` attributes. Lane B's real `Prediction` ORM has `predicted_prob` but the outcome is on `Market.settlement_value`. Add an adapter in `src/sigil/backtesting/metrics.py` or in a new `wiring.py`.

### W2.3 — Write the 4 critical-path tests Wave 1 didn't cover

The eng review identified **12 critical paths** (REVIEW-DECISIONS.md 3B). Wave 1 covered 8. Missing:
1. **Order idempotency under retry** — test that `oms.submit()` with a network timeout retried 3 times produces exactly one Kalshi order (mock the HTTP client; verify `client_order_id` is the same across retries; verify exchange-side dedup in the mock).
2. **Settlement WS handler end-to-end** — test that a Kalshi `status: settled` WS event closes the matching `Position` row, writes `realized_pnl`, and updates `BankrollSnapshot`.
3. **Feature versioning detection** — when a feature's `version` bumps, predictions made with old version stay queryable; new predictions write with new version.
4. **Telegram alert routing** — severity → channel mapping. Critical/warning/info each go to the right destination.

Add `tests/integration/test_idempotency.py`, `tests/integration/test_settlement_e2e.py`, `tests/features/test_versioning.py`, `tests/alerts/test_telegram_routing.py`.

### W2.4 — End-to-end smoke test

Once W2.1-W2.3 land:

```bash
# 1. start postgres locally OR use sqlite fallback
# 2. run alembic upgrade head
# 3. start the API: uvicorn sigil.api.server:app
# 4. start the ingestion runner: python -m sigil.ingestion.runner
# 5. browser to http://127.0.0.1:3000 (Next.js dev server) — verify dashboard loads with real data
# 6. browser to http://127.0.0.1:8000/api/markets — verify JSON
# 7. submit a paper-mode prediction via CLI / Python REPL — verify order, position, eventual settlement
```

Document the smoke procedure in a new `RUNBOOK.md`.

### W2.5 — Commit + tag

When green: `git tag wave-1-verified` and `git tag wave-2-complete`. Update `TODOS.md` with anything that came up.

---

## Open architectural questions to resolve before Phase 5

1. **Where do `BankrollSnapshot` rows actually come from?** Decided in W2.2(b): periodic 5-min APScheduler job.
2. **Backtest Portfolio vs live Position** — same SQLAlchemy model or different abstractions? Decided in W2.2(f): backtest Portfolio is in-memory only.
3. **Telegram bot framework** — `python-telegram-bot` is in `pyproject.toml` deps but `src/sigil/alerts/telegram.py` may not actually use it. Verify in W2.3.
4. **Migration strategy** — Lane A's `alembic/versions/20260430_0000_0001_initial_schema.py` is the only migration. As schema changes during Wave 2, generate new migrations rather than editing the initial one.
5. **Frontend deletion timing** — sigil-frontend is the operator UI right now (Wave 1 wired it to real API). Don't delete it until Phase 5.0 ships and operator confirms parity.

---

## Phase 5 (after Wave 2)

Plan: `C:\Users\simon\.claude\plans\polished-crafting-feigenbaum.md`. Glance-inspired Python dashboard replaces sigil-frontend/. YAML widget config, Jinja2 server-rendered, no JS by default. 3-lane parallel agent dispatch (F1 framework + 6 widgets, F2 6 widgets + charts, F3 templates + CSS + migration). Don't start until Wave 2 is green.

The Hermes-style autonomous research agent was researched and **dropped from current scope**. Findings preserved in conversation history if revisited.

---

## Eng review decisions reference (cheat sheet)

Full text in `REVIEW-DECISIONS.md`. Quick scan:

- **1A** Vertical interface = data + features only
- **1B** No TimescaleDB, no Redis, no Dagster (plain Postgres + cachetools + APScheduler)
- **1C** Polymarket read-only, no order placement
- **1D** Reconciliation 3-match hysteresis
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
- **4D** 5-sec polling SWR (will become 60s server-refresh in Phase 5)
- **4E** No <5min backtest SLA — batch jobs

---

## Files the next agent will most often touch

- `REVIEW-DECISIONS.md` — never modify; reference only
- `src/sigil/models.py` — schema; only add new tables, never modify existing columns/PKs
- `src/sigil/config.py` — add new params at bottom
- `src/sigil/main.py` — orchestrator wiring (W2.2(a), W2.2(b))
- `tests/` — all of it
- `RUNBOOK.md` — new, write during W2.4
