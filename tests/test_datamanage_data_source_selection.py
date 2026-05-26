"""Tests for data-source selection in data management APIs and UI."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def configure_tushare_token(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")
    from stock_datasource.config.settings import settings

    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "test-token")


def test_plugin_detail_exposes_default_and_available_data_sources(monkeypatch):
    """Plugin detail includes provider metadata for multi-source plugins."""
    from stock_datasource.modules.datamanage.service import DataManageService
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin

    plugin = TuShareDailyPlugin()
    service = DataManageService()

    monkeypatch.setattr(
        "stock_datasource.modules.datamanage.service.plugin_manager.get_plugin",
        lambda name: plugin if name == "tushare_daily" else None,
    )
    monkeypatch.setattr(service, "get_table_latest_date", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "get_table_record_count", lambda *args, **kwargs: 0)

    detail = service.get_plugin_detail("tushare_daily")

    assert detail is not None
    assert detail.config.data_source == "tushare"
    assert detail.config.available_data_sources == ["tushare", "qmt"]


def test_trigger_sync_request_accepts_optional_data_source():
    """Manual sync requests can carry a per-run data source override."""
    from stock_datasource.modules.datamanage.schemas import TriggerSyncRequest

    request = TriggerSyncRequest(
        plugin_name="tushare_daily",
        task_type="backfill",
        trade_dates=["2026-01-02"],
        data_source="qmt",
    )

    assert request.data_source == "qmt"


def test_sync_task_manager_passes_data_source_to_queue(monkeypatch):
    """Task manager persists selected provider into queued task data."""
    from stock_datasource.modules.datamanage.schemas import TaskType
    from stock_datasource.modules.datamanage.service import SyncTaskManager
    from stock_datasource.services import task_queue as task_queue_module

    class FakeQueue:
        def __init__(self):
            self.kwargs = None

        def enqueue(self, **kwargs):
            self.kwargs = kwargs
            return "task-1"

    fake_queue = FakeQueue()
    monkeypatch.setattr(task_queue_module, "task_queue", fake_queue)

    manager = SyncTaskManager()
    task = manager.create_task(
        plugin_name="tushare_daily",
        task_type=TaskType.BACKFILL,
        trade_dates=["2026-01-02"],
        data_source="qmt",
    )

    assert fake_queue.kwargs["data_source"] == "qmt"
    assert task.data_source == "qmt"


def test_trigger_sync_rejects_qmt_without_ts_code(monkeypatch):
    """QMT requires a per-symbol query; trigger_sync must reject missing ts_code early."""
    from fastapi import HTTPException

    from stock_datasource.core.plugin_manager import DependencyCheckResult
    from stock_datasource.modules.datamanage import router as router_module
    from stock_datasource.modules.datamanage.schemas import TriggerSyncRequest
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin

    plugin = TuShareDailyPlugin()
    monkeypatch.setattr(
        router_module.plugin_manager, "get_plugin", lambda name: plugin
    )
    monkeypatch.setattr(
        router_module.plugin_manager,
        "check_dependencies",
        lambda name: DependencyCheckResult(satisfied=True),
    )

    request = TriggerSyncRequest(
        plugin_name="tushare_daily",
        task_type="backfill",
        trade_dates=["2026-01-02"],
        data_source="qmt",
    )

    with pytest.raises(HTTPException) as exc_info:
        import asyncio

        asyncio.run(
            router_module.trigger_sync(
                request,
                current_user={"id": "u1", "username": "tester"},
            )
        )

    assert exc_info.value.status_code == 400
    detail = exc_info.value.detail
    assert isinstance(detail, dict)
    assert "ts_code" in detail.get("message", "")


def test_trigger_sync_accepts_qmt_with_ts_code(monkeypatch):
    """QMT sync request with a valid ts_code passes the early validation gate."""
    from stock_datasource.core.plugin_manager import DependencyCheckResult
    from stock_datasource.modules.datamanage import router as router_module
    from stock_datasource.modules.datamanage.schemas import TaskType, TriggerSyncRequest
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin

    plugin = TuShareDailyPlugin()
    captured = {}

    class FakeTask:
        task_id = "task-1"

    def fake_create_task(**kwargs):
        captured.update(kwargs)
        return FakeTask()

    monkeypatch.setattr(
        router_module.plugin_manager, "get_plugin", lambda name: plugin
    )
    monkeypatch.setattr(
        router_module.plugin_manager,
        "check_dependencies",
        lambda name: DependencyCheckResult(satisfied=True),
    )
    monkeypatch.setattr(router_module.sync_task_manager, "create_task", fake_create_task)
    monkeypatch.setattr(
        router_module.schedule_service,
        "create_manual_execution",
        lambda **kwargs: None,
    )

    request = TriggerSyncRequest(
        plugin_name="tushare_daily",
        task_type=TaskType.BACKFILL,
        trade_dates=["2026-01-02"],
        data_source="qmt",
        ts_code="000001.SZ",
    )

    import asyncio

    result = asyncio.run(
        router_module.trigger_sync(
            request,
            current_user={"id": "u1", "username": "tester"},
        )
    )

    assert result is not None
    assert captured["data_source"] == "qmt"
    assert captured["ts_code"] == "000001.SZ"


def test_frontend_sync_dialog_contains_data_source_selector():
    """Sync dialog exposes a per-run data-source selector for multi-source plugins."""
    content = Path(__file__).parent.parent.joinpath(
        "frontend/src/views/datamanage/components/SyncDialog.vue"
    ).read_text(encoding="utf-8")

    assert "本次数据源" in content
    assert "selectedDataSource" in content
    assert "available_data_sources" in content
    assert "requiresTsCode" in content
    assert "tsCode" in content


def test_frontend_api_trigger_request_has_data_source_field():
    """Frontend API types allow per-sync data_source overrides."""
    content = Path(__file__).parent.parent.joinpath(
        "frontend/src/api/datamanage.ts"
    ).read_text(encoding="utf-8")

    assert "data_source?: string" in content
    assert "ts_code?: string" in content
    assert "available_data_sources" in content
