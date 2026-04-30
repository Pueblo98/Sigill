"""Tests for the signal_queue widget."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sigil.dashboard.widgets.signal_queue import (
    SignalQueueConfig,
    SignalQueueWidget,
)
from sigil.models import Prediction


def _make_widget(*, limit: int = 5, min_edge: float = 0.05) -> SignalQueueWidget:
    cfg = SignalQueueConfig(
        type="signal_queue", cache="30s", limit=limit, min_edge=min_edge
    )
    return SignalQueueWidget(cfg)


@pytest.mark.asyncio
async def test_empty_state(session):
    w = _make_widget()
    data = await w.fetch(session)
    assert data == []
    out = w.render(data)
    assert "No signals above edge threshold." in out


@pytest.mark.asyncio
async def test_filter_by_min_edge(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add_all(
        [
            Prediction(
                market_id=sample_market.id,
                model_id="alpha",
                model_version="1",
                predicted_prob=0.6,
                edge=0.02,
                created_at=now - timedelta(minutes=5),
            ),
            Prediction(
                market_id=sample_market.id,
                model_id="alpha",
                model_version="1",
                predicted_prob=0.7,
                edge=0.10,
                created_at=now - timedelta(minutes=4),
            ),
            Prediction(
                market_id=sample_market.id,
                model_id="alpha",
                model_version="1",
                predicted_prob=0.8,
                edge=0.20,
                created_at=now,
            ),
        ]
    )
    await session.commit()

    w = _make_widget(min_edge=0.05)
    data = await w.fetch(session)
    assert len(data) == 2
    # Sorted by created_at DESC.
    assert data[0].predicted_prob == 0.8
    assert data[1].predicted_prob == 0.7


@pytest.mark.asyncio
async def test_limit_caps_results(session, sample_market):
    now = datetime.now(timezone.utc)
    for i in range(10):
        session.add(
            Prediction(
                market_id=sample_market.id,
                model_id="alpha",
                model_version="1",
                predicted_prob=0.6,
                edge=0.10,
                created_at=now - timedelta(minutes=i),
            )
        )
    await session.commit()

    w = _make_widget(limit=3)
    data = await w.fetch(session)
    assert len(data) == 3


@pytest.mark.asyncio
async def test_render_uses_market_title(session, sample_market):
    now = datetime.now(timezone.utc)
    session.add(
        Prediction(
            market_id=sample_market.id,
            model_id="alpha",
            model_version="1",
            predicted_prob=0.65,
            market_price_at_prediction=0.50,
            edge=0.15,
            created_at=now,
        )
    )
    await session.commit()

    w = _make_widget()
    data = await w.fetch(session)
    out = w.render(data)
    assert sample_market.title in out
    assert "alpha" in out
    assert "+0.150" in out


def test_filters_block_hoists_into_top_level():
    cfg = SignalQueueConfig(
        type="signal_queue",
        cache="30s",
        filters={"min_edge": 0.20, "limit": 3},  # hoisted by validator
    )
    assert cfg.min_edge == 0.20
    assert cfg.limit == 3
