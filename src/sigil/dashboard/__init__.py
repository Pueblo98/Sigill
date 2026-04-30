"""Sigil dashboard package.

Glance-inspired Python dashboard. Pages -> columns -> widgets, each widget
owns its fetcher with a TTL cache and exponential backoff. Server-rendered
HTML via Markup-returning render() methods. Background refresh via
APScheduler. See plan: polished-crafting-feigenbaum.md.

Phase 5 lane F1 owns the framework + 6 read-only widgets. Lane F2 adds the
chart-rendering widgets, lane F3 wires Jinja2 + FastAPI mounting.
"""

from sigil.dashboard.widget import (
    Widget,
    WidgetBase,
    WIDGET_REGISTRY,
    register_widget,
)
from sigil.dashboard.cache import WidgetCache, parse_ttl
from sigil.dashboard.config import (
    Column,
    DashboardConfig,
    Page,
    Theme,
    WidgetConfig,
    interpolate,
)
from sigil.dashboard.loader import build_widget_instances, load_dashboard
from sigil.dashboard.refresh import RefreshOrchestrator

__all__ = [
    "Widget",
    "WidgetBase",
    "WIDGET_REGISTRY",
    "register_widget",
    "WidgetCache",
    "parse_ttl",
    "WidgetConfig",
    "Column",
    "Page",
    "Theme",
    "DashboardConfig",
    "interpolate",
    "load_dashboard",
    "build_widget_instances",
    "RefreshOrchestrator",
]
