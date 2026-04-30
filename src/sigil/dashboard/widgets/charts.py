"""Server-side SVG chart helpers for dashboard widgets.

Phase 5 lane F2 deliverable: each widget that needs a chart calls one of
these helpers and embeds the returned SVG string into its HTML output.
matplotlib's ``Agg`` backend is selected up-front (before any pyplot import)
so we never try to attach to a display server.

The charts are deliberately tiny and produced with ``viewBox`` only — the
dashboard CSS controls the rendered size. No client-side JS, no Chart.js,
no Recharts.
"""

from __future__ import annotations

import io
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")  # MUST be set before any pyplot import.

import matplotlib.pyplot as plt  # noqa: E402

from sigil.dashboard.config import Theme  # noqa: E402


_DEFAULT_THEME = Theme(
    background="#1b1b1d",
    surface="#201f21",
    accent="#d2bbff",
    positive="#10b981",
    negative="#ef4444",
)

_active_theme: Theme = _DEFAULT_THEME


def set_theme(theme: Theme) -> None:
    """Override the module-level theme used by the chart helpers.

    F3's loader will call this once on dashboard startup with the YAML
    theme. Tests typically leave the default in place.
    """
    global _active_theme
    _active_theme = theme


def _current_theme() -> Theme:
    return _active_theme


def _figure_to_svg(fig: "plt.Figure") -> str:
    """Render ``fig`` into a responsive SVG string.

    Strips the explicit ``width`` / ``height`` attributes matplotlib adds so
    the SVG scales fluidly inside its widget container. Always closes the
    figure to free memory in long-running processes.
    """
    buf = io.StringIO()
    try:
        fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    finally:
        plt.close(fig)
    raw = buf.getvalue()

    # Drop the XML preamble — keeps the embed simple — and strip the fixed
    # width/height attrs from the root <svg> element so the chart scales.
    svg_start = raw.find("<svg")
    if svg_start == -1:
        return raw
    svg = raw[svg_start:]
    svg = _strip_attr(svg, "width")
    svg = _strip_attr(svg, "height")
    return svg


def _strip_attr(svg: str, attr: str) -> str:
    """Remove the first occurrence of ``attr="..."`` on the root <svg> tag."""
    end = svg.find(">")
    if end == -1:
        return svg
    head = svg[: end + 1]
    rest = svg[end + 1 :]
    needle = f' {attr}="'
    idx = head.find(needle)
    if idx == -1:
        return svg
    close = head.find('"', idx + len(needle))
    if close == -1:
        return svg
    head = head[:idx] + head[close + 1 :]
    return head + rest


def _empty_svg(width: int, height: int, message: str = "no data") -> str:
    """Tiny placeholder SVG used when a chart has no data to plot.

    Keeps the layout stable instead of yanking an entire widget out when a
    metric series is empty.
    """
    theme = _current_theme()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{message}">'
        f'<rect width="100%" height="100%" fill="{theme.surface}"/>'
        f'<text x="50%" y="50%" fill="{theme.accent}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="monospace" font-size="10">{message}</text>'
        f"</svg>"
    )


def render_calibration_curve_svg(
    predicted: Sequence[float],
    observed: Sequence[float],
    *,
    theme: Optional[Theme] = None,
) -> str:
    """200x200 calibration / reliability diagram.

    ``predicted`` and ``observed`` must be parallel sequences (one entry per
    bin) — typically the output of ``metrics.calibration_curve``. Plots the
    bin means against observed frequency and overlays the y=x reference.
    """
    if len(predicted) != len(observed):
        raise ValueError("predicted and observed must have equal length")
    if not predicted:
        return _empty_svg(200, 200, "no calibration data")

    t = theme or _current_theme()
    fig, ax = plt.subplots(figsize=(2.0, 2.0), dpi=100)
    ax.set_facecolor(t.surface)
    fig.patch.set_facecolor(t.background)

    # y=x perfect-calibration reference line.
    ax.plot([0.0, 1.0], [0.0, 1.0], color=t.accent, linewidth=0.8, alpha=0.5)
    ax.plot(
        list(predicted),
        list(observed),
        marker="o",
        markersize=4,
        linestyle="-",
        linewidth=1.0,
        color=t.accent,
    )

    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("predicted", color=t.accent, fontsize=8)
    ax.set_ylabel("observed", color=t.accent, fontsize=8)
    ax.tick_params(colors=t.accent, labelsize=6)
    for spine in ax.spines.values():
        spine.set_edgecolor(t.accent)
        spine.set_linewidth(0.5)
    ax.set_aspect("equal", adjustable="box")

    return _figure_to_svg(fig)


def render_roi_curve_svg(
    equity_curve: Sequence[tuple],
    *,
    theme: Optional[Theme] = None,
) -> str:
    """400x150 cumulative equity / ROI line chart.

    ``equity_curve`` is ``[(timestamp, equity), ...]`` — the same shape used
    by ``backtesting.metrics.roi``. We index x by position rather than
    timestamp so the chart is robust to sparse/uneven series.
    """
    if not equity_curve:
        return _empty_svg(400, 150, "no equity points")

    t = theme or _current_theme()
    ys = [float(eq) for _, eq in equity_curve]
    xs = list(range(len(ys)))

    fig, ax = plt.subplots(figsize=(4.0, 1.5), dpi=100)
    ax.set_facecolor(t.surface)
    fig.patch.set_facecolor(t.background)

    last = ys[-1]
    first = ys[0]
    line_color = t.positive if last >= first else t.negative

    ax.plot(xs, ys, color=line_color, linewidth=1.2)
    ax.fill_between(xs, ys, min(ys), color=line_color, alpha=0.15)

    ax.set_xlabel("trade #", color=t.accent, fontsize=8)
    ax.set_ylabel("equity", color=t.accent, fontsize=8)
    ax.tick_params(colors=t.accent, labelsize=6)
    for spine in ax.spines.values():
        spine.set_edgecolor(t.accent)
        spine.set_linewidth(0.5)

    return _figure_to_svg(fig)


def render_brier_sparkline_svg(
    daily_briers: Sequence[float],
    *,
    theme: Optional[Theme] = None,
) -> str:
    """400x100 sparkline of daily Brier scores. Lower is better.

    ``daily_briers`` is a flat sequence in chronological order. Empty input
    produces the placeholder SVG.
    """
    if not daily_briers:
        return _empty_svg(400, 100, "no brier history")

    t = theme or _current_theme()
    ys = [float(b) for b in daily_briers]
    xs = list(range(len(ys)))

    fig, ax = plt.subplots(figsize=(4.0, 1.0), dpi=100)
    ax.set_facecolor(t.surface)
    fig.patch.set_facecolor(t.background)

    # Brier 0 = perfect, 0.25 = coin flip. Color by the latest value.
    last = ys[-1]
    line_color = t.positive if last < 0.25 else t.negative
    ax.plot(xs, ys, color=line_color, linewidth=1.0)
    ax.axhline(0.25, color=t.accent, linewidth=0.5, alpha=0.4)

    ax.set_ylim(0.0, max(0.5, max(ys) * 1.1))
    ax.tick_params(colors=t.accent, labelsize=6)
    ax.set_xlabel("day", color=t.accent, fontsize=7)
    ax.set_ylabel("brier", color=t.accent, fontsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(t.accent)
        spine.set_linewidth(0.5)

    return _figure_to_svg(fig)
