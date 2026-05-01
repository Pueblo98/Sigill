"""Cross-platform spread-arbitrage signal.

OddsPipe's ``/v1/spreads`` endpoint pre-matches Kalshi <-> Polymarket
markets by title similarity and computes the YES-price difference. This
signal generator polls that endpoint, computes a volume-weighted
"true" probability across the two sides, and emits a ``Prediction`` row
on whichever side is meaningfully under-priced.

Decision engine wiring is unchanged — emitted Predictions land in the
existing pipeline (DecisionEngine -> OMS), and surface in
the ``signal_queue`` dashboard widget.

Sizing assumption: this is a v0 signal. For each match we emit a single
Prediction on the cheaper side (``edge >= min_edge``). The opposite
side may also be mispriced (selling YES at the more expensive platform
is the classic arb), but our pipeline today is buy-only YES, so
that side is intentionally not surfaced.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.ingestion.oddspipe import OddsPipeDataSource, SpreadMatch, SpreadSide
from sigil.models import Market, Prediction, PredictionFeature
from sigil.models_registry import ModelDef, register_model


logger = logging.getLogger(__name__)


MODEL_ID = "spread_arb"
MODEL_VERSION = "v0"


register_model(ModelDef(
    model_id=MODEL_ID,
    version=MODEL_VERSION,
    display_name="Stat Arb (Cross-Platform)",
    description="Volume-weighted true probability across Kalshi & Polymarket spreads.",
    tags=("arbitrage", "cross-platform", "binary-yes"),
))


async def generate_spread_predictions(
    session: AsyncSession,
    odds_source: OddsPipeDataSource,
    *,
    min_score: float = 95.0,
    min_edge: float = 0.05,
    max_yes_diff: float = 0.30,
    dedup_window_seconds: int = 300,
    max_matches: int = 30,
) -> int:
    """Poll /v1/spreads and emit Predictions for under-priced sides.

    Returns the number of new ``Prediction`` rows written. Skips a
    side whenever:

    - the spread match score is below ``min_score`` (handled by the
      OddsPipe call),
    - both sides have zero volume (no signal),
    - the side's ``external_id`` couldn't be resolved (caller didn't
      run :meth:`OddsPipeDataSource.fetch` recently),
    - the volume-weighted edge is below ``min_edge``,
    - we already wrote a Prediction for this market+model in the last
      ``dedup_window_seconds``.
    """
    spreads = await odds_source.fetch_spreads(
        min_score=min_score, top_n=max_matches
    )
    if not spreads:
        return 0

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=dedup_window_seconds)
    n_written = 0

    for match in spreads:
        # Drop matches whose absolute yes_diff is suspiciously large —
        # OddsPipe matches on title similarity, not semantic equivalence,
        # so a 0.9 spread is almost always a wrong-match (e.g. "Will Mexico
        # win the World Cup?" vs "Will a WC game be played in Mexico?").
        if abs(match.yes_diff) > max_yes_diff:
            continue
        n_written += await _emit_for_match(
            session, odds_source, match, min_edge=min_edge, cutoff=cutoff,
        )

    if n_written > 0:
        await session.commit()
        logger.info("spread_arb: emitted %d Prediction(s)", n_written)
    return n_written


async def _upsert_market_for_side(
    session: AsyncSession,
    odds_source: OddsPipeDataSource,
    side: SpreadSide,
) -> Optional[Market]:
    """Find or create a Market row for a spread side. Pulls /v1/markets/{id}
    if we don't already have the market — necessary because /v1/spreads can
    reference markets outside the top-N OddsPipe page.
    """
    if side.external_id is None:
        return None
    market = (await session.execute(
        select(Market).where(
            Market.platform == side.platform,
            Market.external_id == side.external_id,
        )
    )).scalar_one_or_none()
    if market is not None:
        return market

    detail = await odds_source.fetch_market_detail(side.internal_id)
    if detail is None:
        return None

    title = detail.get("title") or side.title or side.external_id
    category_raw = detail.get("category")
    taxonomy = (str(category_raw).lower() if category_raw else "general")

    market = Market(
        platform=side.platform,
        external_id=side.external_id,
        title=title,
        taxonomy_l1=taxonomy,
        market_type="binary",
        status="open",
    )
    session.add(market)
    await session.flush()
    return market


async def _emit_for_match(
    session: AsyncSession,
    odds_source: OddsPipeDataSource,
    match: SpreadMatch,
    *,
    min_edge: float,
    cutoff: datetime,
) -> int:
    if len(match.sides) != 2:
        return 0

    total_vol = sum(s.volume_usd for s in match.sides)
    if total_vol <= 0:
        # Zero volume on both sides — no signal worth trusting.
        return 0
    true_p = sum(s.yes_price * s.volume_usd for s in match.sides) / total_vol

    n = 0
    for side in match.sides:
        if side.external_id is None:
            continue
        edge = true_p - side.yes_price
        if edge < min_edge:
            continue
        market = await _upsert_market_for_side(session, odds_source, side)
        if market is None:
            continue

        # Dedup: skip if we already wrote a Prediction for this market
        # under the same model_id within the dedup window.
        recent = (await session.execute(
            select(Prediction.id).where(
                Prediction.market_id == market.id,
                Prediction.model_id == MODEL_ID,
                Prediction.created_at >= cutoff,
            ).limit(1)
        )).scalar_one_or_none()
        if recent is not None:
            continue

        prediction_id = uuid4()
        session.add(Prediction(
            id=prediction_id,
            market_id=market.id,
            model_id=MODEL_ID,
            model_version=MODEL_VERSION,
            predicted_prob=round(true_p, 4),
            confidence=round(min(match.score / 100.0, 0.99), 3),
            market_price_at_prediction=round(side.yes_price, 4),
            edge=round(edge, 4),
        ))
        # PredictionFeature rows make "why did the model think this?"
        # legible on the market detail page. One row per side per
        # signal-relevant scalar.
        poly = next((s for s in match.sides if s.platform == "polymarket"), None)
        kalshi = next((s for s in match.sides if s.platform == "kalshi"), None)
        feats: List[tuple[str, float]] = [
            ("match_score", float(match.score)),
            ("true_prob_volume_weighted", float(true_p)),
            ("yes_diff", float(match.yes_diff)),
        ]
        if poly is not None:
            feats.append(("polymarket_yes_price", float(poly.yes_price)))
            feats.append(("polymarket_volume_usd", float(poly.volume_usd)))
        if kalshi is not None:
            feats.append(("kalshi_yes_price", float(kalshi.yes_price)))
            feats.append(("kalshi_volume_usd", float(kalshi.volume_usd)))
        for name, value in feats:
            session.add(PredictionFeature(
                prediction_id=prediction_id,
                feature_name=name,
                value=value,
                version=1,
            ))
        n += 1

    return n
