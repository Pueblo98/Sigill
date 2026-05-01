"""Validate the checked-in dashboard.yaml at the repo root.

Operators edit this file directly. If a typo lands here, every page render
explodes — so we keep a tight feedback loop in the test suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import sigil.dashboard.widgets  # noqa: F401  ensure registry populated
from sigil.dashboard.config import DashboardConfig
from sigil.dashboard.loader import build_widget_instances, load_dashboard


# Walk up from this file: tests/dashboard/test_dashboard_yaml.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DASHBOARD_YAML = REPO_ROOT / "dashboard.yaml"


def test_dashboard_yaml_exists():
    assert DASHBOARD_YAML.exists(), f"missing dashboard.yaml at {DASHBOARD_YAML}"


def test_dashboard_yaml_parses_cleanly():
    cfg = load_dashboard(DASHBOARD_YAML)
    assert isinstance(cfg, DashboardConfig)


def test_dashboard_yaml_has_expected_pages():
    cfg = load_dashboard(DASHBOARD_YAML)
    names = [p.name for p in cfg.pages]
    assert names == ["command-center", "markets", "spreads", "models", "health"]


def test_dashboard_yaml_command_center_is_default():
    cfg = load_dashboard(DASHBOARD_YAML)
    defaults = [p for p in cfg.pages if p.default]
    assert len(defaults) == 1
    assert defaults[0].name == "command-center"


def test_dashboard_yaml_widget_instances_build():
    """Every widget referenced in the YAML must be registered + instantiable."""
    cfg = load_dashboard(DASHBOARD_YAML)
    widgets = build_widget_instances(cfg)
    # command-center: bankroll_summary, signal_queue, system_health_strip, recent_activity
    # markets: market_list
    # spreads: cross_platform_spreads
    # models: open_positions
    # health: system_health_strip, recent_activity
    assert len(widgets) == 9
    types = [w.type for w in widgets]
    assert types[:4] == [
        "bankroll_summary",
        "signal_queue",
        "system_health_strip",
        "recent_activity",
    ]
    assert "cross_platform_spreads" in types


def test_dashboard_yaml_theme_present():
    cfg = load_dashboard(DASHBOARD_YAML)
    assert cfg.theme.background.startswith("#")
    assert cfg.theme.accent.startswith("#")
