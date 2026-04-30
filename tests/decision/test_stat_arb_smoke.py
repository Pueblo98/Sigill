"""Smoke tests for the stat-arb scanner — no live API calls."""

from __future__ import annotations

import pytest


def test_stat_arb_imports():
    from sigil.decision.stat_arb import (
        ArbEngine,
        ArbOpportunity,
        MarketSnapshot,
        StatArbScanner,
    )

    assert StatArbScanner is not None
    assert ArbEngine is not None
    assert ArbOpportunity is not None
    assert MarketSnapshot is not None


def test_stat_arb_scanner_constructs_with_defaults():
    from sigil.decision.stat_arb import StatArbScanner

    scanner = StatArbScanner()
    assert scanner.engine is not None
    assert scanner.fuzzy_threshold > 0


def test_stat_arb_scanner_constructs_with_custom_thresholds():
    from sigil.decision.stat_arb import StatArbScanner

    scanner = StatArbScanner(min_arb_profit=0.03, min_stat_divergence=0.07, fuzzy_threshold=85.0)
    assert scanner.engine.min_arb_profit == pytest.approx(0.03)
    assert scanner.engine.min_stat_divergence == pytest.approx(0.07)
    assert scanner.fuzzy_threshold == pytest.approx(85.0)


def test_module_docstring_calls_out_display_only_per_1c():
    """REVIEW-DECISIONS.md 1C says the scanner is display-only — make sure the
    note actually lives in the module docstring so future maintainers see it."""
    from sigil.decision import stat_arb

    assert stat_arb.__doc__ is not None
    doc = stat_arb.__doc__.lower()
    assert "display-only" in doc or "display only" in doc
    assert "1c" in doc


def test_decision_package_exports():
    from sigil import decision

    expected = {
        "DecisionEngine",
        "compute_edge",
        "should_trade",
        "DrawdownState",
        "current_state",
        "position_size_multiplier",
        "StatArbScanner",
        "ArbOpportunity",
    }
    assert expected.issubset(set(decision.__all__))
    # The old superseded class should no longer be exported.
    assert "ArbDetector" not in decision.__all__
