import asyncio
import logging
import json
import os
from datetime import datetime
from sqlalchemy import select
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.ingestion.polymarket import PolymarketDataSource
from sigil.models import MarketPrice, Market
import sigil.db
from sigil.db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurable batching settings
BATCH_INTERVAL = 1.0  # seconds
RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")

os.makedirs(RAW_DATA_DIR, exist_ok=True)

class StreamProcessor:
    def __init__(self, source_name: str, cache_file: str):
        self.batch = []
        self.source_name = source_name
        self.cache_file = cache_file

    async def flush_batch(self):
        while True:
            await asyncio.sleep(BATCH_INTERVAL)
            if not self.batch:
                continue
            
            # Copy and clear
            current_batch = self.batch.copy()
            self.batch.clear()

            # 1. Save to RAW Local Lake (as requested)
            with open(self.cache_file, "a") as f:
                for item in current_batch:
                    # Time needs to be stringified for JSON
                    item_copy = item.copy()
                    item_copy["time"] = item_copy["time"].isoformat()
                    f.write(json.dumps(item_copy) + "\n")

            # 2. Save to Postgres MarketPrice Table
            async with sigil.db.AsyncSessionLocal() as session:
                from dateutil.parser import parse
                for item in current_batch:
                    try:
                        time_val = item["time"]
                        if isinstance(time_val, str):
                            time_val = parse(time_val)
                            
                        mp = MarketPrice(
                            market_id=item["market_id"], # We'll assume the external_id is passed as market_id for simplicity
                            bid=item.get("bid", 0.0),
                            ask=item.get("ask", 0.0),
                            last_price=item.get("last_price", 0.0),
                            volume_24h=item.get("volume_24h", 0.0),
                            time=time_val
                        )
                        session.add(mp)
                    except Exception as e:
                        pass # Silently drop malformed ticks
                await session.commit()

            logger.info(f"[{self.source_name}] Flushed {len(current_batch)} price ticks.")

    async def consume_stream(self, source, market_ids):
        logger.info(f"[{self.source_name}] Starting stream for {len(market_ids)} markets...")
        try:
            async for tick in source.stream_prices(market_ids):
                self.batch.append(tick)
        except Exception as e:
            logger.error(f"[{self.source_name}] Stream error: {e}")

async def run_ingestion():
    # Setup Database Fallbacks / Postgres
    await init_db()

    kalshi_source = KalshiDataSource()
    poly_source = PolymarketDataSource()

    logger.info("Bootstrapping Database with Active Markets...")
    # Seed top 10 Kalshi markets into DB so Next.js Dashboard has data
    kalshi_ids = []
    top_10 = []
    try:
        kal_raw = await kalshi_source.fetch()
        kal_df = kalshi_source.normalize(kal_raw)
        top_10 = kal_df.head(10).to_dict('records')
    except Exception as e:
        logger.warning(f"Failed to fetch Kalshi markets live ({e}). Falling back to sample seed data.")
        top_10 = [
            {"external_id": "KAL-BTC-100K", "title": "Will Bitcoin reach $100k by EOY?", "taxonomy_l1": "crypto"},
            {"external_id": "KAL-FED-DEC", "title": "Will the Federal Reserve cut rates in December?", "taxonomy_l1": "economics"},
            {"external_id": "KAL-NFL-KC", "title": "Will the Kansas City Chiefs win the Super Bowl?", "taxonomy_l1": "sports"},
        ]

    async with sigil.db.AsyncSessionLocal() as session:
        for m in top_10:
            ext_id = m['external_id']
            kalshi_ids.append(ext_id)
            existing = await session.execute(select(Market).where(Market.external_id == ext_id))
            if not existing.scalars().first():
                new_market = Market(
                    platform="kalshi",
                    external_id=ext_id,
                    title=m['title'],
                    taxonomy_l1=m.get('taxonomy_l1', 'general'),
                    market_type="binary",
                    status="open"
                )
                session.add(new_market)
        await session.commit()
        logger.info(f"Seeded {len(kalshi_ids)} Kalshi markets into local DB.")

    logger.info("Bootstrapping Polymarket Active Markets...")
    poly_ids = []
    try:
        poly_raw = await poly_source.fetch()
        poly_df = poly_source.normalize(poly_raw)
        poly_top = poly_df.tail(60).to_dict('records') # Grab the newest appended active chunks
        
        async with sigil.db.AsyncSessionLocal() as session:
            for m in poly_top:
                ext_id = m['external_id']
                if not ext_id:
                    continue
                poly_ids.append(ext_id)
                existing = await session.execute(select(Market).where(Market.external_id == ext_id))
                if not existing.scalars().first():
                    new_market = Market(
                        platform="polymarket",
                        external_id=ext_id,
                        title=m.get('title', 'Unknown Polymarket Event'),
                        taxonomy_l1=m.get('taxonomy_l1', 'general'),
                        market_type="binary",
                        status="open"
                    )
                    session.add(new_market)
            await session.commit()
            logger.info(f"Seeded {len(poly_ids)} Polymarket markets into DB.")
    except Exception as e:
        logger.error(f"Failed to fetch Polymarket: {e}")

    # For safety to ensure stream gets exactly the active mock IDs we want 
    # if Poly API fails, we could mock it, but Poly API is publicly open.

    kalshi_processor = StreamProcessor("Kalshi", os.path.join(RAW_DATA_DIR, "kalshi_ticks.jsonl"))
    poly_processor = StreamProcessor("Polymarket", os.path.join(RAW_DATA_DIR, "polymarket_ticks.jsonl"))

    # Run producers and consumers concurrently
    await asyncio.gather(
        kalshi_processor.consume_stream(kalshi_source, kalshi_ids),
        poly_processor.consume_stream(poly_source, poly_ids),
        kalshi_processor.flush_batch(),
        poly_processor.flush_batch()
    )

if __name__ == "__main__":
    try:
        asyncio.run(run_ingestion())
    except KeyboardInterrupt:
        logger.info("Ingestion stopped.")
