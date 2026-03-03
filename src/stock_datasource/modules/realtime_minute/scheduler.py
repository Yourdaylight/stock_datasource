"""Scheduler integration for realtime minute data collection and sync.

Provides standalone functions that can be registered with the UnifiedScheduler
or called directly.
"""

import logging
from datetime import datetime

from . import config as cfg

logger = logging.getLogger(__name__)


def run_collection(freq: str = "1min", markets=None) -> dict:
    """Execute one round of data collection → Redis.

    This is the function that the scheduler calls every minute
    during trading hours.
    """
    from .collector import get_collector
    from .cache_store import get_cache_store

    collector = get_collector()
    cache = get_cache_store()

    data = collector.collect_all(freq=freq, markets=markets)

    result = {}
    total = 0
    for market_name, df in data.items():
        if df is not None and not df.empty:
            count = cache.store_bars(df)
            cache.update_status(market_name, count)
            result[market_name] = count
            total += count
        else:
            result[market_name] = 0

    logger.info("Collection round finished: %d total bars, details=%s", total, result)
    return result


def run_sync(date: str | None = None) -> dict:
    """Sync today's Redis data to ClickHouse.

    Called once after market close (default 15:30).
    """
    from .sync_service import get_sync_service

    svc = get_sync_service()
    return svc.sync(date)


def run_cleanup(date: str | None = None) -> dict:
    """Clean up Redis cache for a given date.

    Called daily at 03:00.
    """
    from .sync_service import get_sync_service

    svc = get_sync_service()
    return svc.cleanup(date)


def is_trading_time() -> bool:
    """Check if current time is within A-share trading hours."""
    now = datetime.now()
    time_str = now.strftime("%H:%M")
    for start, end in cfg.CN_TRADING_HOURS:
        if start <= time_str <= end:
            return True
    return False


def register_realtime_jobs(scheduler) -> None:
    """Register realtime minute jobs with an APScheduler BackgroundScheduler.

    This should be called from the UnifiedScheduler after it starts,
    if realtime collection is enabled.
    """
    from apscheduler.triggers.cron import CronTrigger

    # Collection job: every minute during trading hours (Mon-Fri)
    def _collection_wrapper():
        if is_trading_time():
            try:
                run_collection()
            except Exception as e:
                logger.error("Scheduled collection failed: %s", e, exc_info=True)
        else:
            logger.debug("Outside trading hours, skipping collection")

    scheduler.add_job(
        _collection_wrapper,
        CronTrigger(minute="*/1", day_of_week="mon-fri"),
        id="rt_minute_collect",
        name="Realtime minute data collection",
        replace_existing=True,
    )
    logger.info("Registered rt_minute_collect job (every minute, Mon-Fri)")

    # Sync job: 15:30 Mon-Fri
    sync_h, sync_m = map(int, cfg.SYNC_TIME.split(":"))
    scheduler.add_job(
        run_sync,
        CronTrigger(hour=sync_h, minute=sync_m, day_of_week="mon-fri"),
        id="rt_minute_sync",
        name="Realtime minute data sync to ClickHouse",
        replace_existing=True,
    )
    logger.info("Registered rt_minute_sync job at %s Mon-Fri", cfg.SYNC_TIME)

    # Cleanup job: 03:00 daily
    cleanup_h, cleanup_m = map(int, cfg.CLEANUP_TIME.split(":"))
    scheduler.add_job(
        run_cleanup,
        CronTrigger(hour=cleanup_h, minute=cleanup_m),
        id="rt_minute_cleanup",
        name="Realtime minute Redis cleanup",
        replace_existing=True,
    )
    logger.info("Registered rt_minute_cleanup job at %s daily", cfg.CLEANUP_TIME)
