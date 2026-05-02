"""Kalshi event_ticker -> taxonomy_l1 mapping.

Kalshi's official /events/{ticker} endpoint is auth-gated, so until we
have creds, ``sigil.ingestion.kalshi._infer_category_from_ticker`` walks
a hardcoded prefix table. These cases pin the dominant series prefixes
seen in production so accidental edits to the table don't silently
re-bucket markets back to ``"general"``.
"""
from __future__ import annotations

import pytest

from sigil.ingestion.kalshi import _infer_category_from_ticker


@pytest.mark.parametrize(
    "ticker,expected",
    [
        # Sports prefixes
        ("KXNBAGAME-26MAY01CLETOR-CLE", "sports"),
        ("KXNFLGAME-26JAN01-KC", "sports"),
        ("KXMLB-25SEP15-LAD", "sports"),
        ("KXEPL-26MAY-CHELSEA", "sports"),
        ("KXUFC-300-MCG", "sports"),
        ("KXNCAAB-26MAR15-DUKE", "sports"),
        ("KXNCAAF-26JAN-OSU", "sports"),
        # Economics
        ("KXFEDDEC-DEC25-CUT", "economics"),
        ("KXCPI-25NOV-OVER3", "economics"),
        ("KXGDP-Q4-OVER2", "economics"),
        # Crypto
        ("KXBTC-25DEC-OVER100K", "crypto"),
        ("KXETH-26JAN-OVER5K", "crypto"),
        # Politics
        ("KXPRES-2028-DEM", "politics"),
        ("KXSENATE-AK-PELTOLA", "politics"),
        # Climate / weather
        ("KXHIGHNY-25JUL-OVER90", "climate"),
        ("KXHURRICANE-25SEP-FL", "climate"),
        # Tech
        ("KXAI-26JAN-OPENAI", "tech"),
        # Unknown / non-matching prefix falls back to general
        ("KXFOOBAR-25-UNKNOWN", "general"),
        ("RANDOM-TICKER", "general"),
    ],
)
def test_category_inference_from_ticker(ticker: str, expected: str):
    assert _infer_category_from_ticker(None, ticker) == expected


def test_event_ticker_takes_precedence_when_provided():
    # _infer_category_from_ticker accepts (event_ticker, ticker); event
    # wins. Useful when the market's full ticker is exotic but the event
    # carries the canonical prefix.
    assert _infer_category_from_ticker("KXNFLGAME-26JAN", "WEIRD-LEG") == "sports"


def test_empty_inputs_return_general():
    assert _infer_category_from_ticker(None, None) == "general"
    assert _infer_category_from_ticker("", "") == "general"


def test_longest_prefix_wins():
    # KXNCAAF should hit "sports" via that exact prefix, not be ambiguous
    # against any shorter "KXN..." would-be prefix.
    assert _infer_category_from_ticker(None, "KXNCAAF-X") == "sports"
