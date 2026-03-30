import httpx
import pandas as pd
from typing import Any, List
from sigil.ingestion.base import DataSource
from sigil.config import config

class PolymarketDataSource(DataSource):
    """
    Ingests market data from the Polymarket Central Limit Order Book (CLOB).
    """
    name: str = "polymarket_clob"
    refresh_interval: int = 30  # Poly is more dynamic

    def __init__(self, base_url: str = "https://clob.polymarket.com"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=base_url)

    async def fetch(self) -> List[dict]:
        """Fetch active markets from Polymarket."""
        # Querying active markets via the CLOB API
        response = await self.client.get("/markets")
        response.raise_for_status()
        return response.json()

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        """Standardizes Polymarket data to match Sigil taxonomy."""
        normalized = []
        for m in raw_data:
            # Polymarket events can have multiple tokens (Yes/No)
            # We map them to our internal market structure
            normalized.append({
                "external_id": m.get("condition_id"),
                "platform": "polymarket",
                "title": m.get("question"),
                "taxonomy_l1": m.get("category", "unknown").lower(),
                "market_type": "binary", # CLOB primarily binary
                "status": "open" if m.get("active") else "closed",
                "resolution_date": m.get("end_date_iso"),
            })
        return pd.DataFrame(normalized)

    def validate(self, df: pd.DataFrame) -> bool:
        return "external_id" in df.columns and not df.empty
