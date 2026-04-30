"""Widget Protocol, base class, and registry for the dashboard.

Each widget knows how to fetch its data from a session and render it into an
HTML fragment (Markup). Backoff state lives on the WidgetBase instance: on a
fetch error the widget pushes its next retry forward by one of the
fixed-interval steps (1, 4, 9, 16, 25 minutes) and resets to step 0 on
success.

The orchestrator (refresh.py) drives fetch + cache; the widget never touches
storage directly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar, Dict, List, Optional, Protocol, Type, runtime_checkable

from markupsafe import Markup, escape

from sigil.dashboard.cache import parse_ttl
from sigil.dashboard.config import Theme, WidgetConfig

logger = logging.getLogger(__name__)


# Backoff schedule in minutes. Aligns with glance's 1/4/9/16/25 schedule —
# error severity climbs slowly so a transient blip doesn't quarantine a
# widget for an hour.
BACKOFF_INTERVALS_MINUTES: List[int] = [1, 4, 9, 16, 25]


@runtime_checkable
class Widget(Protocol):
    """Public contract every widget implements.

    type: ClassVar[str]      — registry key, must match `WidgetConfig.type`.
    cache_ttl: timedelta     — how often the widget *wants* to be refreshed.

    cache_key()              — distinguishes instances of the same widget
                               type with different YAML config.
    async fetch(session)     — produce raw data; orchestrator caches on
                               success, applies backoff on exception.
    render(data) -> Markup   — render into an HTML fragment.
    requires_update(now)     — return True when next fetch is due.
    """

    type: ClassVar[str]
    cache_ttl: timedelta

    def cache_key(self) -> str: ...

    async def fetch(self, session: Any) -> Any: ...

    def render(self, data: Any) -> Markup: ...

    def requires_update(self, now: datetime) -> bool: ...


WIDGET_REGISTRY: Dict[str, Type["WidgetBase"]] = {}


def register_widget(type_name: str):
    """Decorator: register a concrete widget class under `type_name`.

    Usage:
        @register_widget("market_list")
        class MarketListWidget(WidgetBase):
            ...

    Re-registering the same name overwrites the prior class — convenient for
    test isolation and YAML hot-reload, intentional rather than accidental.
    """

    def _decorator(cls: Type["WidgetBase"]) -> Type["WidgetBase"]:
        if not isinstance(type_name, str) or not type_name:
            raise ValueError("widget type name must be a non-empty string")
        cls.type = type_name
        WIDGET_REGISTRY[type_name] = cls
        return cls

    return _decorator


class WidgetBase:
    """Concrete widget base.

    Subclasses set:
      - `type` (via `@register_widget(...)`)
      - `config_model` (a pydantic class extending WidgetConfig) — optional,
        used by the loader to validate widget-specific YAML fields.

    Subclasses override:
      - `async fetch(session)`
      - `render(data) -> Markup`
      - `cache_key()` — defaults to widget type, override when YAML-driven
        config (filters, limits) should produce distinct cache buckets.
    """

    type: ClassVar[str] = "_base"
    config_model: ClassVar[Type[WidgetConfig]] = WidgetConfig

    def __init__(self, config: WidgetConfig):
        self.config = config
        self.cache_ttl: timedelta = parse_ttl(config.cache)
        self._next_fetch_at: Optional[datetime] = None
        # Step index into BACKOFF_INTERVALS_MINUTES. -1 means no error active.
        self._backoff_step: int = -1
        self._last_error: Optional[BaseException] = None
        # Theme is set by the loader at startup so chart widgets can pull
        # accent / positive / negative colors from `self.theme` without a
        # module-level global. None until the loader injects.
        self.theme: Optional[Theme] = None

    def set_theme(self, theme: Theme) -> None:
        """Loader hook: inject the dashboard theme onto the widget instance.

        Widgets that render charts should pass `self.theme` to the chart
        helpers; widgets without color-coded output can ignore it.
        """
        self.theme = theme

    # ------------------------------------------------------------------
    # Identification
    # ------------------------------------------------------------------

    def cache_key(self) -> str:
        """Default: just the widget type. Subclasses override when their
        config splits the cache (e.g. market_list with different filters)."""
        return self.type

    # ------------------------------------------------------------------
    # Refresh scheduling
    # ------------------------------------------------------------------

    def requires_update(self, now: datetime) -> bool:
        """True if the orchestrator should fetch this widget now.

        First call (no prior fetch): always True.
        Otherwise: True iff `now >= self._next_fetch_at`.
        """
        if self._next_fetch_at is None:
            return True
        return now >= self._next_fetch_at

    def mark_success(self, now: Optional[datetime] = None) -> None:
        """Reset backoff and schedule next fetch at now + cache_ttl."""
        now = now or datetime.now(timezone.utc)
        self._backoff_step = -1
        self._last_error = None
        self._next_fetch_at = now + self.cache_ttl

    def mark_error(self, exc: BaseException, now: Optional[datetime] = None) -> None:
        """Bump backoff one step (cap at last interval) and schedule next
        retry. Stores the exception so render_error can surface it."""
        now = now or datetime.now(timezone.utc)
        self._backoff_step = min(self._backoff_step + 1, len(BACKOFF_INTERVALS_MINUTES) - 1)
        delay = BACKOFF_INTERVALS_MINUTES[self._backoff_step]
        self._next_fetch_at = now + timedelta(minutes=delay)
        self._last_error = exc

    @property
    def backoff_step(self) -> int:
        """Public for tests + observability. -1 == healthy, 0..N == error N+1 in a row."""
        return self._backoff_step

    @property
    def last_error(self) -> Optional[BaseException]:
        return self._last_error

    @property
    def next_fetch_at(self) -> Optional[datetime]:
        return self._next_fetch_at

    # ------------------------------------------------------------------
    # Fetch / render hooks
    # ------------------------------------------------------------------

    async def fetch(self, session: Any) -> Any:  # pragma: no cover - subclasses override
        raise NotImplementedError

    def render(self, data: Any) -> Markup:  # pragma: no cover - subclasses override
        raise NotImplementedError

    def render_error(self, exc: BaseException) -> Markup:
        """Default error rendering. Widgets may override for type-specific
        affordances; the default keeps the page useful instead of dropping
        a 500."""
        message = escape(f"{type(exc).__name__}: {exc}")
        next_retry = ""
        if self._next_fetch_at is not None:
            next_retry = (
                f' <span class="widget-error__retry">retry at '
                f'{escape(self._next_fetch_at.isoformat())}</span>'
            )
        html = (
            '<div class="widget-error" data-widget-type="'
            f'{escape(self.type)}">'
            '<div class="widget-error__title">Widget temporarily unavailable</div>'
            f'<div class="widget-error__detail">{message}</div>'
            f"{next_retry}"
            "</div>"
        )
        return Markup(html)

    def render_empty(self, message: str = "No data yet.") -> Markup:
        """Standard empty-state rendering — every widget calls this when its
        query returns nothing, so the look is consistent."""
        return Markup(
            f'<div class="widget-empty" data-widget-type="{escape(self.type)}">'
            f"{escape(message)}</div>"
        )
