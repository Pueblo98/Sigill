"""cross_platform_spreads widget — live OddsPipe spreads in the dashboard."""
from __future__ import annotations

import pytest
from httpx import Response
from markupsafe import Markup

from sigil.config import config
from sigil.dashboard.widgets.cross_platform_spreads import (
    CrossPlatformSpreadsConfig,
    CrossPlatformSpreadsWidget,
    SpreadRow,
)


def _spread_item(*, score, poly_id, kalshi_id, poly_yes, kalshi_yes, poly_title="P", kalshi_title="K"):
    yes_diff = abs(poly_yes - kalshi_yes)
    direction = "polymarket_higher" if poly_yes > kalshi_yes else "kalshi_higher"
    return {
        "match_id": 1,
        "score": score,
        "polymarket": {
            "market_id": poly_id, "title": poly_title, "yes_price": poly_yes,
            "no_price": 1 - poly_yes, "volume_usd": 50000.0, "url": "x",
        },
        "kalshi": {
            "market_id": kalshi_id, "title": kalshi_title, "yes_price": kalshi_yes,
            "no_price": 1 - kalshi_yes, "volume_usd": 25000.0, "url": "y",
        },
        "spread": {"yes_diff": yes_diff, "direction": direction,
                   "price_divergence": True, "note": ""},
    }


@pytest.fixture(autouse=True)
def _api_key():
    """Inject a fake OddsPipe key so the widget actually fetches.
    Restored after each test."""
    saved = config.ODDSPIPE_API_KEY
    config.ODDSPIPE_API_KEY = "test-key"
    yield
    config.ODDSPIPE_API_KEY = saved


def _widget(**overrides):
    cfg = CrossPlatformSpreadsConfig(type="cross_platform_spreads", cache="5m", **overrides)
    return CrossPlatformSpreadsWidget(cfg)


async def test_returns_empty_when_no_api_key(respx_mock):
    config.ODDSPIPE_API_KEY = None
    w = _widget()
    rows = await w.fetch(session=None)
    assert rows == []


async def test_filters_max_yes_diff(respx_mock):
    # Two matches: one within max_yes_diff, one beyond.
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(score=99, poly_id=1, kalshi_id=2,
                         poly_yes=0.50, kalshi_yes=0.30),  # diff=0.20 (kept)
            _spread_item(score=99, poly_id=3, kalshi_id=4,
                         poly_yes=0.90, kalshi_yes=0.10),  # diff=0.80 (drop)
        ]})
    )
    rows = await _widget(max_yes_diff=0.30).fetch(session=None)
    assert len(rows) == 1
    assert rows[0].yes_diff == pytest.approx(0.20)


async def test_sorts_by_abs_yes_diff_desc(respx_mock):
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [
            _spread_item(score=99, poly_id=1, kalshi_id=2,
                         poly_yes=0.55, kalshi_yes=0.50),  # 0.05
            _spread_item(score=99, poly_id=3, kalshi_id=4,
                         poly_yes=0.55, kalshi_yes=0.30),  # 0.25
            _spread_item(score=99, poly_id=5, kalshi_id=6,
                         poly_yes=0.50, kalshi_yes=0.40),  # 0.10
        ]})
    )
    rows = await _widget(max_yes_diff=0.50).fetch(session=None)
    diffs = [r.yes_diff for r in rows]
    assert diffs == sorted(diffs, reverse=True)


async def test_renders_empty_state():
    w = _widget()
    out = w.render([])
    assert "No high-confidence cross-platform spreads" in str(out)
    assert isinstance(out, Markup)


async def test_renders_table_with_links():
    rows = [SpreadRow(
        question="Will Mary Peltola win the 2026 Alaska Senate race?",
        score=98.0,
        yes_diff=0.08,
        direction="polymarket_higher",
        kalshi_yes=0.60,
        kalshi_vol=12345.0,
        kalshi_url="https://kalshi.com/markets/KX-PELTOLA",
        polymarket_yes=0.68,
        polymarket_vol=98765.0,
        polymarket_url="https://polymarket.com",
    )]
    out = str(_widget().render(rows))
    assert "Mary Peltola" in out
    assert "0.600" in out
    assert "0.680" in out
    assert "$12,345" in out
    assert "$98,765" in out
    assert "kalshi.com/markets/KX-PELTOLA" in out
    assert "98" in out  # score


async def test_skips_match_missing_a_side(respx_mock):
    """Spread item with only one platform side -> drop."""
    item = _spread_item(score=99, poly_id=1, kalshi_id=2,
                        poly_yes=0.50, kalshi_yes=0.30)
    item.pop("kalshi")  # only polymarket side present
    respx_mock.get("https://oddspipe.com/v1/spreads").mock(
        return_value=Response(200, json={"items": [item]})
    )
    rows = await _widget(max_yes_diff=0.50).fetch(session=None)
    assert rows == []
