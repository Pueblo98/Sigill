import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from sigil.alerts.telegram import TelegramAlerts
from sigil.config import config
from sigil.db import AsyncSessionLocal
from sigil.execution.bankroll import snapshot_bankroll
from sigil.ingestion.kalshi import KalshiDataSource
from sigil.ingestion.manager import MarketManager
from sigil.ingestion.settlement import (
    KalshiSettlementStream,
    SettlementHandler,
    run_poll_fallback,
    run_ws_subscriber,
)

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


def build_settlement_tasks() -> list[asyncio.Task]:
    """Spawn the WS subscriber + hourly polling fallback as background tasks.

    Both default to off (`SETTLEMENT_WS_ENABLED=False`) so the orchestrator
    can run on a paper-only laptop without trying to connect to Kalshi.
    """
    if not config.SETTLEMENT_WS_ENABLED:
        logger.info("Settlement subscriber disabled (SETTLEMENT_WS_ENABLED=false).")
        return []

    source = KalshiSettlementStream()
    handler = SettlementHandler(AsyncSessionLocal)
    tasks = [
        asyncio.create_task(run_ws_subscriber(source, handler), name="settlement_ws"),
        asyncio.create_task(
            run_poll_fallback(source, handler, AsyncSessionLocal),
            name="settlement_poll",
        ),
    ]
    logger.info(
        "Started settlement subscriber + hourly polling fallback (interval=%ds)",
        config.SETTLEMENT_FALLBACK_POLL_INTERVAL_SECONDS,
    )
    return tasks


async def main_loop():
    """Heartbeat: market sync + drawdown bankroll snapshots + settlement."""
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

    settlement_tasks = build_settlement_tasks()

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
        for t in settlement_tasks:
            t.cancel()
        if settlement_tasks:
            await asyncio.gather(*settlement_tasks, return_exceptions=True)
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
