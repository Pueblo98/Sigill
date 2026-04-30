# TODOs

Captured from /plan-eng-review on 2026-04-30. Each entry has the context a future maintainer needs to pick it up cold.

---

## TODO-1: ~~Archive Kalshi order book snapshots~~ → BUILD NOW (Phase 1)

**Status:** Promoted to in-scope per review. Bundle into Phase 1 alongside ingest reliability work.

(Left in TODOS.md as a tracking pointer; remove once shipped.)

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
