"""Read dashboard.yaml, validate, and instantiate widget classes."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Union

import yaml

from sigil.dashboard.config import DashboardConfig, Page, WidgetConfig, interpolate
from sigil.dashboard.widget import WIDGET_REGISTRY, WidgetBase

logger = logging.getLogger(__name__)


def load_dashboard(path: Union[str, Path]) -> DashboardConfig:
    """Read + interpolate + validate the dashboard YAML at `path`."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    interpolated = interpolate(raw)
    data = yaml.safe_load(interpolated)
    if data is None:
        raise ValueError(f"dashboard YAML at {path} is empty")
    return DashboardConfig.model_validate(data)


def build_widget_instances(config: DashboardConfig) -> List[WidgetBase]:
    """Instantiate concrete widget classes for every YAML widget config.

    Validates the widget-specific config via the widget's `config_model` —
    catches typos like a `limit:` value passed to a widget that doesn't take
    one. Unknown widget types raise so the operator notices immediately.
    """
    instances: List[WidgetBase] = []
    for page in config.pages:
        instances.extend(_instantiate_page(page))
    return instances


def _instantiate_page(page: Page) -> List[WidgetBase]:
    out: List[WidgetBase] = []
    for column in page.columns:
        for widget_config in column.widgets:
            out.append(_instantiate_widget(widget_config))
    return out


def _instantiate_widget(raw: WidgetConfig) -> WidgetBase:
    cls = WIDGET_REGISTRY.get(raw.type)
    if cls is None:
        registered = sorted(WIDGET_REGISTRY.keys())
        raise ValueError(
            f"unknown widget type: {raw.type!r}. Registered: {registered}"
        )

    # Re-validate against the concrete widget's config model so widget-
    # specific fields (limit, filters) get type-checked.
    config_model = getattr(cls, "config_model", WidgetConfig)
    typed_config = config_model.model_validate(raw.model_dump())
    return cls(typed_config)
