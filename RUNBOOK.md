# Sigil — Runbook

Operator-facing how-to for bringing the system up locally and verifying it.
Last updated: Phase 5.0 + framework polish (2026-04-30).

This runbook covers three flows:

1. **In-process smoke** (no port, no external creds) — fastest signal.
2. **Real uvicorn smoke** — boots uvicorn on a non-default port, curls
   every route. Verifies the production-path lifespan + binding.
3. **Live operator stack** (Postgres + uvicorn + ingestion + Next.js) —
   what an operator runs to actually look at the dashboard against real
   markets.

---

## Prerequisites

```bash
# from repo root
python -m venv .venv
source .venv/Scripts/activate    # Windows bash; macOS/Linux: source .venv/bin/activate
pip install -e '.[dev]'
# Optional, only needed by lightgbm-using backtests:
# pip install -e '.[backtest]'
```

Python ≥3.12. The dev install pulls in pytest, pytest-asyncio, respx,
freezegun, alembic, fastapi, sqlalchemy, etc.

The repo uses bash on Windows. **Don't** mix bash `/tmp` paths with absolute
Windows paths in DB URLs — bash maps `/tmp` to a Cygwin temp dir that Python
on Windows resolves to `%TEMP%`, which is a different file. Use repo-relative
paths (`./sigil_smoke.db`) for any throwaway DB.

---

## Path 1 — In-process smoke (no external services)

This is what CI / Wave 2 verification runs. Two scripts cover it:

```bash
# 1. Fresh DB at repo-relative path
rm -f ./sigil_smoke.db

# 2. Apply the alembic baseline
ALEMBIC_DATABASE_URL='sqlite:///./sigil_smoke.db' \
    .venv/Scripts/python.exe -m alembic upgrade head

# 3. Drive the full paper-mode flow:
#      Market + MarketPrice + Prediction
#        -> DecisionEngine.evaluate()
#        -> OMS.submit() (paper short-circuit)
#        -> Settlement event closes Position
#        -> BankrollSnapshot updated
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_paper_flow.py

# 4. Hit every read endpoint via FastAPI TestClient (no port binding)
SIGIL_SMOKE_DB='./sigil_smoke.db' \
    .venv/Scripts/python.exe scripts/smoke_api.py
```

Both scripts print `[ OK ] all ... assertions passed` on success and
exit non-zero on first mismatch.

The full pytest suite covers the lower layers:

```bash
.venv/Scripts/python.exe -m pytest -v
```

As of end of Phase 5 + TODO-8, that should be **357/357 passing**.

---

## Path 2 — Real uvicorn smoke (port-bound, no external services)

Verifies the production-path startup: lifespan hooks fire, dashboard
mounts, refresh scheduler starts, real port binding works. Cleaner
signal than Path 1 because it exercises the same boot path uvicorn
takes in production.

```bash
# 1. Fresh DB with all migrations (initial schema + backtest_results)
rm -f ./sigil_smoke.db
ALEMBIC_DATABASE_URL='sqlite:///./sigil_smoke.db' \
    .venv/Scripts/python.exe -m alembic upgrade head

# 2. Launch uvicorn against the smoke DB (non-default port to avoid
#    colliding with anything on 8000). Background; kill at the end.
SIGIL_SMOKE_DB='./sigil_smoke.db' SIGIL_SMOKE_PORT=8765 \
    .venv/Scripts/python.exe scripts/smoke_uvicorn.py &
UVICORN_PID=$!
sleep 3   # let lifespan complete

# 3. Curl every public surface
curl -s -o /dev/null -w "GET /                       -> %{http_code}\n" \
    http://127.0.0.1:8765/
curl -s -o /dev/null -w "GET /page/command-center    -> %{http_code}\n" \
    http://127.0.0.1:8765/page/command-center
curl -s -o /dev/null -w "GET /page/markets           -> %{http_code}\n" \
    http://127.0.0.1:8765/page/markets
curl -s -o /dev/null -w "GET /page/models            -> %{http_code}\n" \
    http://127.0.0.1:8765/page/models
curl -s -o /dev/null -w "GET /page/health            -> %{http_code}\n" \
    http://127.0.0.1:8765/page/health
curl -s -o /dev/null -w "GET /page/bogus             -> %{http_code}\n" \
    http://127.0.0.1:8765/page/bogus
curl -s -o /dev/null -w "GET /dashboard/static/dashboard.css -> %{http_code}\n" \
    http://127.0.0.1:8765/dashboard/static/dashboard.css
curl -s -o /dev/null -w "GET /dashboard/static/relative-time.js -> %{http_code}\n" \
    http://127.0.0.1:8765/dashboard/static/relative-time.js
curl -s -o /dev/null -w "GET /api/health             -> %{http_code}\n" \
    http://127.0.0.1:8765/api/health
curl -s -o /dev/null -w "GET /api/markets            -> %{http_code}\n" \
    http://127.0.0.1:8765/api/markets

# Expected:
#   /                          -> 302 (redirect to /page/<default>)
#   /page/command-center       -> 200
#   /page/markets              -> 200
#   /page/models               -> 200
#   /page/health               -> 200
#   /page/bogus                -> 404
#   /dashboard/static/*        -> 200 (text/css and text/javascript)
#   /api/health, /api/markets  -> 200

# 4. Cleanup
kill $UVICORN_PID 2>/dev/null
rm -f ./sigil_smoke.db
```

The first page load shows widgets in a `Loading...` state because the
60-second background refresh hasn't fired yet. Wait ~70s and re-curl to
see widgets populated from the cache. The pytest suite covers populated
widgets via FastAPI TestClient — the live smoke just confirms the
binding/lifespan path.

---

## Path 3 — Live operator stack (Postgres + ingestion + dashboard)

### 3a. Postgres

You can either run real Postgres or fall back to the SQLite path. The schema
is identical via alembic; downstream code doesn't care.

For Postgres:

```bash
# Start a local Postgres (either via Postgres.app, brew services, or docker):
docker run -d --name sigil-pg -p 5432:5432 \
  -e POSTGRES_USER=sigil -e POSTGRES_PASSWORD=sigil \
  -e POSTGRES_DB=sigil postgres:16

# config.py defaults to postgresql+asyncpg://sigil:sigil@localhost:5432/sigil

# Apply schema
.venv/Scripts/python.exe -m alembic upgrade head
```

For SQLite-only (no docker), set in shell or .env:

```bash
export DATABASE_URL='sqlite+aiosqlite:///./sigil_dev.db'
ALEMBIC_DATABASE_URL='sqlite:///./sigil_dev.db' \
    .venv/Scripts/python.exe -m alembic upgrade head
```

### 3b. API + Python dashboard

`API_BIND_HOST` defaults to `127.0.0.1` (per decision 1H). For a dashboard
that's only reachable over Tailscale, set it to your Tailscale IP. Note
that `Config` is a plain pydantic `BaseModel` — env vars don't auto-flow
in. Either edit `config.py`, or use a wrapper script that mutates `config`
before `uvicorn.run()` (see `scripts/smoke_uvicorn.py`).

Set `DASHBOARD_ENABLED=true` (or flip the default in `config.py`) to mount
the Python dashboard at `/`. With it off, only `/api/*` is served — the
existing FastAPI tests run that way to skip the refresh scheduler.

Boot:

```bash
.venv/Scripts/python.exe -m sigil.api.server
# or
uvicorn sigil.api.server:app --host 127.0.0.1 --port 8000
```

The lifespan handler calls `init_db()` and `load_secrets()` (sops/age, no-op
if the sops binary or `secrets.enc.yaml` are missing), and — when
`DASHBOARD_ENABLED` is true — starts the dashboard refresh job. Look for
the lines:

    Sigil API listening on 127.0.0.1:8000 (local/tailscale only)
    Dashboard at http://127.0.0.1:8000/

If you ever see `PUBLIC EXPOSURE — VERIFY`, you bound 0.0.0.0 — fix it.

Smoke check:

```bash
curl -s http://127.0.0.1:8000/                    # 302 to /page/<default>
curl -s http://127.0.0.1:8000/page/command-center  # HTML
curl -s http://127.0.0.1:8000/api/health | jq
curl -s http://127.0.0.1:8000/api/markets | jq '.[0]'
```

### 3c. Ingestion + bankroll snapshots

The orchestrator (`src/sigil/main.py`) does two things:

- Polls Kalshi for market data via `MarketManager.sync_source()`.
- Runs an APScheduler job every 5 minutes that writes a `BankrollSnapshot`.
  Without this, the drawdown circuit breaker is permanently INACTIVE
  (decisions 2F + W2.2(b)).

Requires `KALSHI_API_KEY` etc. in env or in `secrets.enc.yaml`:

```bash
.venv/Scripts/python.exe -m sigil.main
```

If you're just dogfooding the dashboard with no live data, skip this and
seed a `BankrollSnapshot` row by hand or via `scripts/smoke_paper_flow.py`.

### 3d. Settlement subscriber

Lives in `sigil.ingestion.settlement` but isn't yet wired into `main.py`.
For now, run it manually if you have positions to settle:

```python
import asyncio
from sigil.db import AsyncSessionLocal
from sigil.ingestion.settlement import KalshiSettlementStream, SettlementHandler, run_ws_subscriber

async def go():
    handler = SettlementHandler(AsyncSessionLocal)
    stream = KalshiSettlementStream()
    await run_ws_subscriber(stream, handler)

asyncio.run(go())
```

### 3e. Next.js dashboard

```bash
cd sigil-frontend
npm install
npm run dev    # binds 127.0.0.1:3000
```

Open `http://127.0.0.1:3000`. With the API on port 8000 and at least one
`BankrollSnapshot` row, the dashboard pages will populate via SWR
5-second polling (decision 4D).

---

## Driving a paper-mode trade by hand

Useful when verifying a code change without waiting for the orchestrator.

```python
from datetime import datetime, timezone
from uuid import uuid4
import asyncio

from sigil.db import AsyncSessionLocal
from sigil.decision.drawdown import DrawdownState
from sigil.decision.engine import DecisionEngine
from sigil.decision.wiring import make_oms_submit
from sigil.execution.oms import OMS
from sigil.models import Market, MarketPrice, Prediction


async def fire():
    async with AsyncSessionLocal() as session:
        market = Market(
            id=uuid4(),
            platform="kalshi",
            external_id="MANUAL-TEST",
            title="Manual test market",
            taxonomy_l1="sports",
            market_type="binary",
            status="open",
        )
        session.add(market)
        session.add(MarketPrice(
            time=datetime.now(timezone.utc),
            market_id=market.id,
            bid=0.49, ask=0.51, last_price=0.50,
            source="manual",
        ))
        prediction = Prediction(
            id=uuid4(), market_id=market.id,
            model_id="manual", model_version="v0",
            predicted_prob=0.75, confidence=1.0,
            market_price_at_prediction=0.50, edge=0.25,
        )
        session.add(prediction)
        await session.commit()

        oms = OMS(session=session)
        submit = make_oms_submit(oms)

        async def stub(_, mode="paper"):
            return DrawdownState.INACTIVE

        engine = DecisionEngine(oms_submit=submit, drawdown_state_fn=stub, mode="paper")
        result = await engine.evaluate(
            session=session,
            prediction=prediction,
            market_price=0.50,
            platform="kalshi",
            market_id=market.id,
        )
        await session.commit()
        print(result)

asyncio.run(fire())
```

---

## Persisting a backtest run

Backtest results don't auto-persist — `Backtester.run()` returns an
in-memory dataclass. Pipe it through `persist_backtest_result` to land
a row in `backtest_results` (which the F2 dashboard widget reads):

```python
from sigil.backtesting.engine import Backtester
from sigil.backtesting.metrics import all_metrics
from sigil.backtesting.persistence import persist_backtest_result
from sigil.db import AsyncSessionLocal

result = backtester.run()
metrics = all_metrics(result)  # optional; persist will compute defaults
async with AsyncSessionLocal() as session:
    await persist_backtest_result(
        session,
        result,
        name="elo_v2 nightly",
        model_id="elo_v2",
        metrics=metrics,
    )
    await session.commit()
```

The widget on `/page/models` shows the most recent row.

---

## Enabling the orderbook archive

Off by default. Flip on for live deploys to capture replay-into-backtester
input alongside the existing `data/raw/kalshi_ticks.jsonl` lake. The
archive runs as a side effect of `StreamProcessor._flush_once()`, so no
new processes; one shared writer per orchestrator.

```python
# src/sigil/config.py — Config is BaseModel (no env auto-load)
ORDERBOOK_ARCHIVE_ENABLED: bool = True
ORDERBOOK_ARCHIVE_DIR: str = "/var/lib/sigil/orderbook_archive"  # default is repo data/orderbook_archive
ORDERBOOK_ARCHIVE_MAX_OPEN_HANDLES: int = 256
```

Disk layout:

    <ORDERBOOK_ARCHIVE_DIR>/kalshi/<external_id>/<YYYY-MM-DD>.jsonl

Each line is the full tick dict (best-bid/ask scalars + raw `bids`/`asks`
ladder + last_price + source + UTC `time`). External-id directory names
are sanitized; `..` substrings are collapsed to `__` so a hostile market
ticker can't escape the archive root.

Sizing rule of thumb: ~few MB per market per day under heavy flow.
Files are uncompressed JSONL; deletion / compression is manual until a
`prune_orderbook_archive` helper lands (TODO-9 follow-up).

Smoke check:

```bash
.venv/Scripts/python.exe scripts/smoke_orderbook_archive.py
```

Asserts that two markets routed through one batch each land in their
own per-day file with depth + renamed `external_id` preserved.

The reader (replay archive into `Backtester`) is **not yet built**;
the JSONL format is the contract. See TODO-9 in `TODOS.md`.

---

## Notes / gaps

These are not blockers; tracked in `TODOS.md`:

1. **`scripts/smoke_*.py` don't run under pytest.** They're standalone
   verification scripts; equivalents under `tests/integration/` cover
   the same paths.
2. **Existing `sigil_dev.db` predates Wave 0's schema.** Don't migrate
   it forward — start from a fresh DB.
3. **`Config` doesn't read env vars** (it's `BaseModel`, not
   `BaseSettings`). Use `scripts/smoke_uvicorn.py` as a template if you
   need to override DB URL / dashboard flag without editing `config.py`.

Closed since prior runbook revision: OMS now opens Positions on fill
(TODO-4), settlement subscriber is wired into `main.py` and gated by
`SETTLEMENT_WS_ENABLED` (TODO-5).

---

## Tags

| Tag | Meaning |
|---|---|
| `wave-1-verified` | Wave 1 lanes A/B/C/D all green under pytest. |
| `wave-2-complete` | Reconciliation done, 4 missing critical-path tests added, smoke green, runbook written. |
| `phase-5-0-complete` | Read-only Python dashboard live alongside the Next.js frontend. 12 widgets, 4 pages, server-rendered HTML, per-widget TTL cache, 60s background refresh. |
