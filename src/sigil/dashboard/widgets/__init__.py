"""Widget implementations for the Sigil dashboard.

Each module registers its widget class with `@register_widget(...)`. Importing
this package side-effects the registry. F1 owns the read-only widgets here;
F2 adds the chart widgets in sibling files.
"""

from sigil.dashboard.widgets import (  # noqa: F401  (registers widgets)
    bankroll_summary,
    market_list,
    open_positions,
    recent_activity,
    signal_queue,
    system_health_strip,
)
