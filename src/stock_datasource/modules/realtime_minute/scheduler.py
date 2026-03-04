"""Scheduler integration for realtime minute data collection and sync.

Provides standalone functions that can be registered with the UnifiedScheduler
or called directly.  Includes pause/resume control so that
``RealtimeManageService`` can start/stop collection via the global switch.
"""

import logging
from datetime import datetime
from typing import Optional

from . import config as cfg

logger = logging.getLogger(__name__)

# Module-level reference to the APScheduler instance so that
# pause_collection / resume_collection can be called from anywhere.
_scheduler_ref: Optional[object] = None

COLLECT_JOB_ID = "rt_minute_collect"
SYNC_JOB_ID = "rt_minute_sync"
CLEANUP_JOB_ID = "rt_minute_cleanup"


# ------------------------------------------------------------------
# Core task functions
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Pause / Resume helpers (called by RealtimeManageService)
# ------------------------------------------------------------------

def get_scheduler():
    """Return the stored APScheduler reference (may be None)."""
    return _scheduler_ref


def pause_collection() -> bool:
    """Pause the collection job. Returns True if successfully paused."""
    sched = _scheduler_ref
    if sched is None:
        logger.warning("Cannot pause: scheduler reference not set")
        return False
    try:
        sched.pause_job(COLLECT_JOB_ID)
        logger.info("Realtime minute collection PAUSED")
        return True
    except Exception as e:
        logger.warning("Failed to pause collection job: %s", e)
        return False


def resume_collection() -> bool:
    """Resume the collection job. Returns True if successfully resumed."""
    sched = _scheduler_ref
    if sched is None:
        logger.warning("Cannot resume: scheduler reference not set")
        return False
    try:
        sched.resume_job(COLLECT_JOB_ID)
        logger.info("Realtime minute collection RESUMED")
        return True
    except Exception as e:
        logger.warning("Failed to resume collection job: %s", e)
        return False


def is_collection_paused() -> bool:
    """Check whether the collection job is currently paused."""
    sched = _scheduler_ref
    if sched is None:
        return True
    try:
        job = sched.get_job(COLLECT_JOB_ID)
        if job is None:
            return True
        return job.next_run_time is None  # paused jobs have next_run_time=None
    except Exception:
        return True


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_realtime_jobs(scheduler) -> None:
    """Register realtime minute jobs with an APScheduler BackgroundScheduler.

    The collection job is registered in *paused* state by default.
    Use ``resume_collection()`` (or the management API) to activate it
    only when ``runtime_config.realtime.enabled`` is True.
    """
    global _scheduler_ref
    _scheduler_ref = scheduler

    from apscheduler.triggers.cron import CronTrigger
    from stock_datasource.config.runtime_config import get_realtime_config

    # Collection job: every minute during trading hours (Mon-Fri)
    def _collection_wrapper():
        # Double-check: honour the runtime config even if the job wasn't paused
        rt_cfg = get_realtime_config()
        if not rt_cfg.get("enabled", False):
            return
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
        id=COLLECT_JOB_ID,
        name="Realtime minute data collection",
        replace_existing=True,
    )
    logger.info("Registered %s job (every minute, Mon-Fri)", COLLECT_JOB_ID)

    # Sync job: 15:30 Mon-Fri (always active – harmless when no data)
    sync_h, sync_m = map(int, cfg.SYNC_TIME.split(":"))
    scheduler.add_job(
        run_sync,
        CronTrigger(hour=sync_h, minute=sync_m, day_of_week="mon-fri"),
        id=SYNC_JOB_ID,
        name="Realtime minute data sync to ClickHouse",
        replace_existing=True,
    )
    logger.info("Registered %s job at %s Mon-Fri", SYNC_JOB_ID, cfg.SYNC_TIME)

    # Cleanup job: 03:00 daily (always active)
    cleanup_h, cleanup_m = map(int, cfg.CLEANUP_TIME.split(":"))
    scheduler.add_job(
        run_cleanup,
        CronTrigger(hour=cleanup_h, minute=cleanup_m),
        id=CLEANUP_JOB_ID,
        name="Realtime minute Redis cleanup",
        replace_existing=True,
    )
    logger.info("Registered %s job at %s daily", CLEANUP_JOB_ID, cfg.CLEANUP_TIME)

    # Default state: pause collection if not enabled in config
    rt_cfg = get_realtime_config()
    if not rt_cfg.get("enabled", False):
        scheduler.pause_job(COLLECT_JOB_ID)
        logger.info("Collection job paused (realtime.enabled=False)")
    else:
        logger.info("Collection job active (realtime.enabled=True)")
