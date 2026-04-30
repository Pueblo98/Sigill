"""
stat_arb.py — Statistical Arbitrage Scanner: Kalshi ↔ Polymarket

Fetches live markets from both platforms, fuzzy-matches equivalent events
by title, then surfaces:
  - PURE_ARB:  Guaranteed profit (buy YES on A + NO on B < $1 after fees)
  - STAT_EDGE: Significant price divergence (≥5¢ mid gap) suggesting mispricing

No database required — fetches directly from both REST APIs.

Usage:
    python -m sigil.decision.stat_arb                # one-shot scan
    python -m sigil.decision.stat_arb --loop 60      # scan every 60 seconds
    python -m sigil.decision.stat_arb --min-profit 3 # 3¢ min arb profit
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from rapidfuzz import fuzz

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────
KALSHI_BASE         = "https://trading-api.kalshi.com/trade-api/v2"
POLY_BASE           = "https://clob.polymarket.com"

KALSHI_TAKER_FEE    = 0.07   # 7¢ per $1 of YES contracts
POLY_TAKER_FEE      = 0.02   # 2% CLOB taker fee

DEFAULT_MIN_ARB     = 0.01   # 1¢ minimum guaranteed profit to surface
DEFAULT_MIN_EDGE    = 0.05   # 5¢ mid-price gap to surface as stat edge
DEFAULT_THRESHOLD   = 80.0   # rapidfuzz token_sort_ratio minimum [0–100]
DEFAULT_KELLY       = 0.25   # quarter-Kelly
MAX_STAT_ARB_KELLY  = 0.10   # cap stat-edge positions at 10% of bankroll

KALSHI_PAGE_LIMIT   = 200    # markets per Kalshi page
POLY_PAGE_LIMIT     = 500    # markets per Polymarket page


# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class MarketSnapshot:
    """Normalized, platform-agnostic snapshot of one market."""
    platform: str            # "kalshi" | "polymarket"
    external_id: str         # Kalshi ticker OR Polymarket condition_id
    yes_token_id: Optional[str]   # Polymarket YES token id (needed for price lookup)
    title: str               # human-readable question
    category: str            # taxonomy label
    yes_bid: Optional[float] # [0, 1] — best bid for YES
    yes_ask: Optional[float] # [0, 1] — best ask for YES
    resolution_date: Optional[str]

    @property
    def mid(self) -> Optional[float]:
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return self.yes_bid or self.yes_ask

    @property
    def spread(self) -> Optional[float]:
        if self.yes_bid is not None and self.yes_ask is not None:
            return self.yes_ask - self.yes_bid
        return None


@dataclass
class ArbOpportunity:
    """Detected arbitrage or statistical-edge opportunity between two matched markets."""
    kalshi: MarketSnapshot
    polymarket: MarketSnapshot
    match_score: float          # fuzzy title similarity [0, 100]
    opportunity_type: str       # "PURE_ARB" | "STAT_EDGE"

    # Trade legs
    leg_a_platform: str
    leg_a_outcome: str          # "YES" or "NO"
    leg_a_price: float          # price to execute at

    leg_b_platform: str
    leg_b_outcome: str
    leg_b_price: float

    gross_cost: float           # leg_a + leg_b
    fee_cost: float             # combined platform fees
    net_profit: float           # 1 - gross - fees (arb) | mid divergence (stat edge)

    @property
    def kelly_size(self) -> float:
        """Suggested position as a fraction of bankroll using quarter-Kelly."""
        if self.opportunity_type == "PURE_ARB":
            # Risk-free: Kelly = profit / (1 + profit), scaled by fraction
            raw = self.net_profit / max(1 + self.net_profit, 1e-9)
            return min(raw * DEFAULT_KELLY, 0.25)
        else:
            # Stat edge: assume 60% chance prices converge our way
            # Kelly = (p*b - (1-p)) / b  where b = expected gain per $1 risked
            p, b = 0.60, max(self.net_profit, 1e-9)
            raw = max(0.0, (p * b - (1 - p)) / b)
            return min(raw * DEFAULT_KELLY, MAX_STAT_ARB_KELLY)

    def display(self) -> str:
        k, p = self.kalshi, self.polymarket
        sep = "─" * 70

        k_prices = (
            f"bid={k.yes_bid:.3f}  ask={k.yes_ask:.3f}  mid={k.mid:.3f}"
            if k.yes_bid is not None else f"mid={k.mid}"
        )
        p_prices = (
            f"bid={p.yes_bid:.3f}  ask={p.yes_ask:.3f}  mid={p.mid:.3f}"
            if p.yes_bid is not None else f"mid={p.mid}"
        )

        lines = [
            sep,
            f"  TYPE:        {self.opportunity_type}",
            f"  MATCH SCORE: {self.match_score:.1f} / 100",
            f"",
            f"  KALSHI      ({k.external_id})",
            f"    {k.title}",
            f"    {k_prices}",
            f"",
            f"  POLYMARKET  ({p.external_id[:12]}...)",
            f"    {p.title}",
            f"    {p_prices}",
            f"",
            f"  TRADE LEGS:",
            f"    A → Buy {self.leg_a_outcome:3s} on {self.leg_a_platform:<12s} @ {self.leg_a_price:.4f}",
            f"    B → Buy {self.leg_b_outcome:3s} on {self.leg_b_platform:<12s} @ {self.leg_b_price:.4f}",
            f"",
            f"  Gross cost:  {self.gross_cost:.4f}",
            f"  Fee cost:    {self.fee_cost:.4f}",
            f"  Net profit:  {self.net_profit * 100:+.2f}¢ per $1",
            f"  Kelly size:  {self.kelly_size * 100:.2f}% of bankroll",
            sep,
        ]
        return "\n".join(lines)


# ─── Platform fetchers ────────────────────────────────────────────────────────

class KalshiFetcher:
    """Pulls all active Kalshi markets (with bid/ask prices) via REST."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_all(self) -> list[MarketSnapshot]:
        markets: list[MarketSnapshot] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"status": "open", "limit": KALSHI_PAGE_LIMIT}
            if cursor:
                params["cursor"] = cursor

            try:
                r = await self.client.get(f"{KALSHI_BASE}/markets", params=params, timeout=15)
                r.raise_for_status()
                body = r.json()
            except Exception as exc:
                logger.error(f"Kalshi fetch failed: {exc}")
                break

            raw_markets = body.get("markets", [])
            for m in raw_markets:
                yes_bid_cents = m.get("yes_bid")
                yes_ask_cents = m.get("yes_ask")
                snap = MarketSnapshot(
                    platform="kalshi",
                    external_id=m.get("ticker", ""),
                    yes_token_id=None,
                    title=m.get("title", ""),
                    category=(m.get("category") or "unknown").lower(),
                    yes_bid=yes_bid_cents / 100.0 if yes_bid_cents is not None else None,
                    yes_ask=yes_ask_cents / 100.0 if yes_ask_cents is not None else None,
                    resolution_date=m.get("close_time"),
                )
                if snap.title and snap.external_id:
                    markets.append(snap)

            cursor = body.get("cursor")
            if not cursor or not raw_markets:
                break

        logger.info(f"Kalshi: fetched {len(markets)} active markets")
        return markets


class PolymarketFetcher:
    """Pulls active Polymarket markets then batch-fetches YES midpoint prices."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def fetch_all(self) -> list[MarketSnapshot]:
        # Phase 1: get market metadata
        snapshots: list[MarketSnapshot] = []
        cursor: Optional[str] = None

        while True:
            params: dict = {"active": "true", "closed": "false", "limit": POLY_PAGE_LIMIT}
            if cursor:
                params["next_cursor"] = cursor

            try:
                r = await self.client.get(f"{POLY_BASE}/markets", params=params, timeout=15)
                r.raise_for_status()
                body = r.json()
            except Exception as exc:
                logger.error(f"Polymarket fetch failed: {exc}")
                break

            raw_markets = body.get("data", []) if isinstance(body, dict) else body

            for m in raw_markets:
                if not m.get("active"):
                    continue

                # Grab the YES token id from the tokens array
                yes_token_id: Optional[str] = None
                for tok in m.get("tokens", []):
                    if tok.get("outcome", "").lower() == "yes":
                        yes_token_id = tok.get("token_id")
                        break

                snap = MarketSnapshot(
                    platform="polymarket",
                    external_id=m.get("condition_id", ""),
                    yes_token_id=yes_token_id,
                    title=m.get("question", ""),
                    category=(m.get("category") or "unknown").lower(),
                    yes_bid=None,
                    yes_ask=None,
                    resolution_date=m.get("end_date_iso"),
                )
                if snap.title and snap.external_id:
                    snapshots.append(snap)

            cursor = body.get("next_cursor") if isinstance(body, dict) else None
            if not cursor or not raw_markets:
                break

        logger.info(f"Polymarket: fetched {len(snapshots)} active markets")

        # Phase 2: batch-fetch midpoint prices for all markets with a YES token
        await self._enrich_with_prices(snapshots)
        return snapshots

    async def _enrich_with_prices(self, snapshots: list[MarketSnapshot]) -> None:
        """Batch-fetches midpoint prices from Polymarket and patches snapshots in place."""
        token_to_snap: dict[str, MarketSnapshot] = {}
        for s in snapshots:
            if s.yes_token_id:
                token_to_snap[s.yes_token_id] = s

        if not token_to_snap:
            return

        # Fetch in chunks of 100 to avoid huge query strings
        ids = list(token_to_snap.keys())
        chunk_size = 100

        for i in range(0, len(ids), chunk_size):
            chunk = ids[i : i + chunk_size]
            try:
                r = await self.client.get(
                    f"{POLY_BASE}/midpoints",
                    params={"token_ids": ",".join(chunk)},
                    timeout=15,
                )
                r.raise_for_status()
                prices: dict = r.json()  # {token_id: "0.62"}
            except Exception as exc:
                logger.warning(f"Polymarket midpoints fetch failed for chunk {i//chunk_size}: {exc}")
                continue

            for token_id, price_str in prices.items():
                snap = token_to_snap.get(token_id)
                if snap and price_str is not None:
                    try:
                        mid = float(price_str)
                        # Midpoint API gives one price; treat as both bid and ask
                        # (spread unknown without hitting /book per market)
                        snap.yes_bid = mid
                        snap.yes_ask = mid
                    except (ValueError, TypeError):
                        pass

        priced = sum(1 for s in snapshots if s.yes_bid is not None)
        logger.info(f"Polymarket: priced {priced}/{len(snapshots)} markets")


# ─── Matching ─────────────────────────────────────────────────────────────────

def fuzzy_match_markets(
    kalshi: list[MarketSnapshot],
    polymarket: list[MarketSnapshot],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[tuple[MarketSnapshot, MarketSnapshot, float]]:
    """
    Fuzzy-matches Kalshi ↔ Polymarket markets by title.
    Returns list of (kalshi_snap, poly_snap, score) tuples above threshold.
    Uses token_sort_ratio to handle reordered words and slight rewording.
    """
    # Pre-lowercase titles for matching
    poly_titles = [(p, p.title.lower()) for p in polymarket]
    matches: list[tuple[MarketSnapshot, MarketSnapshot, float]] = []
    seen_poly_ids: set[str] = set()  # prevent one Poly market matching multiple Kalshi

    for k in kalshi:
        k_title = k.title.lower()
        best_snap: Optional[MarketSnapshot] = None
        best_score = 0.0

        for p, p_title in poly_titles:
            # Skip already-claimed Polymarket markets
            if p.external_id in seen_poly_ids:
                continue

            score = fuzz.token_sort_ratio(k_title, p_title)

            # Bonus: same category bumps score slightly
            if k.category and p.category and k.category == p.category:
                score = min(score + 3, 100)

            if score > best_score and score >= threshold:
                best_score = score
                best_snap = p

        if best_snap is not None:
            seen_poly_ids.add(best_snap.external_id)
            matches.append((k, best_snap, best_score))

    logger.info(f"Matcher: {len(matches)} cross-platform pairs found (threshold={threshold})")
    return matches


# ─── Arb engine ───────────────────────────────────────────────────────────────

class ArbEngine:
    """Evaluates matched market pairs for arbitrage and statistical edge."""

    def __init__(
        self,
        min_arb_profit: float = DEFAULT_MIN_ARB,
        min_stat_divergence: float = DEFAULT_MIN_EDGE,
    ):
        self.min_arb_profit = min_arb_profit
        self.min_stat_divergence = min_stat_divergence

    def evaluate(
        self,
        kalshi: MarketSnapshot,
        polymarket: MarketSnapshot,
        match_score: float,
    ) -> list[ArbOpportunity]:
        """
        Checks all trade combinations for a matched pair.
        Returns up to 2 opportunities: one per arb direction plus any stat edge.
        """
        opps: list[ArbOpportunity] = []

        k_bid = kalshi.yes_bid
        k_ask = kalshi.yes_ask
        p_bid = polymarket.yes_bid
        p_ask = polymarket.yes_ask

        # Need at least a mid price on both sides
        if kalshi.mid is None or polymarket.mid is None:
            return opps

        # ── Pure arbitrage checks ───────────────────────────────────────────
        #
        # Direction A: Buy YES on Kalshi + Buy NO on Polymarket
        #   Cost of NO on Poly = 1 - poly.yes_bid  (selling YES means paying NO price)
        #   Gross cost = k_ask + (1 - p_bid)
        #   Payout = $1 regardless of outcome  →  net = 1 - gross - fees
        #
        # Direction B: Buy YES on Polymarket + Buy NO on Kalshi
        #   Gross cost = p_ask + (1 - k_bid)

        fee_total = KALSHI_TAKER_FEE + POLY_TAKER_FEE

        # Direction A
        if k_ask is not None and p_bid is not None:
            no_poly_ask = 1.0 - p_bid     # cost of buying NO on Polymarket
            gross_a = k_ask + no_poly_ask
            net_a = 1.0 - gross_a - fee_total
            if net_a >= self.min_arb_profit:
                opps.append(ArbOpportunity(
                    kalshi=kalshi,
                    polymarket=polymarket,
                    match_score=match_score,
                    opportunity_type="PURE_ARB",
                    leg_a_platform="kalshi",
                    leg_a_outcome="YES",
                    leg_a_price=k_ask,
                    leg_b_platform="polymarket",
                    leg_b_outcome="NO",
                    leg_b_price=no_poly_ask,
                    gross_cost=gross_a,
                    fee_cost=fee_total,
                    net_profit=net_a,
                ))

        # Direction B
        if p_ask is not None and k_bid is not None:
            no_kalshi_ask = 1.0 - k_bid   # cost of buying NO on Kalshi
            gross_b = p_ask + no_kalshi_ask
            net_b = 1.0 - gross_b - fee_total
            if net_b >= self.min_arb_profit:
                opps.append(ArbOpportunity(
                    kalshi=kalshi,
                    polymarket=polymarket,
                    match_score=match_score,
                    opportunity_type="PURE_ARB",
                    leg_a_platform="polymarket",
                    leg_a_outcome="YES",
                    leg_a_price=p_ask,
                    leg_b_platform="kalshi",
                    leg_b_outcome="NO",
                    leg_b_price=no_kalshi_ask,
                    gross_cost=gross_b,
                    fee_cost=fee_total,
                    net_profit=net_b,
                ))

        # ── Statistical edge / divergence ───────────────────────────────────
        # Even without a pure arb, a significant mid-price gap signals mispricing.
        # We surface this so you can take a directional convergence trade.
        k_mid = kalshi.mid
        p_mid = polymarket.mid
        divergence = abs(k_mid - p_mid)

        if divergence >= self.min_stat_divergence and not opps:
            # Bet the cheaper platform is under-pricing — buy YES there
            if k_mid < p_mid:
                # Kalshi is cheaper → buy YES on Kalshi
                buy_price = k_ask if k_ask is not None else k_mid
                opps.append(ArbOpportunity(
                    kalshi=kalshi,
                    polymarket=polymarket,
                    match_score=match_score,
                    opportunity_type="STAT_EDGE",
                    leg_a_platform="kalshi",
                    leg_a_outcome="YES",
                    leg_a_price=buy_price,
                    leg_b_platform="polymarket",
                    leg_b_outcome="YES",   # optional hedge: sell YES on Poly
                    leg_b_price=p_bid if p_bid is not None else p_mid,
                    gross_cost=buy_price,
                    fee_cost=KALSHI_TAKER_FEE,
                    net_profit=divergence,  # expected convergence gain
                ))
            else:
                # Polymarket is cheaper → buy YES on Polymarket
                buy_price = p_ask if p_ask is not None else p_mid
                opps.append(ArbOpportunity(
                    kalshi=kalshi,
                    polymarket=polymarket,
                    match_score=match_score,
                    opportunity_type="STAT_EDGE",
                    leg_a_platform="polymarket",
                    leg_a_outcome="YES",
                    leg_a_price=buy_price,
                    leg_b_platform="kalshi",
                    leg_b_outcome="YES",   # optional hedge: sell YES on Kalshi
                    leg_b_price=k_bid if k_bid is not None else k_mid,
                    gross_cost=buy_price,
                    fee_cost=POLY_TAKER_FEE,
                    net_profit=divergence,
                ))

        return opps


# ─── Main scanner ─────────────────────────────────────────────────────────────

class StatArbScanner:
    """
    Orchestrates a full Kalshi ↔ Polymarket stat-arb scan cycle.

    Usage:
        scanner = StatArbScanner()
        opportunities = await scanner.scan()
    """

    def __init__(
        self,
        min_arb_profit: float = DEFAULT_MIN_ARB,
        min_stat_divergence: float = DEFAULT_MIN_EDGE,
        fuzzy_threshold: float = DEFAULT_THRESHOLD,
    ):
        self.engine = ArbEngine(min_arb_profit, min_stat_divergence)
        self.fuzzy_threshold = fuzzy_threshold

    async def scan(self) -> list[ArbOpportunity]:
        """Run one full scan cycle. Returns opportunities sorted by net_profit desc."""
        async with httpx.AsyncClient() as client:
            kalshi_f = KalshiFetcher(client)
            poly_f = PolymarketFetcher(client)

            # Fetch both platforms concurrently
            kalshi_markets, poly_markets = await asyncio.gather(
                kalshi_f.fetch_all(),
                poly_f.fetch_all(),
            )

        # Match and evaluate
        pairs = fuzzy_match_markets(
            kalshi_markets, poly_markets, threshold=self.fuzzy_threshold
        )

        all_opps: list[ArbOpportunity] = []
        for k, p, score in pairs:
            opps = self.engine.evaluate(k, p, score)
            all_opps.extend(opps)

        # Sort: PURE_ARB first, then by net_profit descending
        all_opps.sort(
            key=lambda o: (o.opportunity_type != "PURE_ARB", -o.net_profit)
        )

        logger.info(
            f"Scan complete: {len(pairs)} pairs evaluated → "
            f"{sum(1 for o in all_opps if o.opportunity_type == 'PURE_ARB')} arbs, "
            f"{sum(1 for o in all_opps if o.opportunity_type == 'STAT_EDGE')} stat edges"
        )
        return all_opps

    async def run_loop(self, interval_seconds: int = 60) -> None:
        """Continuously scan on a fixed interval, printing results each cycle."""
        logger.info(f"Starting stat-arb loop (interval={interval_seconds}s). Ctrl+C to stop.")
        while True:
            start = datetime.now(timezone.utc)
            try:
                opps = await self.scan()
                _print_results(opps)
            except Exception as exc:
                logger.error(f"Scan cycle failed: {exc}", exc_info=True)

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            sleep_for = max(0, interval_seconds - elapsed)
            logger.info(f"Next scan in {sleep_for:.0f}s …")
            await asyncio.sleep(sleep_for)


# ─── Output helpers ───────────────────────────────────────────────────────────

def _print_results(opps: list[ArbOpportunity]) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*70}")
    print(f"  STAT ARB SCAN  |  {ts}")
    print(f"  {len(opps)} opportunities found")
    print(f"{'='*70}\n")

    if not opps:
        print("  No opportunities above thresholds.\n")
        return

    arbs   = [o for o in opps if o.opportunity_type == "PURE_ARB"]
    edges  = [o for o in opps if o.opportunity_type == "STAT_EDGE"]

    if arbs:
        print(f"  ▶ PURE ARBITRAGE ({len(arbs)})\n")
        for o in arbs:
            print(o.display())

    if edges:
        print(f"\n  ▶ STAT EDGES / DIVERGENCE ({len(edges)})\n")
        for o in edges:
            print(o.display())


# ─── CLI entry point ──────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kalshi ↔ Polymarket statistical arbitrage scanner"
    )
    parser.add_argument(
        "--loop",
        type=int,
        metavar="SECONDS",
        default=0,
        help="Repeat scan every N seconds (default: one-shot)",
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        metavar="CENTS",
        default=DEFAULT_MIN_ARB * 100,
        help=f"Minimum guaranteed profit in cents for PURE_ARB (default: {DEFAULT_MIN_ARB*100:.0f}¢)",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        metavar="CENTS",
        default=DEFAULT_MIN_EDGE * 100,
        help=f"Minimum mid-price divergence in cents for STAT_EDGE (default: {DEFAULT_MIN_EDGE*100:.0f}¢)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        metavar="SCORE",
        default=DEFAULT_THRESHOLD,
        help=f"Fuzzy match threshold 0–100 (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show DEBUG-level logs",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scanner = StatArbScanner(
        min_arb_profit=args.min_profit / 100.0,
        min_stat_divergence=args.min_edge / 100.0,
        fuzzy_threshold=args.threshold,
    )

    if args.loop > 0:
        await scanner.run_loop(interval_seconds=args.loop)
    else:
        opps = await scanner.scan()
        _print_results(opps)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        sys.exit(0)
