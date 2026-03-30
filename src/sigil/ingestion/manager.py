from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sigil.models import Market
from sigil.ingestion.base import DataSource
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class MarketManager:
    """
    Orchestrates the lifecycle of markets in the database.
    Responsible for fetching from DataSources and performing Upserts.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_source(self, source: DataSource):
        """Fetch data from a source and sync it to the 'markets' table."""
        logger.info(f"Syncing source: {source.name}")
        
        try:
            raw_data = await source.fetch()
            df = source.normalize(raw_data)
            
            if not source.validate(df):
                logger.error(f"Validation failed for source: {source.name}")
                return

            for _, row in df.iterrows():
                await self.upsert_market(row.to_dict())
            
            await self.session.commit()
            logger.info(f"Successfully synced {len(df)} markets from {source.name}")
            
        except Exception as e:
            logger.exception(f"Failed to sync source {source.name}: {str(e)}")
            await self.session.rollback()

    async def upsert_market(self, data: dict):
        """Update existing market or insert new one based on platform + external_id."""
        stmt = select(Market).where(
            Market.platform == data["platform"],
            Market.external_id == data["external_id"]
        )
        result = await self.session.execute(stmt)
        market = result.scalar_one_or_none()

        if market:
            # Update existing fields
            for key, value in data.items():
                setattr(market, key, value)
        else:
            # Create new market
            market = Market(**data)
            self.session.add(market)
