from rapidfuzz import fuzz
from typing import List, Dict, Optional
from sigil.models import Market
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

class MarketMatcher:
    """
    The 'Synapse' of Sigil: Matches equivalent markets across different platforms.
    Essential for detecting Arbitrage.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_matches(self, target_market: Market, threshold: float = 85.0) -> List[Market]:
        """Finds all other markets that likely represent the same event."""
        # 1. Get candidate markets with same taxonomy and similar resolution date
        stmt = select(Market).where(
            Market.id != target_market.id,
            Market.taxonomy_l1 == target_market.taxonomy_l1,
            Market.status == "open"
        )
        result = await self.session.execute(stmt)
        candidates = result.scalars().all()

        matches = []
        for candidate in candidates:
            # 2. String similarity on titles
            score = fuzz.token_sort_ratio(target_market.title, candidate.title)
            
            # 3. Date check (must resolve within 24 hours of each other)
            date_match = False
            if target_market.resolution_date and candidate.resolution_date:
                diff = abs(target_market.resolution_date - candidate.resolution_date)
                if diff.total_seconds() < 86400: # 24 hours
                    date_match = True
            
            if score >= threshold and date_match:
                matches.append(candidate)
                logger.info(f"Match found: '{target_market.title}' [{target_market.platform}] == '{candidate.title}' [{candidate.platform}] (Score: {score})")

        return matches
