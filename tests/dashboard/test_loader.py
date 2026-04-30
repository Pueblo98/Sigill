"""Tests for loader + env-var interpolation + YAML schema."""

from __future__ import annotations

from pathlib import Path

import pytest

import sigil.dashboard.widgets  # noqa: F401  ensure registry populated
from sigil.dashboard.config import DashboardConfig, interpolate
from sigil.dashboard.loader import build_widget_instances, load_dashboard


_EXAMPLE_YAML = """
pages:
  - name: command-center
    title: Command Center
    default: true
    columns:
      - size: full
        widgets:
          - type: bankroll_summary
            cache: 1m
          - type: signal_queue
            cache: 30s
            limit: 5
      - size: small
        widgets:
          - type: system_health_strip
            cache: 1m
          - type: recent_activity
            cache: 30s
            limit: 20

  - name: markets
    title: Market Explorer
    columns:
      - size: full
        widgets:
          - type: market_list
            cache: 1m
            filters:
              min_edge: 0.05
              platform: kalshi
            sort: edge_desc
            limit: 50

theme:
  background: "#1b1b1d"
  surface: "#201f21"
  accent: "#d2bbff"
  positive: "#10b981"
  negative: "#ef4444"
"""


def test_load_example_yaml(tmp_path: Path):
    p = tmp_path / "dashboard.yaml"
    p.write_text(_EXAMPLE_YAML, encoding="utf-8")
    cfg = load_dashboard(p)
    assert isinstance(cfg, DashboardConfig)
    assert len(cfg.pages) == 2
    assert cfg.pages[0].default is True
    assert cfg.theme.background == "#1b1b1d"


def test_build_widget_instances_from_example_yaml(tmp_path: Path):
    p = tmp_path / "dashboard.yaml"
    p.write_text(_EXAMPLE_YAML, encoding="utf-8")
    cfg = load_dashboard(p)
    widgets = build_widget_instances(cfg)
    types = [w.type for w in widgets]
    assert types == [
        "bankroll_summary",
        "signal_queue",
        "system_health_strip",
        "recent_activity",
        "market_list",
    ]


def test_unknown_widget_type_raises(tmp_path: Path):
    yaml_text = """
pages:
  - name: p
    title: P
    columns:
      - size: full
        widgets:
          - type: not_a_real_widget
            cache: 1m
theme:
  background: "#000000"
  surface: "#111111"
  accent: "#222222"
  positive: "#10b981"
  negative: "#ef4444"
"""
    p = tmp_path / "bad.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_dashboard(p)
    with pytest.raises(ValueError, match="unknown widget type"):
        build_widget_instances(cfg)


def test_invalid_theme_color(tmp_path: Path):
    yaml_text = """
pages: []
theme:
  background: "not-a-color"
  surface: "#111111"
  accent: "#222222"
  positive: "#10b981"
  negative: "#ef4444"
"""
    p = tmp_path / "bad.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(Exception):
        load_dashboard(p)


def test_multiple_default_pages_rejected(tmp_path: Path):
    yaml_text = """
pages:
  - name: a
    title: A
    default: true
    columns: []
  - name: b
    title: B
    default: true
    columns: []
theme:
  background: "#000000"
  surface: "#111111"
  accent: "#222222"
  positive: "#10b981"
  negative: "#ef4444"
"""
    p = tmp_path / "bad.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(Exception):
        load_dashboard(p)


def test_interpolate_resolves_env(monkeypatch):
    monkeypatch.setenv("SIGIL_TEST_VAR", "hello")
    assert interpolate("x=${SIGIL_TEST_VAR}") == "x=hello"


def test_interpolate_missing_env_raises(monkeypatch):
    monkeypatch.delenv("SIGIL_TEST_MISSING", raising=False)
    with pytest.raises(KeyError):
        interpolate("x=${SIGIL_TEST_MISSING}")


def test_interpolate_no_vars_passthrough():
    assert interpolate("plain string $not_a_var") == "plain string $not_a_var"


def test_loader_injects_theme_onto_every_widget(tmp_path: Path):
    """TODO-6: every widget instance should carry the dashboard theme so
    chart widgets can pull `self.theme.accent` / etc. without a module-level
    global."""
    p = tmp_path / "dashboard.yaml"
    p.write_text(_EXAMPLE_YAML, encoding="utf-8")
    cfg = load_dashboard(p)
    widgets = build_widget_instances(cfg)
    assert widgets, "example YAML should yield widgets"
    for w in widgets:
        assert w.theme is cfg.theme, (
            f"{w.type} did not receive the dashboard theme"
        )


def test_load_with_env_var(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SIGIL_PAGE_NAME", "command-center")
    yaml_text = """
pages:
  - name: ${SIGIL_PAGE_NAME}
    title: Center
    columns: []
theme:
  background: "#000000"
  surface: "#111111"
  accent: "#222222"
  positive: "#10b981"
  negative: "#ef4444"
"""
    p = tmp_path / "dash.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_dashboard(p)
    assert cfg.pages[0].name == "command-center"
