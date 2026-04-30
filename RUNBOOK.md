# Sigil — Runbook

Operator-facing how-to for bringing the system up locally and verifying it.
Last updated: Wave 2 (2026-04-30).

This runbook covers two flows:

1. **Smoke-test path** (no external creds, deterministic) — used to verify
   every code change end-to-end without hitting Kalshi/Polymarket.
2. **Live-ish path** (Postgres + uvicorn + Next.js) — what an operator runs
   to actually look at the dashboard.

Wave 2 only fully exercised path 1. Path 2 is documented but the operator
runs it the first time.

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

As of end of Wave 2, that should be **206/206 passing**.

---

## Path 2 — Live-ish local stack (operator dashboard)

### 2a. Postgres

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

### 2b. API server

`API_BIND_HOST` defaults to `127.0.0.1` (per decision 1H). For a dashboard
that's only reachable over Tailscale, set it to your Tailscale IP:

```bash
export API_BIND_HOST=100.x.y.z
```

Boot:

```bash
.venv/Scripts/python.exe -m sigil.api.server
# or
uvicorn sigil.api.server:app --host 127.0.0.1 --port 8000
```

The lifespan handler calls `init_db()` and `load_secrets()` (sops/age, no-op
if the sops binary or `secrets.enc.yaml` are missing). Look for the line:

    Sigil API listening on 127.0.0.1:8000 (local/tailscale only)

If you ever see `PUBLIC EXPOSURE — VERIFY`, you bound 0.0.0.0 — fix it.

Smoke check:

```bash
curl -s http://127.0.0.1:8000/api/health | jq
curl -s http://127.0.0.1:8000/api/markets | jq '.[0]'
```

### 2c. Ingestion + bankroll snapshots

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

### 2d. Settlement subscriber

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

### 2e. Next.js dashboard

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

## Known gaps surfaced during W2.4

These are not blockers for Wave 2 sign-off but should be picked up in
Phase 5 / 6 work:

1. **OMS doesn't open a `Position` row on paper-fill.** The OMS transitions
   the order to FILLED but no position bookkeeping happens. The smoke
   script (`scripts/smoke_paper_flow.py`) has to mirror a Position by
   hand. Settlement-handler + reconciliation both assume positions exist.
   File this as TODO under "OMS post-fill writes."
2. **Settlement subscriber not wired into `main.py`.** `run_ws_subscriber`
   exists and is tested end-to-end, but `main.py` only runs ingestion
   sync + bankroll snapshots. A second background task is needed.
3. **`scripts/smoke_*.py` don't run under pytest.** They're standalone
   verification scripts; equivalents under `tests/integration/` cover
   the same paths.
4. **Existing `sigil_dev.db` predates Wave 0's schema.** Don't migrate
   it forward — start from a fresh DB.

---

## Tags

| Tag | Meaning |
|---|---|
| `wave-1-verified` | Wave 1 lanes A/B/C/D all green under pytest. |
| `wave-2-complete` | Reconciliation done, 4 missing critical-path tests added, smoke green, runbook written. |
