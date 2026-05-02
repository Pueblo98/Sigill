"""Models list page — card grid of every registered model.

Mirrors the Next.js ``/models`` mechanic: one card per ``ModelDef`` in
:mod:`sigil.models_registry`, populated with summary metrics from
:mod:`sigil.api.model_performance`. Each card links to
``/models/{model_id}`` for the per-model deep dive.

URL: ``GET /models``

Models without any predictions or trades still appear (with a
``no-data`` summary) so a freshly registered model becomes a "no signals
yet" card rather than being invisible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from sigil.api import model_performance as mp


@dataclass(frozen=True)
class _ModelCard:
    model_id: str
    version: str
    display_name: str
    description: str
    tags: List[str]
    enabled: bool
    status: str   # "live" | "idle" | "disabled"
    summary: Dict[str, Any]


@dataclass(frozen=True)
class ModelsListContext:
    cards: List[_ModelCard]
    total: int


def _status_for(meta: Dict[str, Any], summary: Dict[str, Any]) -> str:
    """Map (enabled, recent activity) → display status.

    - disabled: ModelDef.enabled is False
    - live: enabled AND ≥1 prediction in the last 24h
    - idle: enabled AND no recent predictions

    Matches the Next.js Models card status dot logic.
    """
    if not meta.get("enabled", True):
        return "disabled"
    if (summary.get("predictions_24h") or 0) > 0:
        return "live"
    return "idle"


async def build_context(session: AsyncSession) -> ModelsListContext:
    """Fetch every registered model + its summary, in registry order
    (alphabetical by display_name — :func:`sigil.models_registry.all_models`
    sorts).
    """
    summaries = await mp.all_model_summaries(session)
    cards: List[_ModelCard] = []
    for entry in summaries:
        summary = entry.get("summary") or {}
        cards.append(_ModelCard(
            model_id=entry["model_id"],
            version=entry["version"],
            display_name=entry["display_name"],
            description=entry.get("description") or "",
            tags=list(entry.get("tags") or []),
            enabled=bool(entry.get("enabled", True)),
            status=_status_for(entry, summary),
            summary=summary,
        ))
    return ModelsListContext(cards=cards, total=len(cards))
