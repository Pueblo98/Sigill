import pandas as pd
from typing import Dict, List
from datetime import timedelta
from sigil.features.base import FeatureExtractor

class EloRatingExtractor(FeatureExtractor):
    """
    Computes Elo ratings for teams across multiple leagues.
    Maintains independent rating pools for NFL, NBA, etc.
    """
    name: str = "team_elo_rating"
    version: str = "1.1.0"
    refresh_interval: timedelta = timedelta(days=1)
    dependencies: List[str] = ["espn_scoreboard"]

    def __init__(self, k_factor: int = 20):
        self.k_factor = k_factor
        # Dictionary of dictionaries: {league: {team_abbrev: rating}}
        self.ratings: Dict[str, Dict[str, float]] = {}

    def compute(self, game_results: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Expects a DataFrame with: ['league', 'home_team', 'away_team', 'home_score', 'away_score']
        Updates ratings and returns a dictionary of Series (one per league).
        """
        if game_results.empty:
            return {}

        for _, row in game_results.iterrows():
            league = row['league']
            home = row['home_team']
            away = row['away_team']
            
            if league not in self.ratings:
                self.ratings[league] = {}

            # Initial rating of 1500 for new teams in this league
            r_home = self.ratings[league].get(home, 1500.0)
            r_away = self.ratings[league].get(away, 1500.0)

            # 1. Calculate expected scores
            e_home = 1 / (1 + 10 ** ((r_away - r_home) / 400))
            e_away = 1 - e_home

            # 2. Actual outcome (S_i)
            if row['home_score'] > row['away_score']:
                s_home, s_away = 1, 0
            elif row['home_score'] < row['away_score']:
                s_home, s_away = 0, 1
            else:
                s_home, s_away = 0.5, 0.5

            # 3. Update ratings
            self.ratings[league][home] = r_home + self.k_factor * (s_home - e_home)
            self.ratings[league][away] = r_away + self.k_factor * (s_away - e_away)

        return {league: pd.Series(ratings) for league, ratings in self.ratings.items()}

    def get_win_probability(self, league: str, home_team: str, away_team: str) -> float:
        """Calculates win probability for home team based on current Elo ratings."""
        if league not in self.ratings:
            return 0.5
        r_home = self.ratings[league].get(home_team, 1500.0)
        r_away = self.ratings[league].get(away_team, 1500.0)
        return 1 / (1 + 10 ** ((r_away - r_home) / 400))
