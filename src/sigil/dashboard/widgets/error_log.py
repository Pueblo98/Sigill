"""error_log widget.

Recent ``SourceHealth`` rows where ``error_message`` is non-null. Each
entry shows timestamp, source_name, and the error message truncated to
~120 characters. Default cap of 100 entries; the operator can override
with ``limit:`` in YAML.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar, List, Type

from markupsafe import Markup, escape
from pydantic import Field
from sqlalchemy import desc, select

from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.models import SourceHealth


_MESSAGE_TRUNCATE_AT = 120


class ErrorLogConfig(WidgetConfig):
    limit: int = Field(default=100, ge=1, le=1000)


@dataclass(frozen=True)
class ErrorEntry:
    when: datetime
    source_name: str
    message: str  # already truncated


@register_widget("error_log")
class ErrorLogWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = ErrorLogConfig

    def __init__(self, config: ErrorLogConfig):
        super().__init__(config)
        self._limit = config.limit

    def cache_key(self) -> str:
        return f"{self.type}:limit={self._limit}"

    async def fetch(self, session: Any) -> List[ErrorEntry]:
        rows = (
            await session.execute(
                select(SourceHealth)
                .where(SourceHealth.error_message.is_not(None))
                .order_by(desc(SourceHealth.check_time))
                .limit(self._limit)
            )
        ).scalars().all()
        if not rows:
            return []

        out: List[ErrorEntry] = []
        for r in rows:
            msg = r.error_message or ""
            if len(msg) > _MESSAGE_TRUNCATE_AT:
                msg = msg[: _MESSAGE_TRUNCATE_AT - 1] + "…"
            out.append(
                ErrorEntry(
                    when=r.check_time,
                    source_name=r.source_name,
                    message=msg,
                )
            )
        return out

    def render(self, data: List[ErrorEntry]) -> Markup:
        if not data:
            return self.render_empty("No recent errors.")

        items_html = "".join(
            (
                '<li class="error-log__item">'
                f'<span class="error-log__when" data-relative-time="{escape(e.when.isoformat())}">'
                f"{escape(e.when.isoformat())}</span>"
                f'<span class="error-log__source">{escape(e.source_name)}</span>'
                f'<span class="error-log__message">{escape(e.message)}</span>'
                "</li>"
            )
            for e in data
        )
        html = (
            '<div class="widget widget-error-log" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Error Log</div>'
            f'<ol class="error-log__list">{items_html}</ol>'
            "</div>"
        )
        return Markup(html)
