"""Kelly-criterion position sizing.

PRD section 5.3:

    odds = (1 / p_market) - 1
    edge = p_model - p_market
    kelly_pct = (edge * (odds + 1) - (1 - p_model)) / odds
    size = bankroll * max(0, kelly_pct) * fraction

Edge cases (mandated by lane spec):

    p_market <= 0 or >= 1   -> 0          (degenerate market price)
    p_model  <= p_market     -> 0          (no edge or negative edge)
    confidence < 0           -> ValueError (caller bug)
    NaN inputs               -> ValueError
    fraction defaults to config.KELLY_FRACTION (0.25)
    capped at config.MAX_POSITION_PCT of bankroll
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from sigil.config import config


@dataclass
class KellySizeResult:
    bet_amount: float          # dollars
    kelly_fraction_used: float # fraction of bankroll
    capped: bool               # True if MAX_POSITION_PCT cap was hit


def _is_nan(*xs: Optional[float]) -> bool:
    return any(x is not None and isinstance(x, float) and math.isnan(x) for x in xs)


def kelly_size(
    p_model: float,
    p_market: float,
    bankroll: float,
    *,
    fraction: Optional[float] = None,
    confidence: Optional[float] = None,
    max_position_pct: Optional[float] = None,
) -> KellySizeResult:
    """Return the dollar size of a bet under fractional Kelly.

    `confidence`, when supplied, scales the Kelly fraction linearly
    (fraction *= confidence) — caller decides whether to use it.
    """
    if _is_nan(p_model, p_market, bankroll, fraction, confidence):
        raise ValueError("NaN inputs to kelly_size")
    if confidence is not None and confidence < 0:
        raise ValueError(f"confidence must be >= 0, got {confidence}")

    if bankroll <= 0:
        return KellySizeResult(0.0, 0.0, False)

    if not (0.0 < p_market < 1.0):
        return KellySizeResult(0.0, 0.0, False)

    if p_model <= p_market:
        return KellySizeResult(0.0, 0.0, False)

    if not (0.0 <= p_model <= 1.0):
        # p_model out of [0,1] is malformed input.
        raise ValueError(f"p_model must be in [0,1], got {p_model}")

    odds = (1.0 / p_market) - 1.0
    if odds <= 0:
        return KellySizeResult(0.0, 0.0, False)

    edge = p_model - p_market
    kelly_pct_full = (edge * (odds + 1.0) - (1.0 - p_model)) / odds
    kelly_pct_full = max(0.0, kelly_pct_full)

    f = config.KELLY_FRACTION if fraction is None else fraction
    if confidence is not None:
        f = f * confidence

    kelly_pct = kelly_pct_full * f

    cap = (config.MAX_POSITION_PCT if max_position_pct is None else max_position_pct) / 100.0
    capped = False
    if kelly_pct > cap:
        kelly_pct = cap
        capped = True

    return KellySizeResult(
        bet_amount=bankroll * kelly_pct,
        kelly_fraction_used=kelly_pct,
        capped=capped,
    )
