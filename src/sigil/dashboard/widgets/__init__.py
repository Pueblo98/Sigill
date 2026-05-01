"""Widget implementations for the Sigil dashboard.

Each module registers its widget class with `@register_widget(...)`. Importing
this package side-effects the registry. F1 owns the read-only widgets; F2
adds the chart widgets.
"""

from sigil.dashboard.widgets import (  # noqa: F401  (registers widgets)
    backtest_results,
    bankroll_summary,
    cross_platform_spreads,
    error_log,
    market_list,
    model_brier,
    model_calibration,
    model_roi_curve,
    open_positions,
    recent_activity,
    signal_queue,
    source_health_table,
    system_health_strip,
)
