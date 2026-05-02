"""Models card-grid view builder — :mod:`sigil.dashboard.views.models_list`.

The /models route is a thin wrapper; we exercise the context builder
directly against an in-memory SQLite session, mirroring the pattern in
test_markets_list_route.py / test_model_detail_route.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

# Importing this module registers the spread_arb + elo_sports ModelDefs
# in the registry (last write wins on duplicate model_id, so re-imports
# under pytest are safe).
import sigil.signals.spread_arb  # noqa: F401
import sigil.signals.elo_sports  # noqa: F401
from sigil.dashboard.views.models_list import build_context
from sigil.models import Market, Order, Position, Prediction


async def _seed_market(session, *, ext_id: str = "KX-MODELS") -> Market:
    market = Market(
        id=uuid4(),
        platform="kalshi",
        external_id=ext_id,
        title=f"Will {ext_id}?",
        taxonomy_l1="sports",
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.commit()
    await session.refresh(market)
    return market


async def _seed_prediction(
    session,
    *,
    market: Market,
    model_id: str = "spread_arb",
    edge: float = 0.10,
    created_at: datetime | None = None,
) -> Prediction:
    pred = Prediction(
        id=uuid4(),
        market_id=market.id,
        model_id=model_id,
        model_version="v0",
        predicted_prob=0.60,
        confidence=0.80,
        market_price_at_prediction=0.50,
        edge=edge,
    )
    if created_at is not None:
        pred.created_at = created_at
    session.add(pred)
    await session.commit()
    await session.refresh(pred)
    return pred


async def _seed_order_position(
    session,
    *,
    market: Market,
    prediction: Prediction,
    realized_pnl: float = 5.0,
    status: str = "closed",
) -> tuple[Order, Position]:
    order = Order(
        id=uuid4(),
        platform="kalshi",
        market_id=market.id,
        prediction_id=prediction.id,
        client_order_id=f"co-{uuid4().hex[:6]}",
        external_order_id=f"ex-{uuid4().hex[:6]}",
        mode="paper",
        side="buy",
        outcome="yes",
        order_type="limit",
        price=0.50,
        quantity=10,
        filled_quantity=10,
        avg_fill_price=0.50,
        fees=0.0,
        status="filled",
    )
    session.add(order)
    pos = Position(
        id=uuid4(),
        platform="kalshi",
        market_id=market.id,
        outcome="yes",
        mode="paper",
        quantity=10,
        avg_entry_price=0.50,
        current_price=0.55,
        realized_pnl=realized_pnl,
        unrealized_pnl=0.0,
        status=status,
        opened_at=datetime.now(timezone.utc),
        closed_at=datetime.now(timezone.utc) if status == "closed" else None,
    )
    session.add(pos)
    await session.commit()
    return order, pos


async def test_registry_models_appear_even_with_no_data(session):
    ctx = await build_context(session)
    # The two registered models from sigil.signals are visible.
    model_ids = {c.model_id for c in ctx.cards}
    assert "spread_arb" in model_ids
    assert "elo_sports" in model_ids
    # All cards report no_data summaries.
    assert all(c.summary.get("state") == "no_data" for c in ctx.cards)


async def test_card_status_idle_when_enabled_but_no_recent_predictions(session):
    ctx = await build_context(session)
    spread_arb = next(c for c in ctx.cards if c.model_id == "spread_arb")
    assert spread_arb.enabled is True
    assert spread_arb.status == "idle"


async def test_card_status_live_with_recent_prediction(session):
    market = await _seed_market(session, ext_id="KX-LIVE")
    # Prediction within the last 24h → status should flip to "live".
    await _seed_prediction(
        session, market=market, model_id="spread_arb",
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    ctx = await build_context(session)
    spread_arb = next(c for c in ctx.cards if c.model_id == "spread_arb")
    assert spread_arb.status == "live"
    assert spread_arb.summary["predictions_24h"] >= 1


async def test_card_summary_reflects_closed_position(session):
    market = await _seed_market(session, ext_id="KX-PNL")
    pred = await _seed_prediction(session, market=market, model_id="spread_arb")
    await _seed_order_position(
        session, market=market, prediction=pred, realized_pnl=12.5, status="closed"
    )

    ctx = await build_context(session)
    spread_arb = next(c for c in ctx.cards if c.model_id == "spread_arb")
    assert spread_arb.summary["state"] == "ok"
    assert spread_arb.summary["trades_total"] == 1
    assert spread_arb.summary["realized_pnl"] == pytest.approx(12.5, rel=1e-6)


async def test_metadata_passed_through_from_registry(session):
    ctx = await build_context(session)
    spread_arb = next(c for c in ctx.cards if c.model_id == "spread_arb")
    assert spread_arb.display_name == "Stat Arb (Cross-Platform)"
    assert spread_arb.version == "v0"
    assert "arbitrage" in spread_arb.tags


async def test_total_matches_card_count(session):
    ctx = await build_context(session)
    assert ctx.total == len(ctx.cards)
    assert ctx.total >= 2  # spread_arb + elo_sports both registered
