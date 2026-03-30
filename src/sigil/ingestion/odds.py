import httpx
import pandas as pd
from typing import Any, List, Dict, Optional
from sigil.ingestion.base import DataSource
from sigil.config import config
import logging

logger = logging.getLogger(__name__)

class TheOddsAPISource(DataSource):
    """
    Ingests live odds from 50+ traditional bookmakers.
    Used to detect 'Synthetic Edge' by comparing Bookie odds vs Prediction Markets.
    """
    name: str = "the_odds_api"
    refresh_interval: int = 600  # 10 minutes (save API credits)

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY")
        self.base_url = "https://api.the-odds-api.com/v4/sports"
        self.client = httpx.AsyncClient()

    async def fetch_odds(self, sport: str = "americanfootball_nfl", regions: str = "us") -> List[dict]:
        """Fetch odds for a specific sport and region."""
        if not self.api_key:
            logger.warning("The Odds API key missing. Skipping fetch.")
            return []

        params = {
            "api_key": self.api_key,
            "regions": regions,
            "markets": "h2h", # Head-to-head (Moneyline)
            "oddsFormat": "decimal"
        }
        
        try:
            response = await self.client.get(f"{self.base_url}/{sport}/odds", params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch Odds API data: {e}")
            return []

    async def fetch(self) -> List[dict]:
        # Default to NFL for now
        return await self.fetch_odds()

    def normalize(self, raw_data: List[dict]) -> pd.DataFrame:
        """
        Normalizes odds data to compare against our internal market structure.
        """
        normalized = []
        for event in raw_data:
            home_team = event.get("home_team")
            away_team = event.get("away_team")
            
            for bookmaker in event.get("bookmakers", []):
                book_name = bookmaker.get("title")
                for market in bookmaker.get("markets", []):
                    if market.get("key") == "h2h":
                        outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                        
                        # Convert decimal odds to implied probability: 1 / decimal_odds
                        prob_home = 1 / outcomes.get(home_team) if outcomes.get(home_team) else None
                        prob_away = 1 / outcomes.get(away_team) if outcomes.get(away_team) else None

                        normalized.append({
                            "event_id": event.get("id"),
                            "bookmaker": book_name,
                            "home_team": home_team,
                            "away_team": away_team,
                            "prob_home": prob_home,
                            "prob_away": prob_away,
                            "commence_time": event.get("commence_time")
                        })
        return pd.DataFrame(normalized)

    def validate(self, df: pd.DataFrame) -> bool:
        return not df.empty and "prob_home" in df.columns
