"""Integration with the existing UnifiedScheduler."""

import asyncio
import logging
from datetime import datetime

from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

JOB_SENTINEL_SCAN = "sentinel_daily_scan"
JOB_SENTINEL_INTRADAY = "sentinel_intraday_check"


def register_sentinel_jobs(scheduler) -> None:
    """Register sentinel jobs with APScheduler.

    Called from UnifiedScheduler or app startup.
    """
    # Daily full scan at 18:45 (after data sync at 18:00)
    scheduler.add_job(
        _run_daily_scan,
        CronTrigger(hour=18, minute=45, day_of_week="mon-fri"),
        id=JOB_SENTINEL_SCAN,
        name="Sentinel daily scan",
        replace_existing=True,
    )

    # Intraday quick scan every 30 min during trading hours
    scheduler.add_job(
        _run_intraday_check,
        CronTrigger(minute="*/30", hour="9-14", day_of_week="mon-fri"),
        id=JOB_SENTINEL_INTRADAY,
        name="Sentinel intraday check",
        replace_existing=True,
    )

    logger.info("Registered sentinel scheduler jobs")


def _run_daily_scan() -> None:
    """Execute full sentinel scan cycle."""
    logger.info("Sentinel daily scan triggered at %s", datetime.now().isoformat())
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(registry.run_scan_cycle())
            logger.info(
                "Daily scan result: %s alerts, %s reports, decision=%s",
                result.get("sentinel_alerts"),
                result.get("analyst_reports"),
                result.get("decision_produced"),
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error("Sentinel daily scan failed: %s", e, exc_info=True)


def _run_intraday_check() -> None:
    """Quick intraday check - only market risk + volume sentinels."""
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_intraday_subset(registry))
        finally:
            loop.close()
    except Exception as e:
        logger.error("Sentinel intraday check failed: %s", e)


async def _intraday_subset(registry) -> None:
    """Run only market-critical sentinels during trading hours."""
    if not registry._initialized:
        await registry.initialize()

    intraday_types = {"market_risk", "volume_anomaly"}
    for sentinel in registry._sentinels:
        if sentinel.SENTINEL_TYPE in intraday_types:
            await sentinel.execute_scan()
