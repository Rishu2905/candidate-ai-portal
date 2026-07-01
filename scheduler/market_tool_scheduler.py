from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def refresh_market_jobs():
    """
    Refreshes market jobs from Indeed.
    Currently stubbed — will be implemented after prototype.
    """
    logger.info("Market refresh triggered — stubbed for prototype")
    pass


def start_scheduler():
    try:
        scheduler.add_job(
            refresh_market_jobs,
            trigger="interval",
            weeks=2,
            id="market_refresh"
        )
        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Scheduler failed to start: {e}")


def stop_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped")
    except Exception as e:
        logger.error(f"Scheduler failed to stop: {e}")