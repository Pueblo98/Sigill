"""Tests for the model performance feature.

Covers:
- The model registry (idempotent registration, lookup).
- The aggregator (`sigil.api.model_performance`) — summary, equity curve,
  recent trades, recent predictions, all_model_summaries, model_detail.
- The HTTP endpoints (`GET /api/models`, `GET /api/models/{id}`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.api import model_performance as mp
from sigil.models import Market, Order, Position, Prediction
from sigil.models_registry import ModelDef, all_models, get_model, register_model


# ---- registry ------------------------------------------------------------


def test_registry_lookup_and_listing():
    # spread_arb / elo_sports are registered via import side effects in routes.py;
    # importing the conftest's `client` fixture transitively triggers that. Here
    # we just verify our two known models are present.
    ids = {m.model_id for m in all_models()}
    assert "spread_arb" in ids
    assert "elo_sports" in ids

    spread = get_model("spread_arb")
    assert spread is not None
    assert spread.display_name == "Stat Arb (Cross-Platform)"
    assert "arbitrage" in spread.tags


def test_register_model_is_idempotent_last_write_wins():
    register_model(ModelDef(
        model_id="_test_idempotent",
        version="v0",
        display_name="Original",
        description="x",
        tags=("a",),
    ))
    register_model(ModelDef(
        model_id="_test_idempotent",
        version="v1",
        display_name="Updated",
        description="y",
        tags=("b",),
    ))
    m = get_model("_test_idempotent")
    assert m is not None
    assert m.display_name == "Updated"
    assert m.version == "v1"


# ---- helpers -------------------------------------------------------------


async def _seed_market(session, *, external_id: str = "PRED-MKT-1") -> Market:
    market = Market(
        id=uuid4(),
        platform="kalshi",
        external_id=external_id,
        title="Test market for model perf",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)
    return market


async def _seed_prediction(
    session, market, *, model_id: str = "spread_arb", model_version: str = "v0",
    edge: float = 0.10, predicted_prob: float = 0.60,
) -> Prediction:
    pred = Prediction(
        id=uuid4(),
        market_id=market.id,
        model_id=model_id,
        model_version=model_version,
        predicted_prob=predicted_prob,
        confidence=0.8,
        market_price_at_prediction=predicted_prob - edge,
        edge=edge,
    )
    session.add(pred)
    await session.commit()
    await session.refresh(pred)
    return pred


async def _seed_filled_buy_order(session, market, prediction, *, qty: int = 100, price: float = 0.50):
    order = Order(
        id=uuid4(),
        client_order_id=f"sigil_{uuid4()}",
        platform="kalshi",
        market_id=market.id,
        prediction_id=prediction.id,
        mode="paper",
        side="buy",
        outcome="yes",
        order_type="limit",
        price=price,
        quantity=qty,
        filled_quantity=qty,
        avg_fill_price=price,
        edge_at_entry=0.10,
        status="filled",
    )
    session.add(order)
    await session.commit()
    return order


async def _seed_position(
    session, market, *, status: str, realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0, closed_at: datetime | None = None,
    quantity: int = 100, avg_entry_price: float = 0.50,
):
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=market.id,
        mode="paper",
        outcome="yes",
        quantity=quantity,
        avg_entry_price=avg_entry_price,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        status=status,
        closed_at=closed_at,
    )
    session.add(pos)
    await session.commit()
    return pos


# ---- aggregator unit tests ----------------------------------------------


@pytest.mark.asyncio
async def test_summary_no_data(db_session):
    s = await mp.model_summary(db_session, "spread_arb")
    assert s["state"] == "no_data"
    assert s["predictions_total"] == 0
    assert s["trades_total"] == 0
    assert s["realized_pnl"] == 0.0
    assert s["win_rate"] is None
    assert s["max_drawdown"] is None


@pytest.mark.asyncio
async def test_summary_predictions_only(db_session):
    market = await _seed_market(db_session)
    await _seed_prediction(db_session, market, model_id="spread_arb")

    s = await mp.model_summary(db_session, "spread_arb")
    assert s["state"] == "ok"
    assert s["predictions_total"] == 1
    assert s["predictions_24h"] == 1
    # No order yet, so no trades.
    assert s["trades_total"] == 0
    assert s["last_trade_at"] is None


@pytest.mark.asyncio
async def test_summary_full_pipeline(db_session):
    """Predictions → filled buy order → closed winning position should
    produce trades_total=1, realized_pnl > 0, win_rate=1.0."""
    market = await _seed_market(db_session, external_id="FULL-PIPE-1")
    pred = await _seed_prediction(db_session, market, model_id="spread_arb")
    await _seed_filled_buy_order(db_session, market, pred, qty=100, price=0.50)
    await _seed_position(
        db_session, market,
        status="closed",
        realized_pnl=15.0,
        closed_at=datetime.now(timezone.utc),
    )

    s = await mp.model_summary(db_session, "spread_arb")
    assert s["state"] == "ok"
    assert s["predictions_total"] == 1
    assert s["trades_total"] == 1
    assert s["realized_pnl"] == 15.0
    assert s["win_rate"] == 1.0
    assert s["last_trade_at"] is not None


@pytest.mark.asyncio
async def test_summary_attribution_does_not_leak_across_models(db_session):
    """A position whose buy-order is linked to model A must not show up in
    model B's stats. Different markets keeps the test simple and correct."""
    market_a = await _seed_market(db_session, external_id="A-1")
    market_b = await _seed_market(db_session, external_id="B-1")
    pred_a = await _seed_prediction(db_session, market_a, model_id="spread_arb")
    pred_b = await _seed_prediction(db_session, market_b, model_id="elo_sports")
    await _seed_filled_buy_order(db_session, market_a, pred_a)
    await _seed_filled_buy_order(db_session, market_b, pred_b)
    await _seed_position(
        db_session, market_a, status="closed",
        realized_pnl=20.0, closed_at=datetime.now(timezone.utc),
    )
    await _seed_position(
        db_session, market_b, status="closed",
        realized_pnl=-5.0, closed_at=datetime.now(timezone.utc),
    )

    sa = await mp.model_summary(db_session, "spread_arb")
    sb = await mp.model_summary(db_session, "elo_sports")
    assert sa["realized_pnl"] == 20.0
    assert sb["realized_pnl"] == -5.0
    assert sa["win_rate"] == 1.0
    assert sb["win_rate"] == 0.0


@pytest.mark.asyncio
async def test_equity_curve_and_drawdown(db_session):
    """Three closed positions in chronological order: +10, -15, +8.
    Cumulative: 10, -5, 3. Peak=10, trough=-5 → drawdown=15.

    Use one market per position to dodge the Position unique constraint
    on (platform, market_id, outcome, mode).
    """
    base = datetime.now(timezone.utc) - timedelta(days=3)
    pnls = [10.0, -15.0, 8.0]
    for i, pnl in enumerate(pnls):
        market = await _seed_market(db_session, external_id=f"DD-{i}")
        pred = await _seed_prediction(db_session, market, model_id="spread_arb")
        await _seed_filled_buy_order(db_session, market, pred)
        await _seed_position(
            db_session, market,
            status="closed",
            realized_pnl=pnl,
            closed_at=base + timedelta(days=i),
        )

    curve = await mp.model_equity_curve(db_session, "spread_arb")
    cum = [round(p["cum_pnl"], 4) for p in curve]
    assert cum == [10.0, -5.0, 3.0]

    s = await mp.model_summary(db_session, "spread_arb")
    assert s["max_drawdown"] == 15.0


@pytest.mark.asyncio
async def test_recent_trades_only_returns_this_model(db_session):
    market = await _seed_market(db_session, external_id="RT-1")
    pred = await _seed_prediction(db_session, market, model_id="spread_arb")
    await _seed_filled_buy_order(db_session, market, pred)

    market_b = await _seed_market(db_session, external_id="RT-2")
    pred_b = await _seed_prediction(db_session, market_b, model_id="elo_sports")
    await _seed_filled_buy_order(db_session, market_b, pred_b)

    rows = await mp.model_recent_trades(db_session, "spread_arb")
    assert len(rows) == 1
    assert rows[0]["external_id"] == "RT-1"


@pytest.mark.asyncio
async def test_model_detail_has_all_blocks(db_session):
    market = await _seed_market(db_session, external_id="DET-1")
    pred = await _seed_prediction(db_session, market, model_id="spread_arb")
    await _seed_filled_buy_order(db_session, market, pred)

    detail = await mp.model_detail(db_session, "spread_arb")
    assert detail is not None
    assert detail["model_id"] == "spread_arb"
    assert "summary" in detail
    assert "equity_curve" in detail
    assert "recent_trades" in detail
    assert "recent_predictions" in detail
    assert len(detail["recent_predictions"]) == 1
    assert detail["recent_predictions"][0]["order_id"] is not None


@pytest.mark.asyncio
async def test_model_detail_unknown_returns_none(db_session):
    detail = await mp.model_detail(db_session, "definitely-not-a-model")
    assert detail is None


# ---- HTTP endpoint tests ------------------------------------------------


@pytest.mark.asyncio
async def test_get_models_lists_registered_models(client):
    res = client.get("/api/models")
    assert res.status_code == 200
    body = res.json()
    ids = {m["model_id"] for m in body}
    assert "spread_arb" in ids
    assert "elo_sports" in ids
    spread = next(m for m in body if m["model_id"] == "spread_arb")
    assert spread["display_name"] == "Stat Arb (Cross-Platform)"
    assert "tags" in spread
    assert "summary" in spread
    # No data seeded → no_data state
    assert spread["summary"]["state"] == "no_data"


@pytest.mark.asyncio
async def test_get_model_detail_404(client):
    res = client.get("/api/models/definitely-not-a-model")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_model_detail_with_seeded_data(client, db_session):
    market = await _seed_market(db_session, external_id="HTTP-1")
    pred = await _seed_prediction(db_session, market, model_id="spread_arb")
    await _seed_filled_buy_order(db_session, market, pred)
    await _seed_position(
        db_session, market,
        status="closed",
        realized_pnl=12.5,
        closed_at=datetime.now(timezone.utc),
    )

    res = client.get("/api/models/spread_arb")
    assert res.status_code == 200
    body = res.json()
    assert body["model_id"] == "spread_arb"
    assert body["summary"]["state"] == "ok"
    assert body["summary"]["trades_total"] == 1
    assert body["summary"]["realized_pnl"] == 12.5
    assert len(body["equity_curve"]) == 1
    assert len(body["recent_trades"]) == 1
    assert len(body["recent_predictions"]) == 1
