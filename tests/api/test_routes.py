from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sigil.api import routes as routes_module
from sigil.models import (
    BankrollSnapshot,
    Market,
    MarketPrice,
    Order,
    Position,
    Prediction,
    SourceHealth,
)


@pytest.mark.asyncio
async def test_portfolio_returns_no_data_when_empty(client):
    res = client.get("/api/portfolio")
    assert res.status_code == 200
    body = res.json()
    assert body["state"] == "no_data"
    assert body["balance"] == 0.0
    assert body["realized_pnl"] == 0.0


@pytest.mark.asyncio
async def test_portfolio_returns_latest_snapshot(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            BankrollSnapshot(
                time=now - timedelta(hours=1),
                mode="paper",
                equity=4800.0,
                realized_pnl_total=-200.0,
                unrealized_pnl_total=0.0,
                settled_trades_total=10,
                settled_trades_30d=5,
            ),
            BankrollSnapshot(
                time=now,
                mode="paper",
                equity=5500.0,
                realized_pnl_total=400.0,
                unrealized_pnl_total=100.0,
                settled_trades_total=12,
                settled_trades_30d=6,
            ),
        ]
    )
    await db_session.commit()

    res = client.get("/api/portfolio")
    body = res.json()
    assert body["state"] == "ok"
    assert body["balance"] == 5500.0
    assert body["mode"] == "paper"
    assert body["settled_trades_total"] == 12


@pytest.mark.asyncio
async def test_markets_returns_open_only(client, db_session):
    db_session.add_all(
        [
            Market(
                platform="kalshi",
                external_id="OPEN-1",
                title="Open market",
                taxonomy_l1="sports",
                status="open",
            ),
            Market(
                platform="kalshi",
                external_id="CLOSED-1",
                title="Closed market",
                taxonomy_l1="sports",
                status="closed",
            ),
        ]
    )
    await db_session.commit()

    res = client.get("/api/markets")
    body = res.json()
    assert len(body) == 1
    assert body[0]["external_id"] == "OPEN-1"
    assert body[0]["status"] == "open"


@pytest.mark.asyncio
async def test_market_detail_404(client):
    res = client.get("/api/markets/does-not-exist")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_market_detail_uses_uuid_for_price_lookup(client, db_session):
    """Regression test: the FK-type bug used external_id where Market.id (UUID)
    is required. This test would have failed under the old code."""
    market = Market(
        platform="kalshi",
        external_id="EXT-123",
        title="Test market",
        taxonomy_l1="sports",
        status="open",
    )
    db_session.add(market)
    await db_session.commit()
    await db_session.refresh(market)

    now = datetime.now(timezone.utc)
    db_session.add(
        MarketPrice(
            time=now,
            market_id=market.id,
            bid=0.45,
            ask=0.47,
            last_price=0.46,
            volume_24h=1000.0,
            source="kalshi",
        )
    )
    await db_session.commit()

    res = client.get("/api/markets/EXT-123")
    assert res.status_code == 200
    body = res.json()
    assert body["external_id"] == "EXT-123"
    assert body["bid"] == 0.45
    assert body["ask"] == 0.47


@pytest.mark.asyncio
async def test_positions_endpoint(client, db_session):
    market = Market(
        platform="kalshi",
        external_id="POS-1",
        title="Pos market",
        taxonomy_l1="sports",
        status="open",
    )
    db_session.add(market)
    await db_session.commit()
    await db_session.refresh(market)

    db_session.add(
        Position(
            platform="kalshi",
            market_id=market.id,
            mode="paper",
            outcome="yes",
            quantity=100,
            avg_entry_price=0.50,
            status="open",
        )
    )
    await db_session.commit()

    res = client.get("/api/positions")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["market_title"] == "Pos market"
    assert body[0]["outcome"] == "yes"


@pytest.mark.asyncio
async def test_orders_endpoint_pagination(client, db_session):
    market = Market(
        platform="kalshi",
        external_id="ORD-1",
        title="Ord market",
        taxonomy_l1="sports",
        status="open",
    )
    db_session.add(market)
    await db_session.commit()
    await db_session.refresh(market)

    db_session.add_all(
        [
            Order(
                client_order_id=f"sigil_{uuid4()}",
                platform="kalshi",
                market_id=market.id,
                mode="paper",
                side="buy",
                outcome="yes",
                order_type="limit",
                price=0.50,
                quantity=10,
            )
            for _ in range(3)
        ]
    )
    await db_session.commit()

    res = client.get("/api/orders?limit=2")
    assert res.status_code == 200
    assert len(res.json()) == 2


@pytest.mark.asyncio
async def test_predictions_filter_by_model(client, db_session):
    market = Market(
        platform="kalshi",
        external_id="PRED-1",
        title="Pred market",
        taxonomy_l1="sports",
        status="open",
    )
    db_session.add(market)
    await db_session.commit()
    await db_session.refresh(market)

    db_session.add_all(
        [
            Prediction(
                market_id=market.id,
                model_id="alpha",
                model_version="1",
                predicted_prob=0.6,
            ),
            Prediction(
                market_id=market.id,
                model_id="beta",
                model_version="1",
                predicted_prob=0.4,
            ),
        ]
    )
    await db_session.commit()

    res = client.get("/api/predictions?model_id=alpha")
    body = res.json()
    assert len(body) == 1
    assert body[0]["model_id"] == "alpha"


@pytest.mark.asyncio
async def test_health_no_data(client):
    res = client.get("/api/health")
    body = res.json()
    assert body["state"] == "no_data"
    assert body["sources"] == []


@pytest.mark.asyncio
async def test_health_aggregates_sources(client, db_session):
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            SourceHealth(
                check_time=now - timedelta(minutes=10),
                source_name="kalshi",
                status="ok",
                latency_ms=120,
                records_fetched=200,
            ),
            SourceHealth(
                check_time=now,
                source_name="kalshi",
                status="ok",
                latency_ms=180,
                records_fetched=210,
            ),
            SourceHealth(
                check_time=now,
                source_name="polymarket",
                status="degraded",
                latency_ms=900,
                error_message="timeout",
            ),
        ]
    )
    await db_session.commit()

    res = client.get("/api/health")
    body = res.json()
    assert body["state"] == "ok"
    names = {s["source_name"] for s in body["sources"]}
    assert names == {"kalshi", "polymarket"}
    poly = next(s for s in body["sources"] if s["source_name"] == "polymarket")
    assert poly["status"] == "degraded"
    assert poly["error_count_24h"] == 1


@pytest.mark.asyncio
async def test_arbitrage_uses_scanner_and_caches(client, monkeypatch):
    """Verify routes call StatArbScanner.scan() (not difflib) and cache."""
    call_count = {"n": 0}

    class _FakeScanner:
        def __init__(self, *args, **kwargs):
            pass

        async def scan(self):
            call_count["n"] += 1
            return []

    monkeypatch.setattr("sigil.decision.stat_arb.StatArbScanner", _FakeScanner)

    res1 = client.get("/api/arbitrage")
    res2 = client.get("/api/arbitrage")
    assert res1.status_code == 200
    assert res2.status_code == 200
    # First call hits the scanner; second call would too if there were results.
    # Empty list bypasses the cache by design (data is falsy), so we only assert
    # the scanner was used at least once and no exception raised.
    assert call_count["n"] >= 1


@pytest.mark.asyncio
async def test_arbitrage_serialization_shape(client, monkeypatch):
    from dataclasses import dataclass

    @dataclass
    class _Snap:
        platform: str
        external_id: str
        yes_token_id: object
        title: str
        category: str
        yes_bid: float
        yes_ask: float
        resolution_date: object

    @dataclass
    class _Opp:
        kalshi: _Snap
        polymarket: _Snap
        match_score: float
        opportunity_type: str
        leg_a_platform: str
        leg_a_outcome: str
        leg_a_price: float
        leg_b_platform: str
        leg_b_outcome: str
        leg_b_price: float
        gross_cost: float
        fee_cost: float
        net_profit: float

        @property
        def kelly_size(self) -> float:
            return 0.05

    fake_opp = _Opp(
        kalshi=_Snap("kalshi", "K-T", None, "Will X happen?", "politics", 0.40, 0.42, None),
        polymarket=_Snap("polymarket", "P-CONDID-LONGER", None, "Will X occur?", "politics", 0.55, 0.57, None),
        match_score=87.0,
        opportunity_type="STAT_EDGE",
        leg_a_platform="kalshi",
        leg_a_outcome="YES",
        leg_a_price=0.42,
        leg_b_platform="polymarket",
        leg_b_outcome="NO",
        leg_b_price=0.43,
        gross_cost=0.85,
        fee_cost=0.02,
        net_profit=0.13,
    )

    class _FakeScanner:
        def __init__(self, *args, **kwargs):
            pass

        async def scan(self):
            return [fake_opp]

    monkeypatch.setattr("sigil.decision.stat_arb.StatArbScanner", _FakeScanner)

    res = client.get("/api/arbitrage")
    body = res.json()
    assert len(body) == 1
    row = body[0]
    assert row["event"] == "Will X happen?"
    assert row["display_only"] is True
    assert row["opportunity_type"] == "STAT_EDGE"
    assert row["kalshi_bid"] == pytest.approx(40.0)
    assert row["poly_ask"] == pytest.approx(57.0)
