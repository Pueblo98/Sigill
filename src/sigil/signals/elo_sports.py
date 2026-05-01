"""Elo-based sports prediction signal — v0 scaffolding.

Parses Kalshi NBA-game ticker patterns (``KXNBAGAME-<date>-<away><home>-<bet_team>``),
looks up the implied home/away Elo ratings, and emits a ``Prediction``
when the Elo win-probability differs from the market by ``min_edge``.

**Status: scaffolding only.** The Elo ratings here are a small hand-
seeded snapshot and will go stale without a live game-results feed.
Plug in ESPN scoreboard ingestion next; the rest of this module is
ready to consume real ratings.

Design choices:
- Only Kalshi NBA markets supported in v0. Easy to extend by adding
  more parsers; harder to do well across leagues without a real feed.
- Hardcoded ratings instead of importing :class:`EloRatingExtractor`
  state (which is in-memory anyway). A future version reads from a
  ``team_elo_ratings`` table populated by the ESPN ingest job.
- Confidence is a fixed 0.6 to reflect "Elo signal, no recent-form
  features" — the SpreadArbSignal sets confidence by API match score;
  Elo here is more of a hint until trained on real data.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sigil.models import Market, MarketPrice, Prediction, PredictionFeature
from sigil.models_registry import ModelDef, register_model


logger = logging.getLogger(__name__)


MODEL_ID = "elo_sports"
MODEL_VERSION = "v0"


register_model(ModelDef(
    model_id=MODEL_ID,
    version=MODEL_VERSION,
    display_name="Elo Sports (NBA)",
    description="Elo win-probability vs market price for Kalshi NBA single-game tickers.",
    tags=("sports", "elo", "scaffold"),
))


# Hand-seeded NBA team Elo ratings, late 2025-26 season order-of-magnitude.
# Replace with a live feed before trusting these numbers in paper trading.
# Source: ad-hoc from public ratings; absolute values matter less than
# relative deltas.
_NBA_ELO: Dict[str, float] = {
    "BOS": 1620, "MIN": 1605, "OKC": 1605, "DEN": 1590, "PHI": 1580,
    "MIL": 1575, "NYK": 1570, "DAL": 1560, "CLE": 1555, "LAL": 1545,
    "PHX": 1540, "MIA": 1535, "ORL": 1530, "IND": 1525, "GSW": 1520,
    "NOP": 1515, "SAC": 1510, "LAC": 1505, "HOU": 1500, "TOR": 1490,
    "CHI": 1485, "ATL": 1480, "BKN": 1475, "MEM": 1470, "POR": 1460,
    "UTA": 1455, "SAS": 1450, "WAS": 1445, "CHA": 1440, "DET": 1435,
}

# Map Kalshi ticker abbreviations to our roster keys above.
# Kalshi sometimes uses 3-letter codes that match; this dict catches
# the few that don't (e.g. NOP <-> NO).
_KALSHI_TEAM_ALIASES: Dict[str, str] = {
    "NO": "NOP", "NY": "NYK", "GS": "GSW", "PHO": "PHX",
    "BRK": "BKN", "BRO": "BKN", "CHO": "CHA", "WSH": "WAS",
    "SA": "SAS", "UTAH": "UTA",
}


def _normalize_team(code: str) -> Optional[str]:
    code = code.upper().strip()
    if not code:
        return None
    return _KALSHI_TEAM_ALIASES.get(code, code) if code in _NBA_ELO or code in _KALSHI_TEAM_ALIASES else None


# Patterns this v0 understands. The Kalshi single-game ticker format is:
#   KXNBAGAME-<YYMMDD>-<AWAY><HOME>-<BET_TEAM>
# Example: KXNBAGAME-26MAY01CLETOR-CLE = "Will Cleveland beat Toronto?"
_KALSHI_NBA_RE = re.compile(
    r"^KXNBAGAME-\d{2}[A-Z]{3}\d{2}([A-Z]{2,4})([A-Z]{2,4})-([A-Z]{2,4})$"
)


@dataclass(frozen=True)
class _ParsedNbaMarket:
    away: str
    home: str
    bet_on: str  # team being predicted YES


def _parse_kalshi_nba(ticker: str) -> Optional[_ParsedNbaMarket]:
    """Parse a Kalshi single-game NBA ticker. Returns None on miss.

    The away+home concatenation in the middle of the ticker makes parsing
    ambiguous — we try splitting at common 3-3 / 2-3 / 3-2 boundaries.
    """
    m = _KALSHI_NBA_RE.match(ticker.strip())
    if m is None:
        return None
    pair, bet_team = (m.group(1) + m.group(2)), m.group(3)
    bet_norm = _normalize_team(bet_team)
    if bet_norm is None:
        return None
    # Try 3-3, 2-3, 3-2, 2-2 splits.
    for left_len in (3, 2, 4):
        if left_len >= len(pair):
            continue
        right_len = len(pair) - left_len
        if right_len < 2 or right_len > 4:
            continue
        away_raw, home_raw = pair[:left_len], pair[left_len:]
        away = _normalize_team(away_raw)
        home = _normalize_team(home_raw)
        if away and home and bet_norm in (away, home):
            return _ParsedNbaMarket(away=away, home=home, bet_on=bet_norm)
    return None


def _elo_win_probability(home: str, away: str) -> Optional[float]:
    """Standard Elo expected score with a small home-court adjustment."""
    r_home = _NBA_ELO.get(home)
    r_away = _NBA_ELO.get(away)
    if r_home is None or r_away is None:
        return None
    HOME_COURT_ELO = 60.0  # ~3 pts in 538-style models
    diff = (r_home + HOME_COURT_ELO) - r_away
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


async def generate_elo_predictions(
    session: AsyncSession,
    *,
    min_edge: float = 0.05,
    confidence: float = 0.60,
    dedup_window_seconds: int = 1800,
    lookback_hours: int = 12,
) -> int:
    """Iterate open Kalshi NBA markets that have a recent price, parse
    teams, compute Elo win-prob, emit Predictions for under-priced sides.
    Returns count of new Predictions written.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=dedup_window_seconds)
    price_cutoff = now - timedelta(hours=lookback_hours)

    markets = (await session.execute(
        select(Market).where(
            Market.platform == "kalshi",
            Market.status == "open",
            Market.external_id.like("KXNBAGAME-%"),
        )
    )).scalars().all()

    n = 0
    for market in markets:
        parsed = _parse_kalshi_nba(market.external_id)
        if parsed is None:
            continue

        win_p = _elo_win_probability(parsed.home, parsed.away)
        if win_p is None:
            continue
        # Probability for the team being bet ("yes" outcome).
        p_model = win_p if parsed.bet_on == parsed.home else (1.0 - win_p)
        if p_model <= 0.0 or p_model >= 1.0:
            continue

        latest_price = (await session.execute(
            select(MarketPrice)
            .where(MarketPrice.market_id == market.id)
            .where(MarketPrice.time >= price_cutoff)
            .order_by(MarketPrice.time.desc())
            .limit(1)
        )).scalar_one_or_none()
        if latest_price is None:
            continue
        market_price = (
            float(latest_price.last_price)
            if latest_price.last_price is not None
            else float(latest_price.bid or latest_price.ask or 0.0)
        )
        if market_price <= 0.0 or market_price >= 1.0:
            continue

        edge = p_model - market_price
        if edge < min_edge:
            continue

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
            predicted_prob=round(p_model, 4),
            confidence=round(confidence, 3),
            market_price_at_prediction=round(market_price, 4),
            edge=round(edge, 4),
        ))
        # Mediating-factor breadcrumbs for the market detail page.
        home_elo = _NBA_ELO.get(parsed.home, 0.0)
        away_elo = _NBA_ELO.get(parsed.away, 0.0)
        for name, value in (
            ("home_team_elo", float(home_elo)),
            ("away_team_elo", float(away_elo)),
            ("home_advantage_elo", 60.0),
            ("home_win_probability", float(win_p)),
        ):
            session.add(PredictionFeature(
                prediction_id=prediction_id,
                feature_name=name,
                value=value,
                version=1,
            ))
        n += 1

    if n > 0:
        await session.commit()
        logger.info("elo_sports: emitted %d Prediction(s)", n)
    return n
