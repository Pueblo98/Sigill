"""cross_platform_spreads widget — live arb opportunities.

Hits OddsPipe ``/v1/spreads`` directly on each refresh and renders the
matched pairs side-by-side. This is the dashboard surface for the
spread_arb signal: the same matches feed the signal generator, so what
the operator sees here is what's actually being acted on (after edge +
score gates).

Filters by ``min_score`` (default 95 — title-similarity cutoff) and
``max_yes_diff`` (default 0.30 — drop wrong-match noise). Caches
aggressively (5m TTL) because OddsPipe's free tier rate-limits.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, List, Optional, Type

from markupsafe import Markup, escape
from pydantic import Field

from sigil.config import config as root_config
from sigil.dashboard.config import WidgetConfig
from sigil.dashboard.widget import WidgetBase, register_widget
from sigil.ingestion.oddspipe import OddsPipeDataSource


class CrossPlatformSpreadsConfig(WidgetConfig):
    limit: int = Field(default=20, ge=1, le=200)
    min_score: float = Field(default=95.0, ge=0.0, le=100.0)
    max_yes_diff: float = Field(default=0.30, ge=0.0, le=1.0)


@dataclass(frozen=True)
class SpreadRow:
    """One row in the rendered table — a matched pair across platforms."""
    question: str               # one platform's title (typically the longer)
    score: float
    yes_diff: float
    direction: str              # "kalshi_higher" | "polymarket_higher"
    kalshi_yes: Optional[float]
    kalshi_vol: float
    kalshi_url: str
    polymarket_yes: Optional[float]
    polymarket_vol: float
    polymarket_url: str


@register_widget("cross_platform_spreads")
class CrossPlatformSpreadsWidget(WidgetBase):
    config_model: ClassVar[Type[WidgetConfig]] = CrossPlatformSpreadsConfig

    def __init__(self, config: CrossPlatformSpreadsConfig):
        super().__init__(config)
        self._limit = config.limit
        self._min_score = config.min_score
        self._max_yes_diff = config.max_yes_diff

    def cache_key(self) -> str:
        return (
            f"{self.type}:limit={self._limit}:min_score={self._min_score}:"
            f"max_yes_diff={self._max_yes_diff}"
        )

    async def fetch(self, session: Any) -> List[SpreadRow]:
        # Note: this widget hits OddsPipe live (one HTTP per refresh).
        # The refresh orchestrator caches the result for cache_ttl, so
        # if cache=5m is set we're at 12 calls/hour, well under free-tier
        # quota even if every page hit landed during a cold cache.
        api_key = root_config.ODDSPIPE_API_KEY
        if not api_key:
            return []

        odds = OddsPipeDataSource(api_key=api_key)
        try:
            spreads = await odds.fetch_spreads(
                min_score=self._min_score, top_n=self._limit
            )
        finally:
            try:
                await odds.client.aclose()
            except Exception:
                pass

        rows: List[SpreadRow] = []
        for sp in spreads:
            if abs(sp.yes_diff) > self._max_yes_diff:
                continue
            kalshi = next((s for s in sp.sides if s.platform == "kalshi"), None)
            poly = next((s for s in sp.sides if s.platform == "polymarket"), None)
            if kalshi is None or poly is None:
                continue
            # Prefer the longer title (often more descriptive) for display.
            question = kalshi.title if len(kalshi.title) >= len(poly.title) else poly.title
            rows.append(SpreadRow(
                question=question,
                score=sp.score,
                yes_diff=sp.yes_diff,
                direction=sp.direction,
                kalshi_yes=kalshi.yes_price,
                kalshi_vol=kalshi.volume_usd,
                kalshi_url=f"https://kalshi.com/markets/{kalshi.external_id}" if kalshi.external_id else "https://kalshi.com",
                polymarket_yes=poly.yes_price,
                polymarket_vol=poly.volume_usd,
                polymarket_url="https://polymarket.com",
            ))

        rows.sort(key=lambda r: abs(r.yes_diff), reverse=True)
        return rows[: self._limit]

    def render(self, data: List[SpreadRow]) -> Markup:
        if not data:
            return self.render_empty(
                "No high-confidence cross-platform spreads right now."
            )

        rows_html_parts = []
        for r in data:
            ky = "-" if r.kalshi_yes is None else f"{r.kalshi_yes:.3f}"
            py = "-" if r.polymarket_yes is None else f"{r.polymarket_yes:.3f}"
            kvol = f"${r.kalshi_vol:,.0f}"
            pvol = f"${r.polymarket_vol:,.0f}"
            direction_arrow = "↑K" if r.direction == "kalshi_higher" else "↑P"
            rows_html_parts.append(
                "<tr>"
                f"<td>{escape(r.question[:80])}</td>"
                f'<td><a href="{escape(r.kalshi_url)}" target="_blank">{ky}</a></td>'
                f"<td>{kvol}</td>"
                f'<td><a href="{escape(r.polymarket_url)}" target="_blank">{py}</a></td>'
                f"<td>{pvol}</td>"
                f"<td>{r.yes_diff:+.3f} {direction_arrow}</td>"
                f"<td>{r.score:.0f}</td>"
                "</tr>"
            )
        rows_html = "".join(rows_html_parts)
        html = (
            '<div class="widget widget-spreads" '
            f'data-widget-type="{escape(self.type)}">'
            '<div class="widget__header">Cross-platform spreads</div>'
            '<table class="widget__table">'
            "<thead><tr>"
            "<th>Question</th>"
            "<th>Kalshi YES</th><th>Vol</th>"
            "<th>Polymarket YES</th><th>Vol</th>"
            "<th>Spread</th><th>Score</th>"
            "</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            "</table>"
            "</div>"
        )
        return Markup(html)
