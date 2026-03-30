from typing import List, Dict, Optional
from dataclasses import dataclass
from sigil.models import Market
from sigil.config import config
import logging

logger = logging.getLogger(__name__)

@dataclass
class ArbOpportunity:
    market_a: Market
    market_b: Market
    side_a: str # 'yes' or 'no'
    side_b: str
    price_a: float
    price_b: float
    net_profit: float # Total return for $1.00 risk

class ArbDetector:
    """
    Detects cross-platform arbitrage opportunities.
    Condition: P(Yes)_A + P(No)_B < 1.0 (after fees)
    """
    def __init__(self, fee_buffer: float = 0.05):
        self.fee_buffer = fee_buffer

    def detect(self, market_a: Market, market_b: Market, price_a_yes: float, price_b_no: float) -> Optional[ArbOpportunity]:
        """Checks if an arb exists between two matched markets."""
        # Note: Prices should be in [0.0, 1.0]
        
        # 1. Calculate implied costs including fee buffers
        # Kalshi: ~7 cents fee (0.07). Polymarket: ~2% taker (0.02)
        fee_a = 0.07 if market_a.platform == "kalshi" else 0.02
        fee_b = 0.07 if market_b.platform == "kalshi" else 0.02
        
        total_cost = price_a_yes + price_b_no + fee_a + fee_b
        
        if total_cost < 1.0:
            profit = 1.0 - total_cost
            if profit > 0.02: # Minimum 2% profit threshold
                return ArbOpportunity(
                    market_a=market_a,
                    market_b=market_b,
                    side_a="yes",
                    side_b="no",
                    price_a=price_a_yes,
                    price_b=price_b_no,
                    net_profit=profit
                )
        
        # Check reverse: No_A + Yes_B
        # (Simplified: typically you check all permutations)
        return None
