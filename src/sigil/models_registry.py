"""Code-defined registry of trading models.

Each signal module (e.g. ``signals/spread_arb.py``) registers itself at
import time with a :class:`ModelDef`. The registry is read by the
``/api/models`` endpoints to surface every model on the frontend
performance page — even before the model has emitted its first
prediction. That's intentional: a registered-but-quiet model becomes a
"no signals yet" card, not an invisible one.

We deliberately do **not** persist this metadata to the database.
Display name, description, and tags change only when the model code
changes; storing them in DB would create drift between code and surface.

Adding a new model is one ``register_model(...)`` call:

    from sigil.models_registry import ModelDef, register_model

    register_model(ModelDef(
        model_id="my_model",
        version="v0",
        display_name="My Model",
        description="One-line tagline.",
        tags=("category-a", "category-b"),
    ))
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ModelDef:
    model_id: str
    version: str
    display_name: str
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True


_REGISTRY: dict[str, ModelDef] = {}


def register_model(m: ModelDef) -> None:
    """Register a model. Last write wins on duplicate model_id — this lets
    a module re-import (common in test runners) without raising, while
    keeping the most recent definition authoritative.
    """
    _REGISTRY[m.model_id] = m


def all_models() -> list[ModelDef]:
    """Return all registered models, sorted by display_name for stable UI order."""
    return sorted(_REGISTRY.values(), key=lambda m: m.display_name.lower())


def get_model(model_id: str) -> Optional[ModelDef]:
    return _REGISTRY.get(model_id)


def reset_registry_for_tests() -> None:
    """Test-only: clear the registry. Production code never calls this."""
    _REGISTRY.clear()
