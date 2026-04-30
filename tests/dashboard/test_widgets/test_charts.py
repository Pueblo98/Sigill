"""Unit tests for the matplotlib SVG chart helpers.

We do not pixel-compare matplotlib output. We assert the helper:
- returns a string containing ``<svg`` and ``</svg>``
- does not crash on empty inputs (renders the placeholder)
- accepts a custom theme override
- enforces equal-length predicted/observed for the calibration curve
"""

from __future__ import annotations

import pytest

from sigil.dashboard.config import Theme
from sigil.dashboard.widgets import charts


@pytest.fixture
def theme() -> Theme:
    return Theme(
        background="#000000",
        surface="#111111",
        accent="#ffffff",
        positive="#00ff00",
        negative="#ff0000",
    )


def _is_svg(s: str) -> bool:
    return "<svg" in s and "</svg>" in s


def test_calibration_curve_basic(theme):
    svg = charts.render_calibration_curve_svg([0.1, 0.5, 0.9], [0.0, 0.5, 1.0], theme=theme)
    assert _is_svg(svg)
    assert "viewBox" in svg


def test_calibration_curve_equal_length_required():
    with pytest.raises(ValueError):
        charts.render_calibration_curve_svg([0.1, 0.5], [0.0])


def test_calibration_curve_empty_returns_placeholder():
    svg = charts.render_calibration_curve_svg([], [])
    assert _is_svg(svg)
    assert "no calibration data" in svg


def test_roi_curve_basic(theme):
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    curve = [(base + timedelta(days=i), 5000.0 + i * 25) for i in range(8)]
    svg = charts.render_roi_curve_svg(curve, theme=theme)
    assert _is_svg(svg)
    assert "viewBox" in svg


def test_roi_curve_empty_returns_placeholder():
    svg = charts.render_roi_curve_svg([])
    assert _is_svg(svg)
    assert "no equity points" in svg


def test_brier_sparkline_basic(theme):
    svg = charts.render_brier_sparkline_svg([0.20, 0.18, 0.22, 0.19, 0.17], theme=theme)
    assert _is_svg(svg)
    assert "viewBox" in svg


def test_brier_sparkline_empty_returns_placeholder():
    svg = charts.render_brier_sparkline_svg([])
    assert _is_svg(svg)
    assert "no brier history" in svg


def test_set_theme_overrides_default(theme):
    charts.set_theme(theme)
    try:
        # When no explicit theme is passed, the configured theme should drive colors.
        svg = charts.render_calibration_curve_svg([], [])
        # Empty -> placeholder; placeholder uses theme.surface for the background rect.
        assert theme.surface in svg
    finally:
        # Reset to default so other tests aren't affected.
        charts.set_theme(charts._DEFAULT_THEME)


def test_svg_strips_explicit_dimensions(theme):
    svg = charts.render_brier_sparkline_svg([0.1, 0.2, 0.3], theme=theme)
    head = svg[: svg.find(">") + 1]
    assert ' width="' not in head
    assert ' height="' not in head
