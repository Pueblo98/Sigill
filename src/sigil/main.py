import asyncio
import logging
from sigil.db import AsyncSessionLocal
from sigil.ingestion.manager import MarketManager
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.alerts.telegram import TelegramAlerts
from sigil.config import config

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sigil.orchestrator")

async def main_loop():
    """
    The Heartbeat of Sigil: Orchestrates the continuous cycle of 
    ingestion, intelligence, and alerting.
    """
    logger.info("Initializing Sigil Orchestrator...")
    
    # 1. Initialize Components
    kalshi_source = KalshiDataSource()
    alerts = TelegramAlerts()
    
    while True:
        try:
            logger.info("--- Starting New Sync Cycle ---")
            
            async with AsyncSessionLocal() as session:
                manager = MarketManager(session)
                
                # 2. Sync Markets
                await manager.sync_source(kalshi_source)
                
                # 3. (Place Future Logic Here: Run Elo models, detect edge, send alerts)
                # For now, just a heartbeat
                logger.info("Sync complete. Checking for signals...")
                
            # 4. Wait for next refresh interval
            await asyncio.sleep(kalshi_source.refresh_interval)
            
        except asyncio.CancelledError:
            logger.info("Orchestrator shutting down...")
            break
        except Exception as e:
            logger.exception(f"Unexpected error in main loop: {str(e)}")
            await asyncio.sleep(30) # Wait before retry

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
