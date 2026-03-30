import httpx
import pandas as pd
from typing import Any, List, Dict
from sigil.ingestion.base import DataSource
import logging

logger = logging.getLogger(__name__)

class ESPNResultSource(DataSource):
    """
    Ingests live and historical game results from ESPN's public API.
    Feeds the Elo Rating Engine for sports vertical edge detection.
    """
    name: str = "espn_scoreboard"
    refresh_interval: int = 300  # 5 minutes

    BASE_URLS = {
        "nfl": "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        "nba": "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    }

    def __init__(self, leagues: List[str] = ["nfl", "nba"]):
        self.leagues = leagues
        self.client = httpx.AsyncClient()

    async def fetch(self) -> Dict[str, Any]:
        """Fetch scoreboard data for all configured leagues."""
        results = {}
        for league in self.leagues:
            try:
                url = self.BASE_URLS.get(league)
                if not url:
                    continue
                response = await self.client.get(url)
                response.raise_for_status()
                results[league] = response.json()
            except Exception as e:
                logger.error(f"Failed to fetch ESPN data for {league}: {e}")
        return results

    def normalize(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Normalizes ESPN scoreboard into a flat structure for Elo updates.
        Columns: [league, home_team, away_team, home_score, away_score, status, game_date]
        """
        normalized_events = []
        
        for league, data in raw_data.items():
            events = data.get("events", [])
            for event in events:
                competitions = event.get("competitions", [])
                if not competitions:
                    continue
                
                comp = competitions[0]
                status = event.get("status", {}).get("type", {}).get("name")
                
                # We only want finished games for Elo updates
                if status != "STATUS_FINAL":
                    continue

                home_team = None
                away_team = None
                home_score = 0
                away_score = 0

                for team_data in comp.get("competitors", []):
                    if team_data.get("homeAway") == "home":
                        home_team = team_data.get("team", {}).get("abbreviation")
                        home_score = int(team_data.get("score", 0))
                    else:
                        away_team = team_data.get("team", {}).get("abbreviation")
                        away_score = int(team_data.get("score", 0))

                normalized_events.append({
                    "league": league,
                    "home_team": home_team,
                    "away_team": away_team,
                    "home_score": home_score,
                    "away_score": away_score,
                    "status": status,
                    "game_date": event.get("date")
                })

        return pd.DataFrame(normalized_events)

    def validate(self, df: pd.DataFrame) -> bool:
        required_cols = {"home_team", "away_team", "home_score", "away_score"}
        return required_cols.issubset(df.columns)
