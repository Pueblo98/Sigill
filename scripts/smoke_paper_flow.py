"""W2.4 in-process smoke test.

Drives the full paper-mode flow against a temporary SQLite DB:

    Market + MarketPrice + Prediction
      -> DecisionEngine.evaluate()
      -> OMS.submit() (paper-mode short-circuit)
      -> Settlement event closes Position
      -> BankrollSnapshot updated

Assertions live inside the script. Run after `alembic upgrade head` against
the same DB. Exits non-zero on first mismatch.

Usage:

    rm -f /tmp/sigil_smoke.db
    ALEMBIC_DATABASE_URL='sqlite:////tmp/sigil_smoke.db' \
        .venv/Scripts/python.exe -m alembic upgrade head
    SIGIL_SMOKE_DB=/tmp/sigil_smoke.db .venv/Scripts/python.exe scripts/smoke_paper_flow.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import sigil.db as sigil_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sigil.decision.drawdown import DrawdownState
from sigil.decision.engine import DecisionEngine
from sigil.decision.wiring import make_oms_submit
from sigil.execution.bankroll import snapshot_bankroll
from sigil.execution.oms import OMS, OrderState
from sigil.ingestion.settlement import SettlementEvent, SettlementHandler
from sigil.models import (
    BankrollSnapshot,
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
)


def _ok(label: str) -> None:
    print(f"[ OK ] {label}")


def _fail(label: str, detail: str = "") -> None:
    print(f"[FAIL] {label}: {detail}")
    sys.exit(1)


async def main() -> None:
    db_path = os.environ.get("SIGIL_SMOKE_DB", "/tmp/sigil_smoke.db")
    db_url = f"sqlite+aiosqlite:///{db_path}"
    print(f"--- Sigil paper-mode smoke (db={db_url}) ---")

    engine = create_async_engine(db_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    sigil_db.engine = engine
    sigil_db.AsyncSessionLocal = factory

    async with factory() as session:
        market = Market(
            id=uuid4(),
            platform="kalshi",
            external_id=f"SMOKE-{uuid4().hex[:8]}",
            title="Smoke test market",
            taxonomy_l1="sports",
            market_type="binary",
            status="open",
        )
        session.add(market)
        session.add(
            MarketPrice(
                time=datetime.now(timezone.utc),
                market_id=market.id,
                bid=0.49,
                ask=0.51,
                last_price=0.50,
                source="smoke",
            )
        )
        await session.commit()
        _ok("seeded Market + MarketPrice")

        prediction = Prediction(
            id=uuid4(),
            market_id=market.id,
            model_id="smoke-model",
            model_version="v0",
            predicted_prob=0.75,
            confidence=1.0,
            market_price_at_prediction=0.50,
            edge=0.25,
        )
        session.add(prediction)
        await session.commit()
        _ok("inserted positive-edge Prediction (p_model=0.75, p_market=0.50)")

        await snapshot_bankroll(session, mode="paper")
        _ok("seeded baseline BankrollSnapshot")

        oms = OMS(session=session)
        submit = make_oms_submit(oms)

        async def stub_drawdown(_session, mode="paper"):
            return DrawdownState.INACTIVE

        engine_d = DecisionEngine(oms_submit=submit, drawdown_state_fn=stub_drawdown, mode="paper")
        result = await engine_d.evaluate(
            session=session,
            prediction=prediction,
            market_price=0.50,
            platform="kalshi",
            market_id=market.id,
        )
        await session.commit()

        if not result.accepted:
            _fail("DecisionEngine.evaluate", result.reason)
        if result.reason != "submitted":
            _fail("decision reason", result.reason)
        _ok(f"DecisionEngine accepted (edge={result.edge:.3f})")

        orders = (await session.execute(select(Order))).scalars().all()
        if len(orders) != 1:
            _fail("expected 1 order", f"got {len(orders)}")
        order = orders[0]
        if order.status != OrderState.FILLED:
            _fail("order not filled", order.status)
        if order.mode != "paper":
            _fail("order not in paper mode", order.mode)
        if not order.client_order_id.startswith("sigil_"):
            _fail("client_order_id prefix", order.client_order_id)
        _ok(f"OMS wrote Order {order.id} ({order.quantity} contracts @ ${order.price:.3f}, status={order.status})")

        # Manually mirror an open Position for the order so settlement has something to close.
        # In production this is OMS's responsibility on fill; the OMS smoke path doesn't yet
        # write Positions on paper-fill — track that gap explicitly.
        pos = Position(
            id=uuid4(),
            platform="kalshi",
            market_id=market.id,
            mode="paper",
            outcome=order.outcome,
            quantity=order.filled_quantity,
            avg_entry_price=float(order.avg_fill_price or order.price),
            status="open",
        )
        session.add(pos)
        await session.commit()
        _ok(f"opened Position {pos.id} mirroring fill")

    handler = SettlementHandler(factory)
    settled = await handler.apply(
        SettlementEvent(
            platform="kalshi",
            external_id=market.external_id,
            settlement_value=1.0,  # YES wins
            settled_at=datetime.now(timezone.utc),
        )
    )
    if settled != 1:
        _fail("settlement count", f"expected 1, got {settled}")
    _ok("settlement event closed 1 position")

    async with factory() as session:
        refreshed = await session.get(Position, pos.id)
        if refreshed.status != "closed":
            _fail("position not closed", refreshed.status)
        if float(refreshed.realized_pnl) <= 0:
            _fail("realized_pnl <= 0", str(refreshed.realized_pnl))
        _ok(f"position closed (realized_pnl=${float(refreshed.realized_pnl):.2f})")

        snaps = (
            await session.execute(
                select(BankrollSnapshot).where(BankrollSnapshot.mode == "paper").order_by(BankrollSnapshot.time)
            )
        ).scalars().all()
        if len(snaps) < 2:
            _fail("expected >=2 BankrollSnapshot rows", f"got {len(snaps)}")
        latest = snaps[-1]
        baseline = snaps[0]
        if float(latest.realized_pnl_total) <= float(baseline.realized_pnl_total):
            _fail("realized_pnl_total didn't increase", f"{baseline.realized_pnl_total} -> {latest.realized_pnl_total}")
        if latest.settled_trades_total <= baseline.settled_trades_total:
            _fail("settled_trades_total didn't increase", f"{baseline.settled_trades_total} -> {latest.settled_trades_total}")
        _ok(
            f"BankrollSnapshot updated (equity ${float(baseline.equity):.2f} -> ${float(latest.equity):.2f}, "
            f"settled {baseline.settled_trades_total} -> {latest.settled_trades_total})"
        )

    await engine.dispose()
    print("\n[ OK ] all smoke assertions passed")


if __name__ == "__main__":
    asyncio.run(main())
