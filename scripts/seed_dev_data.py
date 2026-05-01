"""Seed realistic dev data so the dashboard isn't empty.

Populates Markets, MarketPrice, Predictions, SourceHealth,
ReconciliationObservation, and a BacktestResult — enough to make
every research/data widget render with content.

By default this script does NOT fabricate Orders, Positions, or
BankrollSnapshots — those are paper-trading state and should come from
the real signal → DecisionEngine → OMS flow against your bankroll.
The fake-trades path is still available behind ``--include-fake-trades``
for demos and screenshots, but should not be used when you want the
dashboard to honestly reflect what your strategies have done.

All rows seeded by this script use external-id prefix ``DEV-`` so they
are easy to clean up and won't collide with real ingestion.

Usage:

    # Seed market/prediction data (no fake trades)
    .venv/Scripts/python.exe scripts/seed_dev_data.py

    # Demo mode: include fabricated paper trades + bankroll snapshots
    .venv/Scripts/python.exe scripts/seed_dev_data.py --include-fake-trades

    # Different DB
    .venv/Scripts/python.exe scripts/seed_dev_data.py --db-url \\
        sqlite+aiosqlite:///./sigil_dev.db

    # Wipe DEV- seed data without re-inserting
    .venv/Scripts/python.exe scripts/seed_dev_data.py --reset-only

    # Wipe paper-trading state (Orders/Positions/BankrollSnapshots in
    # mode=paper) without touching market data. Use this to start the
    # paper bankroll from BANKROLL_INITIAL again.
    .venv/Scripts/python.exe scripts/seed_dev_data.py --wipe-paper-state
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import sigil.db as sigil_db
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from sigil.config import config as root_config
from sigil.db import Base
import sigil.models  # noqa: F401  (registers tables on Base.metadata)
from sigil.models import (
    BacktestResult,
    BankrollSnapshot,
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
    PredictionFeature,
    ReconciliationObservation,
    SourceHealth,
)


DEV_PREFIX = "DEV-"

# (external_id, platform, title, taxonomy_l1, "true" probability)
# The "true" prob seeds the random-walk midpoint so charts have shape.
SEED_MARKETS: List[Tuple[str, str, str, str, float]] = [
    ("DEV-NFL-KC-SB",      "kalshi",     "Will the Chiefs win the Super Bowl?",            "sports",    0.32),
    ("DEV-NBA-CELT-FIN",   "kalshi",     "Will the Celtics reach the Finals?",             "sports",    0.55),
    ("DEV-MLB-LAD-WIN",    "kalshi",     "Will the Dodgers win 100+ games?",               "sports",    0.62),
    ("DEV-NCAA-MICH-CFP",  "kalshi",     "Will Michigan make the CFP semifinal?",          "sports",    0.41),
    ("DEV-PGA-MASTERS",    "kalshi",     "Will Scheffler win the Masters?",                "sports",    0.18),
    ("DEV-FED-CUT-DEC",    "kalshi",     "Will the Fed cut rates in December?",            "economics", 0.71),
    ("DEV-CPI-3-PCT",      "kalshi",     "Will CPI print >3% for August?",                 "economics", 0.27),
    ("DEV-BTC-100K-EOY",   "polymarket", "Will Bitcoin reach $100k by end of year?",       "crypto",    0.48),
    ("DEV-ETH-5K-EOY",     "polymarket", "Will Ethereum reach $5k by end of year?",        "crypto",    0.33),
    ("DEV-PRES-INCUMB",    "kalshi",     "Will the incumbent party hold the presidency?",  "politics",  0.50),
]

SEED_MODELS = [
    ("baseline_elo",   "v1.0"),
    ("baseline_elo",   "v1.1"),
    ("challenger_glm", "v0.3"),
]

SEED_SOURCES = ["kalshi", "polymarket", "espn_scoreboard", "odds_api"]


def _ok(label: str) -> None:
    print(f"[ OK ] {label}")


def _info(label: str) -> None:
    print(f"[INFO] {label}")


async def _reset_seed(session) -> None:
    """Delete prior DEV-prefixed seed data. Order matters (FK constraints)."""
    dev_market_ids = (
        await session.execute(
            select(Market.id).where(Market.external_id.like(f"{DEV_PREFIX}%"))
        )
    ).scalars().all()
    if not dev_market_ids:
        _info("no prior DEV- seed found")
        return

    await session.execute(delete(MarketPrice).where(MarketPrice.market_id.in_(dev_market_ids)))
    await session.execute(
        delete(PredictionFeature).where(
            PredictionFeature.prediction_id.in_(
                select(Prediction.id).where(Prediction.market_id.in_(dev_market_ids))
            )
        )
    )
    await session.execute(delete(Prediction).where(Prediction.market_id.in_(dev_market_ids)))
    await session.execute(delete(Order).where(Order.market_id.in_(dev_market_ids)))
    await session.execute(delete(Position).where(Position.market_id.in_(dev_market_ids)))
    await session.execute(
        delete(ReconciliationObservation).where(
            ReconciliationObservation.market_id.in_(dev_market_ids)
        )
    )
    await session.execute(delete(Market).where(Market.id.in_(dev_market_ids)))

    # SourceHealth and BankrollSnapshot don't FK to markets; we wipe by tag.
    await session.execute(
        delete(SourceHealth).where(SourceHealth.error_message.like("[DEV] %"))
    )
    await session.execute(
        delete(SourceHealth).where(SourceHealth.source_name.like(f"{DEV_PREFIX.lower()}%"))
    )
    # Delete any BankrollSnapshot rows whose unrealized_pnl equals our magic tag — see below.
    # Cleaner: tag via a sentinel value in equity (we use float fractional below).
    # Simpler: just delete all paper-mode snapshots in the seeded window. Skip for safety.
    await session.execute(
        delete(BacktestResult).where(BacktestResult.name.like(f"{DEV_PREFIX}%"))
    )
    _ok(f"wiped prior DEV- seed across {len(dev_market_ids)} markets")


async def _seed_markets(session, now: datetime) -> List[Market]:
    out: List[Market] = []
    for ext, platform, title, tax, _truep in SEED_MARKETS:
        m = Market(
            id=uuid4(),
            platform=platform,
            external_id=ext,
            title=title,
            taxonomy_l1=tax,
            market_type="binary",
            status="open",
            resolution_date=now + timedelta(days=random.randint(7, 60)),
        )
        session.add(m)
        out.append(m)
    await session.flush()
    _ok(f"inserted {len(out)} Markets")
    return out


async def _seed_market_prices(session, markets: List[Market], now: datetime) -> int:
    rng = random.Random(42)
    # 30 days × 12 ticks/day (every 2h) = 360 ticks per market.
    n = 0
    span = timedelta(days=30)
    step = timedelta(hours=2)
    for m, (_e, _p, _t, _tax, true_p) in zip(markets, SEED_MARKETS):
        price = max(0.05, min(0.95, true_p + rng.uniform(-0.05, 0.05)))
        t = now - span
        while t <= now:
            # mean-reverting random walk around true_p
            price += (true_p - price) * 0.06 + rng.gauss(0, 0.012)
            price = max(0.02, min(0.98, price))
            spread = rng.uniform(0.005, 0.02)
            bid = round(max(0.01, price - spread / 2), 4)
            ask = round(min(0.99, price + spread / 2), 4)
            session.add(
                MarketPrice(
                    time=t,
                    market_id=m.id,
                    bid=bid,
                    ask=ask,
                    last_price=round(price, 4),
                    volume_24h=rng.uniform(1000, 250_000),
                    open_interest=rng.uniform(500, 80_000),
                    source="dev_seed",
                )
            )
            n += 1
            t += step
    _ok(f"inserted {n} MarketPrice rows ({len(markets)} markets × ~360)")
    return n


async def _seed_predictions(session, markets: List[Market], now: datetime) -> List[Prediction]:
    """Several Predictions per market spanning the last 14 days. The latest
    Prediction for each market is engineered so 5/10 markets clear the
    ``min_edge=0.05`` filter that signal_queue + market_list use.
    """
    rng = random.Random(7)
    out: List[Prediction] = []
    span = timedelta(days=14)
    for idx, (m, (_e, _p, _t, _tax, true_p)) in enumerate(zip(markets, SEED_MARKETS)):
        n_per_market = rng.randint(2, 5)
        positive_edge_market = idx % 2 == 0  # half pass the filter
        for k in range(n_per_market):
            ts = now - span + (span / max(n_per_market, 1)) * k + timedelta(hours=rng.randint(0, 5))
            mp = max(0.05, min(0.95, true_p + rng.uniform(-0.05, 0.05)))
            if k == n_per_market - 1 and positive_edge_market:
                # latest pred for half the markets: edge >= +0.07 vs. mp
                pred_prob = max(0.05, min(0.95, mp + rng.uniform(0.07, 0.18)))
            else:
                pred_prob = max(0.05, min(0.95, true_p + rng.uniform(-0.06, 0.06)))
            edge = pred_prob - mp
            model_id, ver = SEED_MODELS[k % len(SEED_MODELS)]
            p = Prediction(
                id=uuid4(),
                market_id=m.id,
                model_id=model_id,
                model_version=ver,
                predicted_prob=round(pred_prob, 4),
                confidence=round(rng.uniform(0.55, 0.95), 3),
                market_price_at_prediction=round(mp, 4),
                edge=round(edge, 4),
                created_at=ts,
            )
            session.add(p)
            session.add_all([
                PredictionFeature(prediction_id=p.id, feature_name="elo_diff",
                                  value=round(rng.uniform(-200, 200), 1), version=1),
                PredictionFeature(prediction_id=p.id, feature_name="recent_form",
                                  value=round(rng.uniform(0.0, 1.0), 3), version=1),
            ])
            out.append(p)
    await session.flush()
    _ok(f"inserted {len(out)} Predictions ({sum(1 for p in out if (p.edge or 0) >= 0.05)} clear min_edge=0.05)")
    return out


async def _seed_orders_positions(
    session, markets: List[Market], predictions: List[Prediction], now: datetime
) -> Tuple[int, int]:
    rng = random.Random(11)
    orders = 0
    positions = 0

    # Pick predictions across 6 markets to convert into orders/positions.
    used_markets = markets[:6]
    for i, m in enumerate(used_markets):
        # Latest prediction for this market
        pred = max((p for p in predictions if p.market_id == m.id), key=lambda p: p.created_at, default=None)
        if pred is None:
            continue

        outcome = "yes"
        side = "buy"
        qty = rng.randint(50, 250)
        price = float(pred.market_price_at_prediction or 0.5)

        order = Order(
            id=uuid4(),
            client_order_id=f"sigil_dev_{m.external_id}_{i}",
            platform=m.platform,
            market_id=m.id,
            prediction_id=pred.id,
            mode="paper",
            side=side,
            outcome=outcome,
            order_type="limit",
            price=round(price, 4),
            quantity=qty,
            filled_quantity=qty,
            avg_fill_price=round(price + rng.uniform(-0.005, 0.005), 4),
            fees=round(qty * 0.07, 4),
            edge_at_entry=float(pred.edge or 0.0),
            status="filled",
            created_at=now - timedelta(days=rng.randint(1, 5)),
        )
        session.add(order)
        orders += 1

        # 4 of 6 stay open, 2 close (one win, one lose).
        if i < 4:
            session.add(Position(
                id=uuid4(),
                platform=m.platform,
                market_id=m.id,
                mode="paper",
                outcome=outcome,
                quantity=qty,
                avg_entry_price=order.avg_fill_price,
                current_price=round(order.avg_fill_price + rng.uniform(-0.04, 0.06), 4),
                unrealized_pnl=round(qty * rng.uniform(-0.04, 0.06), 2),
                realized_pnl=0.0,
                status="open",
                opened_at=order.created_at,
            ))
        else:
            won = i == 4
            settlement = 1.0 if won else 0.0
            realized = qty * (settlement - float(order.avg_fill_price))
            session.add(Position(
                id=uuid4(),
                platform=m.platform,
                market_id=m.id,
                mode="paper",
                outcome=outcome,
                quantity=qty,
                avg_entry_price=order.avg_fill_price,
                current_price=round(settlement, 4),
                unrealized_pnl=0.0,
                realized_pnl=round(realized, 2),
                status="closed",
                opened_at=order.created_at,
                closed_at=order.created_at + timedelta(hours=rng.randint(6, 36)),
            ))
        positions += 1

    # Add 2 more "created" / "canceled" orders to vary recent_activity.
    for kind, status in (("limit", "canceled"), ("limit", "open")):
        m = markets[6 + (positions % 4)]
        session.add(Order(
            id=uuid4(),
            client_order_id=f"sigil_dev_{m.external_id}_{kind}_{status}",
            platform=m.platform,
            market_id=m.id,
            mode="paper",
            side="buy",
            outcome="yes",
            order_type=kind,
            price=0.50,
            quantity=100,
            filled_quantity=0,
            status=status,
            created_at=now - timedelta(hours=rng.randint(1, 18)),
        ))
        orders += 1

    _ok(f"inserted {orders} Orders + {positions} Positions (4 open, 2 closed)")
    return orders, positions


async def _seed_source_health(session, now: datetime) -> int:
    rng = random.Random(13)
    n = 0
    # Last 24h × 30min cadence × 4 sources = 192 rows. Mostly ok; a few errors.
    cadence = timedelta(minutes=30)
    t = now - timedelta(hours=24)
    seen: set[Tuple[datetime, str]] = set()
    while t <= now:
        for src in SEED_SOURCES:
            # 90% ok, 8% timeout, 2% 5xx
            r = rng.random()
            status = "ok"
            err: str | None = None
            if r < 0.02:
                status = "error"
                err = "[DEV] HTTP 503 from upstream"
            elif r < 0.10:
                status = "error"
                err = "[DEV] timed out after 5000ms"
            ts = t + timedelta(microseconds=rng.randint(0, 999_999))
            key = (ts, src)
            if key in seen:
                continue
            seen.add(key)
            session.add(SourceHealth(
                check_time=ts,
                source_name=src,
                status=status,
                latency_ms=rng.randint(80, 1500),
                error_message=err,
                records_fetched=rng.randint(0, 240) if status == "ok" else 0,
            ))
            n += 1
        t += cadence
    _ok(f"inserted {n} SourceHealth rows (mostly ok, ~10% errors)")
    return n


async def _seed_reconciliation(session, markets: List[Market], now: datetime) -> int:
    rng = random.Random(17)
    n = 0
    for m in markets[:4]:
        for k in range(5):
            qty = rng.randint(50, 200)
            session.add(ReconciliationObservation(
                id=uuid4(),
                observed_at=now - timedelta(minutes=5 * (4 - k)),
                platform=m.platform,
                market_id=m.id,
                outcome="yes",
                exchange_qty=qty,
                local_qty=qty if k < 4 or rng.random() < 0.5 else qty - 1,
                is_match=True,
                consecutive_matches=k,
            ))
            n += 1
    _ok(f"inserted {n} ReconciliationObservation rows")
    return n


async def _seed_bankroll_snapshots(session, now: datetime) -> int:
    """14-day equity curve, hourly. Slight upward drift + a 2-day drawdown
    around day 7-9 so the bankroll widget has a story to tell."""
    rng = random.Random(19)
    n = 0
    span = timedelta(days=14)
    step = timedelta(hours=1)
    initial = float(root_config.BANKROLL_INITIAL)
    realized_total = 0.0
    settled = 0
    equity = initial
    t = now - span
    hour = 0
    while t <= now:
        # Drift up at +0.0008/h with noise; -0.005/h during drawdown window.
        days_in = (t - (now - span)).total_seconds() / 86400
        drift = -0.005 if 6 < days_in < 8.5 else 0.0008
        equity *= 1 + drift + rng.gauss(0, 0.0015)
        equity = max(initial * 0.6, equity)  # floor

        # Realize trades sporadically.
        if rng.random() < 0.04:
            settled += 1
            realized_total += rng.uniform(-50, 90)

        unrealized = equity - initial - realized_total

        session.add(BankrollSnapshot(
            time=t,
            mode="paper",
            equity=round(equity, 2),
            realized_pnl_total=round(realized_total, 2),
            unrealized_pnl_total=round(unrealized, 2),
            settled_trades_total=settled,
            settled_trades_30d=settled,  # all in the window for our 14d span
        ))
        n += 1
        t += step
        hour += 1
    _ok(f"inserted {n} BankrollSnapshot rows (paper mode, 14d hourly)")
    return n


async def _seed_backtest_result(session, now: datetime) -> int:
    session.add(BacktestResult(
        id=uuid4(),
        name=f"{DEV_PREFIX}baseline_elo nightly",
        model_id="baseline_elo",
        created_at=now - timedelta(hours=8),
        config_json={"start": "2026-04-01", "end": "2026-04-30", "fee_kalshi": 0.07},
        initial_capital=5000.0,
        final_equity=5612.34,
        roi=0.1225,
        sharpe=1.41,
        max_drawdown=-0.082,
        win_rate=0.58,
        n_trades=132,
        brier=0.211,
        log_loss=0.62,
        calibration_error=0.038,
    ))
    _ok("inserted 1 BacktestResult row")
    return 1


async def _wipe_paper_state(session) -> None:
    """Delete every paper-mode Order, Position, and BankrollSnapshot.

    Leaves Markets, MarketPrice, Predictions, SourceHealth, and
    BacktestResult intact — only the trading state is reset, so the
    paper bankroll restarts from BANKROLL_INITIAL on the next snapshot.
    """
    paper_orders = (await session.execute(delete(Order).where(Order.mode == "paper"))).rowcount
    paper_positions = (await session.execute(delete(Position).where(Position.mode == "paper"))).rowcount
    paper_snaps = (await session.execute(delete(BankrollSnapshot).where(BankrollSnapshot.mode == "paper"))).rowcount
    _ok(
        f"wiped paper-trading state: {paper_orders} Orders, "
        f"{paper_positions} Positions, {paper_snaps} BankrollSnapshots"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", default=None,
                        help="override DATABASE_URL (else config.DATABASE_URL)")
    parser.add_argument("--reset-only", action="store_true",
                        help="wipe DEV- seed data and exit (no re-insert)")
    parser.add_argument("--wipe-paper-state", action="store_true",
                        help="wipe paper Orders/Positions/BankrollSnapshots and exit; "
                             "leaves market data intact so the next snapshot starts "
                             "from BANKROLL_INITIAL")
    parser.add_argument("--include-fake-trades", action="store_true",
                        help="ALSO seed fabricated Orders/Positions/BankrollSnapshots "
                             "(demo mode). Off by default — the paper-trading flow "
                             "should drive these via the real signal → OMS path.")
    args = parser.parse_args()

    db_url = args.db_url or root_config.DATABASE_URL
    print(f"--- Sigil dev-data seed (db={db_url}) ---")

    engine = create_async_engine(db_url, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    sigil_db.engine = engine
    sigil_db.AsyncSessionLocal = factory

    now = datetime.now(timezone.utc)

    if args.wipe_paper_state:
        async with factory() as session:
            await _wipe_paper_state(session)
            await session.commit()
        print("\n[ OK ] paper-trading state wiped (market data untouched)")
        await engine.dispose()
        return 0

    async with factory() as session:
        await _reset_seed(session)
        await session.commit()

    if args.reset_only:
        print("\n[ OK ] reset complete (no re-insert)")
        await engine.dispose()
        return 0

    async with factory() as session:
        markets = await _seed_markets(session, now)
        await _seed_market_prices(session, markets, now)
        preds = await _seed_predictions(session, markets, now)
        await _seed_source_health(session, now)
        await _seed_reconciliation(session, markets, now)
        await _seed_backtest_result(session, now)
        if args.include_fake_trades:
            await _seed_orders_positions(session, markets, preds, now)
            await _seed_bankroll_snapshots(session, now)
            print("[INFO] --include-fake-trades active: paper trade rows are fabricated, "
                  "not from the real signal flow.")
        await session.commit()

    await engine.dispose()
    print("\n[ OK ] dev seed populated. Reload the dashboard; widgets should fill within ~60s")
    print("       (the refresh job ticks every minute; or curl /page/command-center after a tick)")
    if not args.include_fake_trades:
        print("       Paper trading state is empty — start ingestion to let real signals fill it,")
        print("       or re-run with --include-fake-trades for a demo dataset.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
