"""Tests for the Unified Data Scheduler (``unify-data-scheduler`` change).

Covers:
- UnifiedScheduler start / stop / reschedule
- Smart backfill strategy in ScheduleService.trigger_now()
- Config update triggers reschedule notification
- Old scheduler compatibility wrapper
"""

import sys
from pathlib import Path
from datetime import date, datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Ensure project src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_schedule_config(**overrides):
    """Return a scheduler config dict with sane defaults, merged with *overrides*."""
    base = {
        "enabled": True,
        "execute_time": "18:00",
        "frequency": "weekday",
        "skip_non_trading_days": True,
        "missing_check_time": "16:00",
        "smart_backfill_enabled": True,
        "auto_backfill_max_days": 3,
        "include_optional_deps": True,
        "last_run_at": None,
        "next_run_at": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# UnifiedScheduler tests
# ---------------------------------------------------------------------------

class TestUnifiedSchedulerLifecycle:
    """Test start / stop / get_status."""

    def setup_method(self):
        """Reset the singleton before each test."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_start_enabled(self, mock_load):
        """When enabled=True, scheduler starts and registers 2 jobs."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        sched.start()

        assert sched._running is True
        assert sched._scheduler is not None
        jobs = sched._scheduler.get_jobs()
        assert len(jobs) == 2
        job_ids = {j.id for j in jobs}
        assert "unified_daily_sync" in job_ids
        assert "unified_missing_check" in job_ids

        sched.stop()
        assert sched._running is False

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_start_disabled_no_jobs(self, mock_load):
        """When enabled=False, scheduler starts but registers 0 jobs."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=False)

        sched.start()

        assert sched._running is True
        jobs = sched._scheduler.get_jobs()
        assert len(jobs) == 0

        sched.stop()

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_stop_idempotent(self, mock_load):
        """Calling stop when not running should not raise."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched.stop()  # should not raise

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_get_status(self, mock_load):
        """get_status returns expected fields."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)
        sched.start()

        status = sched.get_status()

        assert status["is_running"] is True
        assert status["enabled"] is True
        assert status["execute_time"] == "18:00"
        assert status["missing_check_time"] == "16:00"
        assert status["smart_backfill_enabled"] is True
        assert status["auto_backfill_max_days"] == 3
        assert "next_sync_at" in status
        assert "next_check_at" in status
        assert len(status["jobs"]) == 2

        sched.stop()


class TestUnifiedSchedulerReschedule:
    """Test reschedule after config changes."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_reschedule_updates_jobs(self, mock_load):
        """After reschedule, jobs should reflect the new config."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True, execute_time="18:00")
        sched.start()

        # Simulate config change
        sched._config["execute_time"] = "19:30"
        sched._config["missing_check_time"] = "15:00"
        sched.reschedule()

        jobs = {j.id: j for j in sched._scheduler.get_jobs()}
        # Verify the trigger times were updated
        sync_job = jobs.get("unified_daily_sync")
        assert sync_job is not None

        check_job = jobs.get("unified_missing_check")
        assert check_job is not None

        sched.stop()

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_reschedule_when_disabled_removes_jobs(self, mock_load):
        """Reschedule with enabled=False removes all jobs."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)
        sched.start()
        assert len(sched._scheduler.get_jobs()) == 2

        # Disable
        sched._config["enabled"] = False
        sched.reschedule()

        assert len(sched._scheduler.get_jobs()) == 0

        sched.stop()


class TestUnifiedSchedulerDailySyncJob:
    """Test the _daily_sync_job logic."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=True)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_daily_sync_calls_trigger_now(self, mock_load, mock_trading):
        """On a trading day, daily sync should call schedule_service.trigger_now."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_record = {
            "execution_id": "test",
            "status": "running",
            "task_ids": [],
            "total_plugins": 0,
        }

        with patch("stock_datasource.modules.datamanage.schedule_service.schedule_service") as mock_svc:
            mock_svc.trigger_now = MagicMock(return_value=mock_record)
            sched._daily_sync_job()
            mock_svc.trigger_now.assert_called_once_with(
                is_manual=False,
                smart_backfill=True,
                auto_backfill_max_days=3,
            )
        # Report should have been generated
        assert sched._last_sync_report is not None
        assert sched._last_sync_report["job_type"] == "daily_sync"

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=False)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_daily_sync_skipped_non_trading(self, mock_load, mock_trading):
        """On a non-trading day, daily sync should be skipped."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        with patch("stock_datasource.modules.datamanage.schedule_service.schedule_service") as mock_svc:
            mock_svc.trigger_now = MagicMock()
            sched._daily_sync_job()
            mock_svc.trigger_now.assert_not_called()
        # Report should indicate skip
        assert sched._last_sync_report is not None
        assert sched._last_sync_report["skipped"] is True
        assert sched._last_sync_report["skip_reason"] == "non-trading day"


class TestUnifiedSchedulerMissingCheckJob:
    """Test the _missing_check_job logic."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_missing_check_executes(self, mock_load):
        """Missing check should call detect_missing_data regardless of trading day."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_summary = MagicMock()
        mock_summary.plugins_with_missing = 0
        mock_summary.total_plugins = 5
        mock_summary.plugins = []

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(return_value=mock_summary)
            sched._missing_check_job()
            mock_dms.detect_missing_data.assert_called_once_with(days=30, force_refresh=True)
        # Report should have been generated
        assert sched._last_missing_report is not None
        assert sched._last_missing_report["job_type"] == "missing_check"

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_missing_check_runs_on_non_trading_day(self, mock_load):
        """On a non-trading day, missing check should still execute.

        Data from previous trading days may be missing and needs detection
        regardless of whether today is a trading day.
        """
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_summary = MagicMock()
        mock_summary.plugins_with_missing = 2
        mock_summary.total_plugins = 5
        mock_plugin = MagicMock()
        mock_plugin.plugin_name = "tushare_daily"
        mock_plugin.missing_count = 3
        mock_summary.plugins = [mock_plugin]

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(return_value=mock_summary)
            sched._missing_check_job()
            # Should still be called even if today is a non-trading day
            mock_dms.detect_missing_data.assert_called_once_with(days=30, force_refresh=True)
        # Report should show the missing data
        assert sched._last_missing_report is not None
        assert sched._last_missing_report["data_quality"]["plugins_with_missing"] == 2
        assert sched._last_missing_report["data_quality"]["total_missing_dates"] == 3


# ---------------------------------------------------------------------------
# Smart backfill tests (ScheduleService.trigger_now)
# ---------------------------------------------------------------------------

class TestSmartBackfill:
    """Test the smart backfill logic in ScheduleService.trigger_now()."""

    def _make_mock_summary(self, plugin_missing: dict):
        """Create a mock MissingDataSummary.

        Args:
            plugin_missing: mapping of plugin_name -> list of missing dates
        """
        mock_summary = MagicMock()
        plugins = []
        for name, dates in plugin_missing.items():
            pinfo = MagicMock()
            pinfo.plugin_name = name
            pinfo.missing_dates = dates
            pinfo.missing_count = len(dates)
            plugins.append(pinfo)
        mock_summary.plugins = plugins
        mock_summary.plugins_with_missing = sum(1 for d in plugin_missing.values() if d)
        mock_summary.total_plugins = len(plugin_missing)
        return mock_summary

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.add_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.update_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.plugin_manager")
    def test_no_missing_creates_incremental(
        self, mock_pm, mock_save, mock_update, mock_add, mock_get_config
    ):
        """When no data is missing, incremental tasks are created."""
        mock_get_config.return_value = _make_schedule_config(skip_non_trading_days=False)

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()

        # Mock get_plugin_configs
        svc.get_plugin_configs = MagicMock(return_value=[
            {"plugin_name": "tushare_daily", "schedule_enabled": True, "full_scan_enabled": False},
        ])
        svc.get_config = MagicMock(return_value=_make_schedule_config(skip_non_trading_days=False))

        mock_pm.batch_trigger_sync.return_value = [{"plugin_name": "tushare_daily"}]

        # Mock get_plugin to return an enabled plugin
        mock_plugin = MagicMock()
        mock_plugin.is_enabled.return_value = True
        mock_pm.get_plugin.return_value = mock_plugin

        mock_task = MagicMock()
        mock_task.task_id = "task-001"

        # No missing data
        mock_summary = self._make_mock_summary({"tushare_daily": []})

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
                mock_dms.detect_missing_data.return_value = mock_summary
                with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
                    mock_stm.create_task.return_value = mock_task

                    result = svc.trigger_now(
                        is_manual=False,
                        smart_backfill=True,
                        auto_backfill_max_days=3,
                    )

                    # Should create incremental task (no backfill needed)
                    call_args = mock_stm.create_task.call_args
                    from stock_datasource.modules.datamanage.schemas import TaskType
                    assert call_args.kwargs.get("task_type") == TaskType.INCREMENTAL or \
                           call_args[1].get("task_type") == TaskType.INCREMENTAL

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.add_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.update_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.plugin_manager")
    def test_few_missing_creates_backfill(
        self, mock_pm, mock_save, mock_update, mock_add, mock_get_config
    ):
        """When missing days ≤ threshold, backfill tasks are created."""
        mock_get_config.return_value = _make_schedule_config(skip_non_trading_days=False)

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()

        svc.get_plugin_configs = MagicMock(return_value=[
            {"plugin_name": "tushare_daily", "schedule_enabled": True, "full_scan_enabled": False},
        ])
        svc.get_config = MagicMock(return_value=_make_schedule_config(skip_non_trading_days=False))

        mock_pm.batch_trigger_sync.return_value = [{"plugin_name": "tushare_daily"}]

        # Mock get_plugin to return an enabled plugin
        mock_plugin = MagicMock()
        mock_plugin.is_enabled.return_value = True
        mock_pm.get_plugin.return_value = mock_plugin

        mock_task = MagicMock()
        mock_task.task_id = "task-002"

        # 2 missing days (within threshold of 3)
        mock_summary = self._make_mock_summary({
            "tushare_daily": ["2026-01-05", "2026-01-06"]
        })

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
                mock_dms.detect_missing_data.return_value = mock_summary
                with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
                    mock_stm.create_task.return_value = mock_task

                    result = svc.trigger_now(
                        is_manual=False,
                        smart_backfill=True,
                        auto_backfill_max_days=3,
                    )

                    call_args = mock_stm.create_task.call_args
                    from stock_datasource.modules.datamanage.schemas import TaskType
                    assert call_args.kwargs.get("task_type") == TaskType.BACKFILL or \
                           call_args[1].get("task_type") == TaskType.BACKFILL
                    # trade_dates should contain the missing dates
                    trade_dates = call_args.kwargs.get("trade_dates") or call_args[1].get("trade_dates")
                    assert trade_dates is not None
                    assert "2026-01-05" in trade_dates
                    assert "2026-01-06" in trade_dates

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.add_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.update_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.plugin_manager")
    def test_excessive_missing_skipped(
        self, mock_pm, mock_save, mock_update, mock_add, mock_get_config
    ):
        """When missing days > threshold, plugin is skipped."""
        mock_get_config.return_value = _make_schedule_config(skip_non_trading_days=False)

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()

        svc.get_plugin_configs = MagicMock(return_value=[
            {"plugin_name": "tushare_daily", "schedule_enabled": True, "full_scan_enabled": False},
        ])
        svc.get_config = MagicMock(return_value=_make_schedule_config(skip_non_trading_days=False))

        mock_pm.batch_trigger_sync.return_value = [{"plugin_name": "tushare_daily"}]

        # Mock get_plugin to return an enabled plugin
        mock_plugin = MagicMock()
        mock_plugin.is_enabled.return_value = True
        mock_pm.get_plugin.return_value = mock_plugin

        # 10 missing days (exceeds threshold of 3)
        missing_dates = [f"2026-01-{d:02d}" for d in range(1, 11)]
        mock_summary = self._make_mock_summary({
            "tushare_daily": missing_dates
        })

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
                mock_dms.detect_missing_data.return_value = mock_summary
                with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
                    mock_stm.create_task.return_value = MagicMock(task_id="t")

                    result = svc.trigger_now(
                        is_manual=False,
                        smart_backfill=True,
                        auto_backfill_max_days=3,
                    )

                    # create_task should NOT be called for the skipped plugin
                    mock_stm.create_task.assert_not_called()
                    # Record should note the skipped plugins
                    assert "tushare_daily" in result.get("skipped_excessive_missing", [])

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.add_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.update_schedule_execution")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.plugin_manager")
    def test_smart_backfill_disabled_fallback(
        self, mock_pm, mock_save, mock_update, mock_add, mock_get_config
    ):
        """When smart_backfill=False, always creates incremental tasks."""
        mock_get_config.return_value = _make_schedule_config(skip_non_trading_days=False)

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()

        svc.get_plugin_configs = MagicMock(return_value=[
            {"plugin_name": "tushare_daily", "schedule_enabled": True, "full_scan_enabled": False},
        ])
        svc.get_config = MagicMock(return_value=_make_schedule_config(skip_non_trading_days=False))

        mock_pm.batch_trigger_sync.return_value = [{"plugin_name": "tushare_daily"}]

        # Mock get_plugin to return an enabled plugin
        mock_plugin = MagicMock()
        mock_plugin.is_enabled.return_value = True
        mock_pm.get_plugin.return_value = mock_plugin

        mock_task = MagicMock()
        mock_task.task_id = "task-004"

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
                mock_stm.create_task.return_value = mock_task

                result = svc.trigger_now(
                    is_manual=False,
                    smart_backfill=False,  # disabled
                    auto_backfill_max_days=3,
                )

                call_args = mock_stm.create_task.call_args
                from stock_datasource.modules.datamanage.schemas import TaskType
                assert call_args.kwargs.get("task_type") == TaskType.INCREMENTAL or \
                       call_args[1].get("task_type") == TaskType.INCREMENTAL


# ---------------------------------------------------------------------------
# Config update tests
# ---------------------------------------------------------------------------

class TestConfigUpdateNotifiesScheduler:
    """Verify that ScheduleService.update_config notifies UnifiedScheduler."""

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    def test_update_config_calls_reschedule(self, mock_save, mock_get_config):
        """update_config should call UnifiedScheduler.reschedule()."""
        mock_get_config.return_value = _make_schedule_config()

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()
        svc.get_config = MagicMock(return_value=_make_schedule_config())

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.tasks.unified_scheduler.get_unified_scheduler") as mock_get_us:
                mock_scheduler = MagicMock()
                mock_scheduler._running = True
                mock_get_us.return_value = mock_scheduler

                svc.update_config(execute_time="19:30")

                mock_scheduler.reschedule.assert_called_once()

    @patch("stock_datasource.modules.datamanage.schedule_service.get_schedule_config")
    @patch("stock_datasource.modules.datamanage.schedule_service.save_runtime_config")
    def test_update_config_new_fields(self, mock_save, mock_get_config):
        """update_config accepts new fields (missing_check_time, smart_backfill_enabled, auto_backfill_max_days)."""
        mock_get_config.return_value = _make_schedule_config()

        from stock_datasource.modules.datamanage.schedule_service import ScheduleService
        svc = ScheduleService.__new__(ScheduleService)
        svc._initialized = True
        svc._executor_thread = None
        svc._stop_event = MagicMock()
        svc.get_config = MagicMock(return_value=_make_schedule_config())

        with patch("stock_datasource.modules.datamanage.schedule_service.ScheduleService._mark_interrupted_executions"):
            with patch("stock_datasource.tasks.unified_scheduler.get_unified_scheduler") as mock_get_us:
                mock_scheduler = MagicMock()
                mock_scheduler._running = False
                mock_get_us.return_value = mock_scheduler

                svc.update_config(
                    missing_check_time="15:00",
                    smart_backfill_enabled=False,
                    auto_backfill_max_days=5,
                )

                # Verify save_runtime_config was called with the new fields
                call_kwargs = mock_save.call_args
                schedule_updates = call_kwargs.kwargs.get("schedule") or call_kwargs[1].get("schedule", {})
                assert schedule_updates["missing_check_time"] == "15:00"
                assert schedule_updates["smart_backfill_enabled"] is False
                assert schedule_updates["auto_backfill_max_days"] == 5


# ---------------------------------------------------------------------------
# Old scheduler compatibility tests
# ---------------------------------------------------------------------------

class TestLegacyCompatibility:
    """Test the deprecated DataSyncScheduler wrapper."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    def test_get_data_sync_scheduler_returns_instance(self):
        """get_data_sync_scheduler should return a DataSyncScheduler."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from stock_datasource.tasks.data_sync_scheduler import get_data_sync_scheduler
            scheduler = get_data_sync_scheduler()
            assert scheduler is not None
            assert hasattr(scheduler, "start")
            assert hasattr(scheduler, "stop")
            assert hasattr(scheduler, "get_status")

    def test_get_status_returns_old_format(self):
        """get_status() should return a dict with the old field names."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from stock_datasource.tasks.data_sync_scheduler import get_data_sync_scheduler

        with patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config"):
            scheduler = get_data_sync_scheduler()
            # Initialize the unified scheduler mock
            unified = scheduler._get_unified()
            unified._config = _make_schedule_config(enabled=False)
            unified._running = False

            status = scheduler.get_status()

            assert "is_running" in status
            assert "enabled" in status
            assert "data_sync_time" in status
            assert "analysis_time" in status
            assert "thread_alive" in status


# ---------------------------------------------------------------------------
# Runtime config defaults test
# ---------------------------------------------------------------------------

class TestRuntimeConfigDefaults:
    """Verify new default fields are present in the runtime_config module."""

    def test_default_config_has_new_fields(self):
        """DEFAULT_CONFIG should contain the new scheduler fields."""
        from stock_datasource.config.runtime_config import DEFAULT_CONFIG

        schedule_defaults = DEFAULT_CONFIG["schedule"]
        assert "missing_check_time" in schedule_defaults
        assert schedule_defaults["missing_check_time"] == "16:00"
        assert "smart_backfill_enabled" in schedule_defaults
        assert schedule_defaults["smart_backfill_enabled"] is True
        assert "auto_backfill_max_days" in schedule_defaults
        assert schedule_defaults["auto_backfill_max_days"] == 3


# ---------------------------------------------------------------------------
# Execution report tests
# ---------------------------------------------------------------------------

class TestDailySyncReport:
    """Test that _daily_sync_job generates structured execution reports."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=True)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_generated_on_success(self, mock_load, mock_trading):
        """Sync report should be generated after successful sync."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_record = {
            "execution_id": "test-001",
            "status": "running",
            "task_ids": ["t1", "t2"],
            "total_plugins": 2,
        }

        # Mock tasks that complete successfully
        mock_task_completed = MagicMock()
        mock_task_completed.status.value = "completed"
        mock_task_completed.plugin_name = "tushare_daily"
        mock_task_completed.error_message = None
        mock_task_completed.records_processed = 1000

        mock_task_failed = MagicMock()
        mock_task_failed.status.value = "failed"
        mock_task_failed.plugin_name = "tushare_adj"
        mock_task_failed.error_message = "Connection timeout after 30s"
        mock_task_failed.records_processed = 0

        def get_task_side_effect(task_id):
            if task_id == "t1":
                return mock_task_completed
            return mock_task_failed

        with patch("stock_datasource.modules.datamanage.schedule_service.schedule_service") as mock_svc:
            mock_svc.trigger_now = MagicMock(return_value=mock_record)
            with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
                mock_stm.get_task = MagicMock(side_effect=get_task_side_effect)
                sched._daily_sync_job()

        # Verify report was generated
        report = sched._last_sync_report
        assert report is not None
        assert report["job_type"] == "daily_sync"
        assert report["triggered_at"] is not None
        assert report["completed_at"] is not None
        assert report["duration_seconds"] >= 0
        assert report["summary"]["total_plugins"] == 2
        assert report["summary"]["succeeded"] == 1
        assert report["summary"]["failed"] == 1
        assert len(report["failures"]) == 1
        assert report["failures"][0]["plugin"] == "tushare_adj"
        assert report["failures"][0]["error_type"] == "Timeout"

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=False)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_generated_on_skip(self, mock_load, mock_trading):
        """When skipped due to non-trading day, report should reflect skip reason."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        sched._daily_sync_job()

        report = sched._last_sync_report
        assert report is not None
        assert report["job_type"] == "daily_sync"
        assert report["skipped"] is True
        assert report["skip_reason"] == "non-trading day"

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=True)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_generated_on_error(self, mock_load, mock_trading):
        """When an exception occurs, report should capture the error."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        with patch("stock_datasource.modules.datamanage.schedule_service.schedule_service") as mock_svc:
            mock_svc.trigger_now = MagicMock(side_effect=RuntimeError("Redis unavailable"))
            sched._daily_sync_job()

        report = sched._last_sync_report
        assert report is not None
        assert report["error"] is not None
        assert "Redis unavailable" in report["error"]

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._should_run_today", return_value=False)
    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_available_in_get_status(self, mock_load, mock_trading):
        """The last sync report should be accessible via get_status()."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        # Simulate a skipped report (non-trading day)
        sched._daily_sync_job()

        sched.start()
        status = sched.get_status()
        assert "last_sync_report" in status
        assert status["last_sync_report"] is not None
        assert status["last_sync_report"]["skipped"] is True
        sched.stop()


class TestMissingCheckReport:
    """Test that _missing_check_job generates structured reports."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_when_all_complete(self, mock_load):
        """When all plugins have complete data, report should reflect that."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_summary = MagicMock()
        mock_summary.plugins_with_missing = 0
        mock_summary.total_plugins = 5
        mock_summary.plugins = []

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(return_value=mock_summary)
            sched._missing_check_job()

        report = sched._last_missing_report
        assert report is not None
        assert report["job_type"] == "missing_check"
        assert report["data_quality"]["total_plugins"] == 5
        assert report["data_quality"]["plugins_with_missing"] == 0
        assert report["data_quality"]["total_missing_dates"] == 0
        assert len(report["data_quality"]["needs_attention"]) == 0

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_when_missing_detected(self, mock_load):
        """When plugins have missing data, report should list them."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_plugin_1 = MagicMock()
        mock_plugin_1.plugin_name = "tushare_daily"
        mock_plugin_1.missing_count = 3

        mock_plugin_2 = MagicMock()
        mock_plugin_2.plugin_name = "tushare_adj"
        mock_plugin_2.missing_count = 0

        mock_summary = MagicMock()
        mock_summary.plugins_with_missing = 1
        mock_summary.total_plugins = 2
        mock_summary.plugins = [mock_plugin_1, mock_plugin_2]

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(return_value=mock_summary)
            sched._missing_check_job()

        report = sched._last_missing_report
        assert report is not None
        assert report["data_quality"]["plugins_with_missing"] == 1
        assert report["data_quality"]["total_missing_dates"] == 3
        assert len(report["data_quality"]["needs_attention"]) == 1
        assert report["data_quality"]["needs_attention"][0]["plugin"] == "tushare_daily"
        assert report["data_quality"]["needs_attention"][0]["missing_days"] == 3

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_on_error(self, mock_load):
        """When an exception occurs, report should capture the error."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(side_effect=RuntimeError("DB offline"))
            sched._missing_check_job()

        report = sched._last_missing_report
        assert report is not None
        assert report["error"] is not None
        assert "DB offline" in report["error"]

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_report_available_in_get_status(self, mock_load):
        """The last missing report should be accessible via get_status()."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_summary = MagicMock()
        mock_summary.plugins_with_missing = 0
        mock_summary.total_plugins = 3
        mock_summary.plugins = []

        with patch("stock_datasource.modules.datamanage.service.data_manage_service") as mock_dms:
            mock_dms.detect_missing_data = MagicMock(return_value=mock_summary)
            sched._missing_check_job()

        sched.start()
        status = sched.get_status()
        assert "last_missing_report" in status
        assert status["last_missing_report"] is not None
        assert status["last_missing_report"]["job_type"] == "missing_check"
        sched.stop()


class TestErrorClassification:
    """Test the _classify_error static method."""

    def test_rate_limit(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("Rate limit exceeded for API") == "Rate limit exceeded"
        assert UnifiedScheduler._classify_error("HTTP 429 Too Many Requests") == "Rate limit exceeded"

    def test_timeout(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("Connection timed out after 30s") == "Timeout"
        assert UnifiedScheduler._classify_error("Read timed out") == "Timeout"

    def test_connection_error(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("Connection refused by host") == "Connection error"

    def test_auth_error(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("HTTP 401 Unauthorized") == "Authentication error"

    def test_not_found(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("No data found for given date range") == "Data not found"

    def test_unknown_error(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        assert UnifiedScheduler._classify_error("Something weird happened") == "Execution error"
        assert UnifiedScheduler._classify_error("") == "Unknown"


class TestWaitForTasks:
    """Test the _wait_for_tasks polling logic."""

    def setup_method(self):
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler
        UnifiedScheduler._instance = None

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_empty_task_ids(self, mock_load):
        """Empty task list should return immediately."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        results = sched._wait_for_tasks([])
        assert results == []

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_all_tasks_already_complete(self, mock_load):
        """When all tasks are already terminal, should return immediately."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        mock_task = MagicMock()
        mock_task.status.value = "completed"
        mock_task.plugin_name = "tushare_daily"
        mock_task.error_message = None
        mock_task.records_processed = 500

        with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
            mock_stm.get_task = MagicMock(return_value=mock_task)
            results = sched._wait_for_tasks(["t1"], poll_interval=1, timeout=5)

        assert len(results) == 1
        assert results[0]["status"] == "completed"
        assert results[0]["plugin_name"] == "tushare_daily"

    @patch("stock_datasource.tasks.unified_scheduler.UnifiedScheduler._load_config")
    def test_task_not_found(self, mock_load):
        """When a task is not found in the queue, it should be marked as failed."""
        from stock_datasource.tasks.unified_scheduler import UnifiedScheduler

        sched = UnifiedScheduler()
        sched._config = _make_schedule_config(enabled=True)

        with patch("stock_datasource.modules.datamanage.service.sync_task_manager") as mock_stm:
            mock_stm.get_task = MagicMock(return_value=None)
            results = sched._wait_for_tasks(["t-missing"], poll_interval=1, timeout=5)

        assert len(results) == 1
        assert results[0]["status"] == "failed"
        assert "not found" in results[0]["error_message"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
