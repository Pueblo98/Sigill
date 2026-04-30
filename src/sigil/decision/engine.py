"""Decision engine: edge calculation and signal generation.

Implements PRD §4.2:
    edge           = P_model - P_market
    weighted_edge  = (P_model - P_market) * model_confidence
    Trade only when weighted_edge > min_edge_threshold

Per REVIEW-DECISIONS.md:
    1C: Polymarket is read-only. should_trade('polymarket', ...) is always False.
    2F: Drawdown gate runs before order submission.

The DecisionEngine does NOT import from sigil.execution.* (Lane A may not have
shipped OMS yet). Instead, an OMS-submit callable is injected at construction
time. Tests pass a mock callable.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Union
from uuid import UUID

from sigil.config import config
from sigil.decision.drawdown import (
    DrawdownState,
    current_state,
    position_size_multiplier,
)

logger = logging.getLogger(__name__)


OMSSubmitResult = Any  # Lane A defines the concrete return type.
OMSSubmit = Callable[..., Union[OMSSubmitResult, Awaitable[OMSSubmitResult]]]


@dataclass
class DecisionResult:
    """Outcome of a single decision-engine evaluation."""

    accepted: bool
    reason: str
    edge: float
    weighted_edge: float
    drawdown_state: DrawdownState
    size_multiplier: float
    oms_response: Any = None


def compute_edge(p_model: float, p_market: float, confidence: float) -> float:
    """Confidence-weighted edge: (p_model - p_market) * confidence.

    Returns 0.0 when p_market is at the boundary (0 or 1) — these indicate
    no liquidity and any "edge" against them is degenerate.

    Raises:
        ValueError: if any input is NaN, p_model/p_market outside [0, 1],
            or confidence outside [0, 1].
    """
    for name, value in (("p_model", p_model), ("p_market", p_market), ("confidence", confidence)):
        if value is None or (isinstance(value, float) and math.isnan(value)):
            raise ValueError(f"{name} must be a finite number, got {value!r}")

    if not (0.0 <= p_model <= 1.0):
        raise ValueError(f"p_model must be in [0, 1], got {p_model}")
    if not (0.0 <= p_market <= 1.0):
        raise ValueError(f"p_market must be in [0, 1], got {p_market}")
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"confidence must be in [0, 1], got {confidence}")

    if p_market in (0.0, 1.0):
        return 0.0

    return (p_model - p_market) * confidence


def should_trade(weighted_edge: float, platform: str) -> bool:
    """Return True iff the weighted edge clears the per-platform threshold.

    Polymarket is display-only per REVIEW-DECISIONS.md 1C. We never auto-trade
    Polymarket legs even if the edge is large — log and reject.
    """
    if weighted_edge is None or (isinstance(weighted_edge, float) and math.isnan(weighted_edge)):
        raise ValueError(f"weighted_edge must be a finite number, got {weighted_edge!r}")

    platform_lc = (platform or "").lower()

    if platform_lc == "polymarket":
        logger.warning(
            "Rejecting polymarket auto-trade (display-only per REVIEW-DECISIONS.md 1C); "
            "weighted_edge=%.4f",
            weighted_edge,
        )
        return False

    if platform_lc == "kalshi":
        return weighted_edge > config.MIN_EDGE_KALSHI

    logger.warning("Unknown platform %r; refusing to trade.", platform)
    return False


class DecisionEngine:
    """Orchestrates edge calc, drawdown check, and order submission.

    The engine never imports from `sigil.execution.*`; the OMS submit hook is
    injected so Lane B's tests don't depend on Lane A's implementation timing.
    """

    def __init__(
        self,
        oms_submit: OMSSubmit,
        mode: str = "paper",
        drawdown_state_fn: Optional[Callable[..., DrawdownState]] = None,
    ):
        self.oms_submit = oms_submit
        self.mode = mode
        self._drawdown_state_fn = drawdown_state_fn or current_state

    async def evaluate(
        self,
        session: Any,
        prediction: Any,
        market_price: float,
        platform: str,
        market_id: UUID,
        side: str = "buy",
        outcome: str = "yes",
    ) -> DecisionResult:
        """Score a prediction and (if all gates pass) submit an order via OMS.

        `prediction` is duck-typed: any object with `predicted_prob` and
        `confidence` attributes works (so tests can pass a plain namespace).
        """
        p_model = float(prediction.predicted_prob)
        confidence = float(prediction.confidence) if prediction.confidence is not None else 1.0

        edge = compute_edge(p_model, market_price, confidence)
        weighted_edge = edge  # compute_edge already applies confidence weighting

        platform_lc = (platform or "").lower()

        if platform_lc == "polymarket":
            logger.info(
                "Polymarket display-only signal: p_model=%.3f p_market=%.3f weighted_edge=%.4f "
                "(market_id=%s)",
                p_model,
                market_price,
                weighted_edge,
                market_id,
            )
            return DecisionResult(
                accepted=False,
                reason="polymarket_display_only",
                edge=edge,
                weighted_edge=weighted_edge,
                drawdown_state=DrawdownState.INACTIVE,
                size_multiplier=0.0,
            )

        if not should_trade(weighted_edge, platform_lc):
            return DecisionResult(
                accepted=False,
                reason="edge_below_threshold",
                edge=edge,
                weighted_edge=weighted_edge,
                drawdown_state=DrawdownState.INACTIVE,
                size_multiplier=0.0,
            )

        state = await _maybe_await(self._drawdown_state_fn(session, mode=self.mode))
        multiplier = position_size_multiplier(state)

        if multiplier <= 0.0:
            logger.warning(
                "Drawdown gate halted trade: state=%s market_id=%s",
                state,
                market_id,
            )
            return DecisionResult(
                accepted=False,
                reason=f"drawdown_{state.value}",
                edge=edge,
                weighted_edge=weighted_edge,
                drawdown_state=state,
                size_multiplier=multiplier,
            )

        oms_response = await _maybe_await(
            self.oms_submit(
                session=session,
                prediction_id=getattr(prediction, "id", None),
                market_id=market_id,
                platform=platform_lc,
                side=side,
                outcome=outcome,
                edge_at_entry=edge,
                size_multiplier=multiplier,
                mode=self.mode,
            )
        )

        return DecisionResult(
            accepted=True,
            reason="submitted",
            edge=edge,
            weighted_edge=weighted_edge,
            drawdown_state=state,
            size_multiplier=multiplier,
            oms_response=oms_response,
        )


async def _maybe_await(value: Any) -> Any:
    if hasattr(value, "__await__"):
        return await value
    return value
