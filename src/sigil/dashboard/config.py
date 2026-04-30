"""Pydantic models for the dashboard YAML schema + env-var interpolation.

Schema:
    pages:
      - name, title, default, columns:
          - size: full|small|half
            widgets:
              - type, cache, ...widget-specific keys
    theme:
      background, surface, accent, positive, negative  (hex strings)

Env-var interpolation runs over the raw YAML string before parsing: `${VAR}`
resolves from os.environ. Missing vars raise KeyError so misconfiguration
fails loud rather than silently rendering "${THING}" into the UI.
"""

from __future__ import annotations

import os
import re
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_INTERPOLATION_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def interpolate(s: str) -> str:
    """Resolve `${VAR}` references in `s` from os.environ.

    Raises KeyError on missing variables. Designed to run on the raw YAML
    string before yaml.safe_load — catches typos in env names without us
    having to re-walk the parsed tree.
    """

    def _replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise KeyError(f"environment variable not set: {name}")
        return os.environ[name]

    return _INTERPOLATION_RE.sub(_replace, s)


class WidgetConfig(BaseModel):
    """Base widget configuration. Concrete widgets define a subclass with
    extra fields; the base allows extras so YAML stays permissive while the
    widget instance itself drives validation in its own model."""

    model_config = ConfigDict(extra="allow")

    type: str = Field(..., description="Widget type, must match a registry key")
    cache: str = Field(..., description="TTL spec (e.g. '30s', '5m', 'hourly')")


class Column(BaseModel):
    model_config = ConfigDict(extra="forbid")

    size: Literal["full", "small", "half"]
    widgets: List[WidgetConfig] = Field(default_factory=list)


class Page(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    title: str
    default: bool = False
    columns: List[Column] = Field(default_factory=list)


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: str
    surface: str
    accent: str
    positive: str
    negative: str

    @field_validator("background", "surface", "accent", "positive", "negative")
    @classmethod
    def _hex_color(cls, v: str) -> str:
        if not _HEX_COLOR_RE.match(v):
            raise ValueError(f"theme color must be hex (e.g. '#1b1b1d'), got {v!r}")
        return v


class DashboardConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pages: List[Page] = Field(default_factory=list)
    theme: Theme

    @field_validator("pages")
    @classmethod
    def _at_most_one_default(cls, v: List[Page]) -> List[Page]:
        defaults = [p for p in v if p.default]
        if len(defaults) > 1:
            names = [p.name for p in defaults]
            raise ValueError(f"multiple pages marked default: {names}")
        return v
