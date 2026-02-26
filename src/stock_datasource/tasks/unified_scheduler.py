"""Unified scheduler for automated data sync, missing-data checks, and smart backfill.

Replaces the legacy ``DataSyncScheduler`` (``schedule`` library) with a single
APScheduler ``BackgroundScheduler`` that drives **all** timed work.  The real
business logic still lives in ``ScheduleService`` – this module is purely
responsible for *when* things run.

Config is read from ``runtime_config.json`` → ``scheduler`` section.
"""

from __future__ import annotations

import json
import logging
import threading
import time as _time
from datetime import datetime, date, time
from typing import Any, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Job IDs (constants for reschedule / remove)
JOB_DAILY_SYNC = "unified_daily_sync"
JOB_MISSING_CHECK = "unified_missing_check"

# Default configuration values
_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "execute_time": "18:00",
    "frequency": "weekday",
    "skip_non_trading_days": True,
    "missing_check_time": "16:00",
    "smart_backfill_enabled": True,
    "auto_backfill_max_days": 3,
}

# How often to poll task statuses when waiting for completion (seconds)
_POLL_INTERVAL = 10
# Maximum time to wait for all tasks to complete (seconds)
_POLL_TIMEOUT = 7200  # 2 hours


class UnifiedScheduler:
    """Singleton APScheduler-backed scheduler.

    Lifecycle
    ---------
    1. ``start()`` – read config, create ``BackgroundScheduler``, register jobs.
    2. ``reschedule()`` – called when config is updated via API.
    3. ``stop()`` – graceful shutdown.
    """

    _instance: Optional["UnifiedScheduler"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "UnifiedScheduler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._scheduler: Optional[BackgroundScheduler] = None
        self._config: Dict[str, Any] = dict(_DEFAULTS)
        self._running = False
        self._last_sync_report: Optional[Dict[str, Any]] = None
        self._last_missing_report: Optional[Dict[str, Any]] = None
        logger.info("UnifiedScheduler instance created")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler and register jobs based on config."""
        if self._running and self._scheduler and self._scheduler.running:
            logger.info("UnifiedScheduler already running – skipping start")
            return

        self._load_config()

        self._scheduler = BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600,  # 1 hour grace
            }
        )

        self._register_jobs()
        self._scheduler.start()
        self._running = True

        job_count = len(self._scheduler.get_jobs())
        if self._config.get("enabled"):
            logger.info("UnifiedScheduler started with %d jobs", job_count)
        else:
            logger.info("UnifiedScheduler started (disabled, no jobs registered)")

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        if not self._running or self._scheduler is None:
            logger.warning("UnifiedScheduler is not running")
            return

        logger.info("Stopping UnifiedScheduler...")
        try:
            self._scheduler.shutdown(wait=True)
        except Exception as exc:
            logger.warning("Error during scheduler shutdown: %s", exc)
        self._running = False
        logger.info("UnifiedScheduler stopped")

    def reschedule(self) -> None:
        """Reload config and re-register jobs (called after config update)."""
        if not self._running or self._scheduler is None:
            logger.warning("UnifiedScheduler is not running – cannot reschedule")
            return

        self._load_config()

        # Remove existing jobs then re-register
        for job_id in (JOB_DAILY_SYNC, JOB_MISSING_CHECK):
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass  # job may not exist

        self._register_jobs()
        logger.info("UnifiedScheduler rescheduled with updated config")

    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-friendly status dict."""
        jobs_info: List[Dict[str, Any]] = []
        next_sync_at: Optional[str] = None
        next_check_at: Optional[str] = None

        if self._scheduler and self._running:
            for job in self._scheduler.get_jobs():
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                info = {"job_id": job.id, "next_run_at": next_run}
                jobs_info.append(info)
                if job.id == JOB_DAILY_SYNC:
                    next_sync_at = next_run
                elif job.id == JOB_MISSING_CHECK:
                    next_check_at = next_run

        return {
            "is_running": self._running,
            "enabled": self._config.get("enabled", False),
            "execute_time": self._config.get("execute_time", "18:00"),
            "missing_check_time": self._config.get("missing_check_time", "16:00"),
            "frequency": self._config.get("frequency", "weekday"),
            "skip_non_trading_days": self._config.get("skip_non_trading_days", True),
            "smart_backfill_enabled": self._config.get("smart_backfill_enabled", True),
            "auto_backfill_max_days": self._config.get("auto_backfill_max_days", 3),
            "next_sync_at": next_sync_at,
            "next_check_at": next_check_at,
            "jobs": jobs_info,
            "last_sync_report": self._last_sync_report,
            "last_missing_report": self._last_missing_report,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load scheduler config from runtime_config.json."""
        try:
            from ..config.runtime_config import get_schedule_config

            saved = get_schedule_config()
            for key, default_val in _DEFAULTS.items():
                self._config[key] = saved.get(key, default_val)
        except Exception as exc:
            logger.warning("Failed to load scheduler config: %s", exc)

    def _register_jobs(self) -> None:
        """Register APScheduler jobs based on current config."""
        if not self._config.get("enabled"):
            logger.info("Scheduler is disabled – no jobs registered")
            return

        # --- Daily sync job ---
        exec_time = self._config.get("execute_time", "18:00")
        hour, minute = map(int, exec_time.split(":"))
        frequency = self._config.get("frequency", "weekday")

        if frequency == "daily":
            day_of_week = "mon-sun"
        else:
            day_of_week = "mon-fri"

        self._scheduler.add_job(
            self._daily_sync_job,
            CronTrigger(hour=hour, minute=minute, day_of_week=day_of_week),
            id=JOB_DAILY_SYNC,
            name="Daily data sync",
            replace_existing=True,
        )
        logger.info(
            "Registered daily sync job: %s %s:%02d (%s)",
            JOB_DAILY_SYNC, hour, minute, day_of_week,
        )

        # --- Missing data check job ---
        # Missing check runs every day (mon-sun), including non-trading days,
        # because data from previous trading days may still need backfilling.
        check_time = self._config.get("missing_check_time", "16:00")
        chk_hour, chk_minute = map(int, check_time.split(":"))

        self._scheduler.add_job(
            self._missing_check_job,
            CronTrigger(hour=chk_hour, minute=chk_minute, day_of_week="mon-sun"),
            id=JOB_MISSING_CHECK,
            name="Missing data check",
            replace_existing=True,
        )
        logger.info(
            "Registered missing check job: %s %s:%02d (every day)",
            JOB_MISSING_CHECK, chk_hour, chk_minute,
        )

    # ------------------------------------------------------------------
    # Job implementations
    # ------------------------------------------------------------------

    def _daily_sync_job(self) -> None:
        """Execute the daily data sync and generate an execution report."""
        triggered_at = datetime.now()
        logger.info("=" * 60)
        logger.info("Daily sync job triggered at %s", triggered_at.isoformat())
        logger.info("=" * 60)

        report: Dict[str, Any] = {
            "job_type": "daily_sync",
            "triggered_at": triggered_at.isoformat(),
            "completed_at": None,
            "duration_seconds": 0,
            "skipped": False,
            "skip_reason": None,
            "summary": {
                "total_plugins": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0,
            },
            "failures": [],
            "error": None,
        }

        try:
            if not self._should_run_today():
                report["skipped"] = True
                report["skip_reason"] = "non-trading day"
                report["completed_at"] = datetime.now().isoformat()
                self._last_sync_report = report
                logger.info("[REPORT] Daily sync skipped: non-trading day")
                return

            smart_backfill = self._config.get("smart_backfill_enabled", True)
            auto_backfill_max_days = self._config.get("auto_backfill_max_days", 3)

            from ..modules.datamanage.schedule_service import schedule_service

            record = schedule_service.trigger_now(
                is_manual=False,
                smart_backfill=smart_backfill,
                auto_backfill_max_days=auto_backfill_max_days,
            )

            # If trigger returned a skipped status (e.g. non-trading day at service level)
            if record.get("status") == "skipped":
                report["skipped"] = True
                report["skip_reason"] = record.get("skip_reason", "skipped by schedule_service")
                report["completed_at"] = datetime.now().isoformat()
                self._last_sync_report = report
                logger.info("[REPORT] Daily sync skipped: %s", report["skip_reason"])
                return

            task_ids = record.get("task_ids", [])
            total_plugins = record.get("total_plugins", len(task_ids))
            skipped_excessive = record.get("skipped_excessive_missing", [])

            report["summary"]["total_plugins"] = total_plugins
            report["summary"]["skipped"] = len(skipped_excessive)
            if skipped_excessive:
                report["skipped_excessive_missing"] = skipped_excessive

            # Poll and wait for all tasks to complete
            task_results = self._wait_for_tasks(task_ids)

            # Build report from task results
            succeeded = 0
            failed = 0
            failures: List[Dict[str, Any]] = []

            for task_info in task_results:
                if task_info["status"] == "completed":
                    succeeded += 1
                elif task_info["status"] in ("failed", "cancelled"):
                    failed += 1
                    failures.append({
                        "plugin": task_info["plugin_name"],
                        "task_id": task_info["task_id"],
                        "error_type": self._classify_error(task_info.get("error_message", "")),
                        "error_brief": (task_info.get("error_message", "") or "")[:200],
                    })

            report["summary"]["succeeded"] = succeeded
            report["summary"]["failed"] = failed
            report["failures"] = failures

            completed_at = datetime.now()
            report["completed_at"] = completed_at.isoformat()
            report["duration_seconds"] = round((completed_at - triggered_at).total_seconds(), 1)

            self._last_sync_report = report
            self._log_sync_report(report)

        except Exception as exc:
            completed_at = datetime.now()
            report["completed_at"] = completed_at.isoformat()
            report["duration_seconds"] = round((completed_at - triggered_at).total_seconds(), 1)
            report["error"] = str(exc)
            self._last_sync_report = report
            logger.error("Daily sync job failed: %s", exc, exc_info=True)
            self._log_sync_report(report)

    def _missing_check_job(self) -> None:
        """Execute the daily missing-data check and generate a report.

        NOTE: This job runs every day including non-trading days, because
        data from previous trading days may still be missing and needs to
        be detected and backfilled promptly.
        """
        triggered_at = datetime.now()
        logger.info("=" * 60)
        logger.info("Missing data check job triggered at %s", triggered_at.isoformat())
        logger.info("=" * 60)

        report: Dict[str, Any] = {
            "job_type": "missing_check",
            "triggered_at": triggered_at.isoformat(),
            "completed_at": None,
            "duration_seconds": 0,
            "data_quality": {
                "total_plugins": 0,
                "plugins_with_missing": 0,
                "total_missing_dates": 0,
                "needs_attention": [],
            },
            "error": None,
        }

        try:
            from ..modules.datamanage.service import data_manage_service

            summary = data_manage_service.detect_missing_data(days=30, force_refresh=True)

            report["data_quality"]["total_plugins"] = summary.total_plugins
            report["data_quality"]["plugins_with_missing"] = summary.plugins_with_missing

            total_missing = 0
            needs_attention: List[Dict[str, Any]] = []

            if summary.plugins_with_missing > 0:
                for plugin_info in summary.plugins:
                    if plugin_info.missing_count > 0:
                        total_missing += plugin_info.missing_count
                        needs_attention.append({
                            "plugin": plugin_info.plugin_name,
                            "missing_days": plugin_info.missing_count,
                        })

            report["data_quality"]["total_missing_dates"] = total_missing
            report["data_quality"]["needs_attention"] = needs_attention

            completed_at = datetime.now()
            report["completed_at"] = completed_at.isoformat()
            report["duration_seconds"] = round((completed_at - triggered_at).total_seconds(), 1)

            self._last_missing_report = report
            self._log_missing_report(report)

        except Exception as exc:
            completed_at = datetime.now()
            report["completed_at"] = completed_at.isoformat()
            report["duration_seconds"] = round((completed_at - triggered_at).total_seconds(), 1)
            report["error"] = str(exc)
            self._last_missing_report = report
            logger.error("Missing data check job failed: %s", exc, exc_info=True)
            self._log_missing_report(report)

    # ------------------------------------------------------------------
    # Execution report helpers
    # ------------------------------------------------------------------

    def _wait_for_tasks(
        self,
        task_ids: List[str],
        poll_interval: int = _POLL_INTERVAL,
        timeout: int = _POLL_TIMEOUT,
    ) -> List[Dict[str, Any]]:
        """Poll task statuses until all tasks are terminal or timeout.

        Returns a list of dicts with keys: task_id, plugin_name, status,
        error_message, records_processed.
        """
        if not task_ids:
            return []

        terminal_statuses = {"completed", "failed", "cancelled"}
        start = _time.monotonic()
        results: Dict[str, Dict[str, Any]] = {}

        while True:
            all_done = True
            try:
                from ..modules.datamanage.service import sync_task_manager

                for task_id in task_ids:
                    if task_id in results and results[task_id]["status"] in terminal_statuses:
                        continue  # already terminal

                    task = sync_task_manager.get_task(task_id)
                    if task is None:
                        results[task_id] = {
                            "task_id": task_id,
                            "plugin_name": "unknown",
                            "status": "failed",
                            "error_message": "Task not found in queue",
                            "records_processed": 0,
                        }
                        continue

                    status_val = task.status.value if hasattr(task.status, "value") else str(task.status)
                    results[task_id] = {
                        "task_id": task_id,
                        "plugin_name": task.plugin_name,
                        "status": status_val,
                        "error_message": task.error_message,
                        "records_processed": task.records_processed,
                    }

                    if status_val not in terminal_statuses:
                        all_done = False

            except Exception as exc:
                logger.warning("Error polling task statuses: %s", exc)
                all_done = False

            if all_done:
                break

            elapsed = _time.monotonic() - start
            if elapsed >= timeout:
                logger.warning(
                    "Task polling timed out after %ds, %d/%d tasks still running",
                    timeout,
                    sum(1 for r in results.values() if r["status"] not in terminal_statuses),
                    len(task_ids),
                )
                # Mark still-running tasks as timed out in the report
                for task_id in task_ids:
                    if task_id not in results or results[task_id]["status"] not in terminal_statuses:
                        results[task_id] = results.get(task_id, {
                            "task_id": task_id,
                            "plugin_name": "unknown",
                            "status": "running",
                            "error_message": None,
                            "records_processed": 0,
                        })
                        results[task_id]["error_message"] = "Report timeout: task still running"
                break

            _time.sleep(poll_interval)

        return list(results.values())

    @staticmethod
    def _classify_error(error_message: str) -> str:
        """Classify an error message into a human-readable category."""
        if not error_message:
            return "Unknown"

        msg_lower = error_message.lower()
        if any(kw in msg_lower for kw in ("rate limit", "too many request", "429", "freq")):
            return "Rate limit exceeded"
        if any(kw in msg_lower for kw in ("timeout", "timed out", "read timed")):
            return "Timeout"
        if any(kw in msg_lower for kw in ("connection", "connect", "refused", "unreachable")):
            return "Connection error"
        if any(kw in msg_lower for kw in ("permission", "auth", "401", "403", "token")):
            return "Authentication error"
        if any(kw in msg_lower for kw in ("not found", "404", "no data")):
            return "Data not found"
        if any(kw in msg_lower for kw in ("memory", "oom", "killed")):
            return "Resource exhaustion"
        return "Execution error"

    def _log_sync_report(self, report: Dict[str, Any]) -> None:
        """Output the daily sync execution report to structured log."""
        summary = report.get("summary", {})
        total = summary.get("total_plugins", 0)
        succeeded = summary.get("succeeded", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        duration = report.get("duration_seconds", 0)
        failures = report.get("failures", [])
        error = report.get("error")

        logger.info("=" * 60)
        logger.info("[EXECUTION REPORT] Daily Sync")
        logger.info("-" * 60)
        logger.info("  Triggered at : %s", report.get("triggered_at", "?"))
        logger.info("  Completed at : %s", report.get("completed_at", "?"))
        logger.info("  Duration     : %.1fs", duration)
        logger.info("-" * 60)
        logger.info("  Total plugins: %d", total)
        logger.info("  Succeeded    : %d", succeeded)
        logger.info("  Failed       : %d", failed)
        logger.info("  Skipped      : %d", skipped)

        if error:
            logger.error("  Job error    : %s", error)

        if failures:
            logger.warning("-" * 60)
            logger.warning("  Failed plugins:")
            for f in failures:
                logger.warning(
                    "    - %s [%s] (task: %s)",
                    f.get("plugin", "?"),
                    f.get("error_type", "?"),
                    f.get("task_id", "?"),
                )
                if f.get("error_brief"):
                    logger.warning("      %s", f["error_brief"])

        # Also output the full report as structured JSON for machine parsing
        logger.info("-" * 60)
        logger.info("[REPORT JSON] %s", json.dumps(report, ensure_ascii=False, default=str))
        logger.info("=" * 60)

    def _log_missing_report(self, report: Dict[str, Any]) -> None:
        """Output the missing data check report to structured log."""
        dq = report.get("data_quality", {})
        total_plugins = dq.get("total_plugins", 0)
        with_missing = dq.get("plugins_with_missing", 0)
        total_missing = dq.get("total_missing_dates", 0)
        needs_attention = dq.get("needs_attention", [])
        duration = report.get("duration_seconds", 0)
        error = report.get("error")

        logger.info("=" * 60)
        logger.info("[EXECUTION REPORT] Missing Data Check")
        logger.info("-" * 60)
        logger.info("  Triggered at        : %s", report.get("triggered_at", "?"))
        logger.info("  Completed at        : %s", report.get("completed_at", "?"))
        logger.info("  Duration            : %.1fs", duration)
        logger.info("-" * 60)
        logger.info("  Total plugins       : %d", total_plugins)
        logger.info("  Plugins with missing: %d", with_missing)
        logger.info("  Total missing dates : %d", total_missing)

        if error:
            logger.error("  Job error           : %s", error)

        if needs_attention:
            log_fn = logger.warning
            log_fn("-" * 60)
            log_fn("  Plugins needing attention:")
            for item in needs_attention:
                log_fn(
                    "    - %s : %d missing trading days",
                    item.get("plugin", "?"),
                    item.get("missing_days", 0),
                )
        else:
            logger.info("  ✅ All plugins data complete")

        # Output full report as structured JSON
        logger.info("-" * 60)
        logger.info("[REPORT JSON] %s", json.dumps(report, ensure_ascii=False, default=str))
        logger.info("=" * 60)

    def _should_run_today(self) -> bool:
        """Check if today is a valid run day (respects skip_non_trading_days).
        
        Returns True if today is a trading day in ANY market (A-share or HK),
        so that HK plugins are not skipped on HK trading days when A-share is closed.
        """
        if not self._config.get("skip_non_trading_days", True):
            return True

        try:
            from ..core.trade_calendar import TradeCalendarService, MARKET_CN, MARKET_HK

            calendar = TradeCalendarService()
            today = date.today()
            is_cn = calendar.is_trading_day(today, market=MARKET_CN)
            is_hk = calendar.is_trading_day(today, market=MARKET_HK)
            if is_cn or is_hk:
                return True
            logger.info("Today is not a trading day for either A-share or HK")
            return False
        except Exception as exc:
            logger.warning("Failed to check trading day, defaulting to weekday check: %s", exc)
            return date.today().weekday() < 5


# ---------------------------------------------------------------------------
# Module-level helpers (keep the same call-site pattern as old scheduler)
# ---------------------------------------------------------------------------

_unified_scheduler: Optional[UnifiedScheduler] = None


def get_unified_scheduler() -> UnifiedScheduler:
    """Return the global ``UnifiedScheduler`` singleton."""
    global _unified_scheduler
    if _unified_scheduler is None:
        _unified_scheduler = UnifiedScheduler()
    return _unified_scheduler


async def start_unified_scheduler() -> None:
    """Convenience coroutine for lifespan startup."""
    scheduler = get_unified_scheduler()
    scheduler.start()


async def stop_unified_scheduler() -> None:
    """Convenience coroutine for lifespan shutdown."""
    scheduler = get_unified_scheduler()
    scheduler.stop()
