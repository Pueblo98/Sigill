import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sigil.alerts.telegram import TelegramAlerts
from sigil.config import config
from sigil.db import AsyncSessionLocal
from sigil.execution.bankroll import snapshot_bankroll
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.ingestion.manager import MarketManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sigil.orchestrator")


BANKROLL_SNAPSHOT_INTERVAL_SECONDS = 300


async def _snapshot_job():
    async with AsyncSessionLocal() as session:
        try:
            await snapshot_bankroll(session, mode=config.DEFAULT_MODE)
        except Exception:
            logger.exception("bankroll snapshot job failed")


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _snapshot_job,
        trigger="interval",
        seconds=BANKROLL_SNAPSHOT_INTERVAL_SECONDS,
        id="bankroll_snapshot",
        replace_existing=True,
        next_run_time=None,
    )
    return scheduler


async def main_loop():
    """Heartbeat: market sync + drawdown-input bankroll snapshots."""
    logger.info("Initializing Sigil Orchestrator...")

    kalshi_source = KalshiDataSource()
    alerts = TelegramAlerts()  # noqa: F841 — wired up for future use

    scheduler = build_scheduler()
    scheduler.start()
    logger.info(
        "Started APScheduler (bankroll snapshot every %ds, mode=%s)",
        BANKROLL_SNAPSHOT_INTERVAL_SECONDS,
        config.DEFAULT_MODE,
    )

    try:
        while True:
            try:
                logger.info("--- Starting New Sync Cycle ---")

                async with AsyncSessionLocal() as session:
                    manager = MarketManager(session)
                    await manager.sync_source(kalshi_source)
                    logger.info("Sync complete. Checking for signals...")

                await asyncio.sleep(kalshi_source.refresh_interval)

            except asyncio.CancelledError:
                logger.info("Orchestrator shutting down...")
                break
            except Exception as e:
                logger.exception(f"Unexpected error in main loop: {str(e)}")
                await asyncio.sleep(30)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
