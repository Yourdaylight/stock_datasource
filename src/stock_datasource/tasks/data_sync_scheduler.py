"""DEPRECATED: Legacy data sync scheduler.

This module is deprecated. Use ``tasks.unified_scheduler.UnifiedScheduler``
instead.  The functions below are kept solely for backward compatibility
with existing router imports.  They delegate to the new unified scheduler.
"""

from __future__ import annotations

import logging
import warnings
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Issue a deprecation warning on import
warnings.warn(
    "data_sync_scheduler is deprecated. Use tasks.unified_scheduler instead.",
    DeprecationWarning,
    stacklevel=2,
)


class DataSyncScheduler:
    """DEPRECATED compatibility wrapper.

    All calls are forwarded to ``UnifiedScheduler``.
    """

    def __init__(self) -> None:
        self._unified = None

    def _get_unified(self):
        if self._unified is None:
            from .unified_scheduler import get_unified_scheduler
            self._unified = get_unified_scheduler()
        return self._unified

    def start(self) -> None:
        self._get_unified().start()

    def stop(self) -> None:
        self._get_unified().stop()

    def get_status(self) -> Dict[str, Any]:
        """Return status in the old format for backward compatibility."""
        status = self._get_unified().get_status()
        return {
            "is_running": status.get("is_running", False),
            "enabled": status.get("enabled", False),
            "data_sync_time": status.get("execute_time", "18:00"),
            "analysis_time": "18:30",
            "next_data_sync": status.get("next_sync_at"),
            "next_analysis": None,
            "last_data_sync": None,
            "last_analysis": None,
            "current_task": None,
            "thread_alive": status.get("is_running", False),
        }

    @property
    def enabled(self) -> bool:
        return self._get_unified()._config.get("enabled", False)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        pass  # Config is managed via ScheduleService

    @property
    def data_sync_time(self) -> str:
        return self._get_unified()._config.get("execute_time", "18:00")

    @property
    def analysis_time(self) -> str:
        return "18:30"

    @property
    def _is_running(self) -> bool:
        return self._get_unified()._running

    def update_data_sync_time(self, time_str: str) -> None:
        pass  # Config is managed via ScheduleService

    def update_analysis_time(self, time_str: str) -> None:
        pass  # No-op

    def run_data_sync_now(self) -> None:
        """Trigger immediate sync via ScheduleService."""
        try:
            from ..modules.datamanage.schedule_service import schedule_service
            schedule_service.trigger_now(is_manual=True)
        except Exception as exc:
            logger.error("run_data_sync_now failed: %s", exc)

    def run_analysis_now(self) -> None:
        """No-op – analysis is not part of the unified scheduler."""
        logger.info("run_analysis_now is deprecated and does nothing")


# ---------------------------------------------------------------------------
# Module-level helpers (kept for backward compatibility)
# ---------------------------------------------------------------------------

_data_sync_scheduler: Optional[DataSyncScheduler] = None


def get_data_sync_scheduler() -> DataSyncScheduler:
    """Get the (deprecated) data sync scheduler instance."""
    global _data_sync_scheduler
    if _data_sync_scheduler is None:
        _data_sync_scheduler = DataSyncScheduler()
    return _data_sync_scheduler


async def start_data_sync_scheduler() -> None:
    """DEPRECATED: Start the data sync scheduler."""
    scheduler = get_data_sync_scheduler()
    scheduler.start()


async def stop_data_sync_scheduler() -> None:
    """DEPRECATED: Stop the data sync scheduler."""
    scheduler = get_data_sync_scheduler()
    scheduler.stop()
