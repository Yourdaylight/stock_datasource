"""Data sync scheduler for automated daily data synchronization.

Uses the lightweight `schedule` library.

Scheduled jobs:
- Daily data sync: create incremental sync tasks for enabled daily plugins
- Daily analysis: run portfolio analysis after data sync

Config is persisted in `runtime_config.json` under `scheduler`.
"""

import logging
import threading
import time as time_module
from datetime import datetime, date
from typing import Optional, Dict, Any

import schedule

logger = logging.getLogger(__name__)


class DataSyncScheduler:
    """Scheduler for automated data synchronization and analysis tasks."""

    def __init__(self):
        self._is_running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Default schedule times
        self.data_sync_time = "18:00"
        self.analysis_time = "18:30"
        self.enabled = False

        # Task tracking
        self._last_data_sync: Optional[str] = None
        self._last_analysis: Optional[str] = None
        self._current_task: Optional[str] = None

    def start(self):
        """Start scheduler.

        Idempotent: if already running, it will reload config and reschedule jobs.
        """
        self._load_config()

        with self._lock:
            self._setup_schedules()

        if self._is_running:
            logger.info(
                "Data sync scheduler refreshed (enabled=%s, data_sync=%s, analysis=%s)",
                self.enabled,
                self.data_sync_time,
                self.analysis_time,
            )
            return

        self._is_running = True
        self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self._scheduler_thread.start()

        logger.info(
            "Data sync scheduler started (enabled=%s, data_sync=%s, analysis=%s)",
            self.enabled,
            self.data_sync_time,
            self.analysis_time,
        )

    def stop(self):
        """Stop scheduler."""
        if not self._is_running:
            logger.warning("Data sync scheduler is not running")
            return

        logger.info("Stopping data sync scheduler...")
        self._is_running = False

        with self._lock:
            schedule.clear()

        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5)

        logger.info("Data sync scheduler stopped")

    def _load_config(self):
        """Load scheduler config from runtime config."""
        try:
            from ..config.runtime_config import load_runtime_config

            runtime_cfg = load_runtime_config()
            scheduler_cfg = runtime_cfg.get("scheduler", {})

            self.enabled = bool(scheduler_cfg.get("enabled", False))
            self.data_sync_time = scheduler_cfg.get("data_sync_time", "18:00")
            self.analysis_time = scheduler_cfg.get("analysis_time", "18:30")

            # Validate time format
            datetime.strptime(self.data_sync_time, "%H:%M")
            datetime.strptime(self.analysis_time, "%H:%M")

        except Exception as e:
            logger.warning(f"Failed to load scheduler config: {e}")

    def _setup_schedules(self):
        """Clear and set up scheduled tasks."""
        schedule.clear()

        if not self.enabled:
            logger.info("Scheduler is disabled, no jobs scheduled")
            return

        schedule.every().day.at(self.data_sync_time).do(self._run_data_sync_job)
        schedule.every().day.at(self.analysis_time).do(self._run_analysis_job)

        logger.info(f"Jobs scheduled: data_sync@{self.data_sync_time}, analysis@{self.analysis_time}")

    def _run_scheduler(self):
        """Run scheduler loop in background thread."""
        logger.info("Scheduler thread started")

        while self._is_running:
            try:
                with self._lock:
                    schedule.run_pending()
                time_module.sleep(30)
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                time_module.sleep(60)

        logger.info("Scheduler thread stopped")

    def _run_data_sync_job(self):
        """Execute the data sync job."""
        logger.info("Data sync job triggered")
        self._current_task = "data_sync"

        try:
            if not self._is_trading_day():
                logger.info("Today is not a trading day, skipping data sync")
                return

            self._execute_data_sync()
            self._last_data_sync = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Data sync job failed: {e}")
        finally:
            self._current_task = None

    def _run_analysis_job(self):
        """Execute the analysis job."""
        logger.info("Analysis job triggered")
        self._current_task = "analysis"

        try:
            if not self._is_trading_day():
                logger.info("Today is not a trading day, skipping analysis")
                return

            self._execute_analysis()
            self._last_analysis = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Analysis job failed: {e}")
        finally:
            self._current_task = None

    def _is_trading_day(self, check_date: Optional[date] = None) -> bool:
        """Check if the given date is a trading day."""
        check_date = check_date or date.today()

        try:
            from ..modules.datamanage.service import data_manage_service

            trading_days = data_manage_service.get_trading_days(days=7)
            return check_date.strftime("%Y%m%d") in trading_days
        except Exception as e:
            logger.warning(f"Failed to check trading day: {e}")
            return check_date.weekday() < 5

    def _execute_data_sync(self):
        """Create incremental sync tasks for all enabled daily plugins."""
        logger.info("Starting data synchronization...")

        from ..core.plugin_manager import plugin_manager
        from ..modules.datamanage.service import sync_task_manager

        plugins = plugin_manager.get_plugin_list()
        daily_plugins: list[str] = []

        for plugin_name in plugins:
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if plugin and plugin.is_enabled():
                    schedule_info = plugin.get_schedule()
                    if schedule_info.get("frequency") == "daily":
                        daily_plugins.append(plugin_name)
            except Exception as e:
                logger.warning(f"Failed to check plugin {plugin_name}: {e}")

        logger.info(f"Found {len(daily_plugins)} daily plugins to sync")

        trade_date = date.today().strftime("%Y%m%d")
        for plugin_name in daily_plugins:
            try:
                task = sync_task_manager.create_task(
                    plugin_name=plugin_name,
                    task_type="incremental",
                    trade_dates=[trade_date],
                    user_id="scheduler",
                    username="scheduler",
                )
                logger.info(f"Created sync task for {plugin_name}: {task.task_id}")
            except Exception as e:
                logger.error(f"Failed to create sync task for {plugin_name}: {e}")

        logger.info("Data synchronization tasks created")

    def _execute_analysis(self):
        """Execute daily analysis (best-effort)."""
        logger.info("Starting daily analysis...")

        try:
            import asyncio
            from ..services.daily_analysis_service import get_daily_analysis_service

            service = get_daily_analysis_service()
            if hasattr(service, "run_daily_analysis"):
                asyncio.run(service.run_daily_analysis("default_user"))
            else:
                logger.warning("DailyAnalysisService has no run_daily_analysis method")

        except Exception as e:
            logger.error(f"Daily analysis failed: {e}")
            raise

        logger.info("Daily analysis completed")

    def update_data_sync_time(self, time_str: str):
        """Update data sync time and reschedule jobs."""
        datetime.strptime(time_str, "%H:%M")
        self.data_sync_time = time_str

        if self._is_running:
            with self._lock:
                self._setup_schedules()

        logger.info(f"Data sync time updated to {time_str}")

    def update_analysis_time(self, time_str: str):
        """Update analysis time and reschedule jobs."""
        datetime.strptime(time_str, "%H:%M")
        self.analysis_time = time_str

        if self._is_running:
            with self._lock:
                self._setup_schedules()

        logger.info(f"Analysis time updated to {time_str}")

    def run_data_sync_now(self):
        """Manually trigger data sync immediately."""
        logger.info("Manual data sync triggered")
        threading.Thread(target=self._run_data_sync_job, daemon=True).start()

    def run_analysis_now(self):
        """Manually trigger analysis immediately."""
        logger.info("Manual analysis triggered")
        threading.Thread(target=self._run_analysis_job, daemon=True).start()

    def get_status(self) -> Dict[str, Any]:
        """Get current scheduler status."""
        next_data_sync = None
        next_analysis = None

        with self._lock:
            for job in schedule.jobs:
                job_name = str(job.job_func)
                if "data_sync" in job_name and job.next_run:
                    next_data_sync = job.next_run.isoformat()
                elif "analysis" in job_name and job.next_run:
                    next_analysis = job.next_run.isoformat()

        return {
            "is_running": self._is_running,
            "enabled": self.enabled,
            "data_sync_time": self.data_sync_time,
            "analysis_time": self.analysis_time,
            "next_data_sync": next_data_sync,
            "next_analysis": next_analysis,
            "last_data_sync": self._last_data_sync,
            "last_analysis": self._last_analysis,
            "current_task": self._current_task,
            "thread_alive": self._scheduler_thread.is_alive() if self._scheduler_thread else False,
        }


# Global scheduler instance
_data_sync_scheduler: Optional[DataSyncScheduler] = None


def get_data_sync_scheduler() -> DataSyncScheduler:
    """Get the data sync scheduler instance."""
    global _data_sync_scheduler
    if _data_sync_scheduler is None:
        _data_sync_scheduler = DataSyncScheduler()
    return _data_sync_scheduler


async def start_data_sync_scheduler():
    """Start the data sync scheduler."""
    scheduler = get_data_sync_scheduler()
    scheduler.start()


async def stop_data_sync_scheduler():
    """Stop the data sync scheduler."""
    scheduler = get_data_sync_scheduler()
    scheduler.stop()
