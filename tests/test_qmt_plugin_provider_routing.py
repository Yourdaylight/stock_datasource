"""Tests for routing logical plugins to QMT historical providers."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(autouse=True)
def configure_tushare_token(monkeypatch):
    monkeypatch.setenv("TUSHARE_TOKEN", "test-token")
    from stock_datasource.config.settings import settings

    monkeypatch.setattr(settings, "TUSHARE_TOKEN", "test-token")


class FakeQmtProvider:
    def __init__(self):
        self.daily_calls = []
        self.minute_calls = []

    def get_daily_bars(self, ts_code, start_date=None, end_date=None, count=None):
        self.daily_calls.append(
            {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date,
                "count": count,
            }
        )
        return pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "trade_date": start_date,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.5,
                    "close": 10.5,
                    "pre_close": 10.0,
                    "change": 0.5,
                    "pct_chg": 5.0,
                    "vol": 1000,
                    "amount": 10000.0,
                }
            ]
        )

    def get_minute_bars(self, ts_code, freq="1min", start_time=None, end_time=None, count=None):
        self.minute_calls.append(
            {
                "ts_code": ts_code,
                "freq": freq,
                "start_time": start_time,
                "end_time": end_time,
                "count": count,
            }
        )
        return pd.DataFrame(
            [
                {
                    "ts_code": ts_code,
                    "trade_time": start_time,
                    "freq": freq,
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.9,
                    "close": 10.1,
                    "vol": 100,
                    "amount": 1000.0,
                }
            ]
        )


def test_daily_plugin_uses_qmt_provider_when_data_source_override(monkeypatch):
    """tushare_daily remains logical plugin but can fetch via QMT provider."""
    from stock_datasource.plugins.tushare_daily import plugin as daily_module

    provider = FakeQmtProvider()
    monkeypatch.setattr(daily_module, "QmtHistoricalProvider", lambda: provider)

    plugin = daily_module.TuShareDailyPlugin()
    data = plugin.extract_data(
        data_source="qmt", ts_code="000001.SZ", trade_date="20260102"
    )

    assert provider.daily_calls == [
        {
            "ts_code": "000001.SZ",
            "start_date": "20260102",
            "end_date": "20260102",
            "count": None,
        }
    ]
    assert data.iloc[0]["ts_code"] == "000001.SZ"
    assert data.iloc[0]["trade_date"] == "20260102"
    assert "version" in data.columns
    assert "_ingested_at" in data.columns


def test_daily_plugin_rejects_unsupported_data_source():
    """Historical plugins reject unsupported data sources before creating tasks."""
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin

    plugin = TuShareDailyPlugin()

    with pytest.raises(ValueError, match="Unsupported data_source"):
        plugin.extract_data(data_source="unknown", trade_date="20260102")


def test_daily_plugin_requires_ts_code_for_qmt():
    """QMT daily provider requires an explicit symbol for the first milestone."""
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin

    plugin = TuShareDailyPlugin()

    with pytest.raises(ValueError, match="ts_code is required"):
        plugin.extract_data(data_source="qmt", trade_date="20260102")


def test_minute_plugin_uses_qmt_provider_when_data_source_override(monkeypatch):
    """tushare_stk_mins can fetch minute bars through QMT provider."""
    from stock_datasource.plugins.tushare_stk_mins import plugin as mins_module

    provider = FakeQmtProvider()
    monkeypatch.setattr(mins_module, "QmtHistoricalProvider", lambda: provider)

    plugin = mins_module.TuShareStkMinsPlugin()
    data = plugin.extract_data(
        data_source="qmt",
        ts_code="000001.SZ",
        freq="1min",
        start_date="2026-01-02 09:31:00",
        end_date="2026-01-02 09:32:00",
    )

    assert provider.minute_calls == [
        {
            "ts_code": "000001.SZ",
            "freq": "1min",
            "start_time": "2026-01-02 09:31:00",
            "end_time": "2026-01-02 09:32:00",
            "count": None,
        }
    ]
    assert data.iloc[0]["ts_code"] == "000001.SZ"
    assert data.iloc[0]["freq"] == "1min"


def test_task_worker_forwards_data_source_to_plugin(monkeypatch):
    """Worker subprocess entry must pass data_source from task_data into plugin.run."""
    from multiprocessing import Queue

    from stock_datasource.services import task_worker

    captured = {}

    class FakePlugin:
        def get_category(self):
            from stock_datasource.core.base_plugin import PluginCategory

            return PluginCategory.CN_STOCK

        def get_config(self):
            return {"data_source": "tushare", "available_data_sources": ["tushare", "qmt"]}

        def run(self, **kwargs):
            captured["kwargs"] = kwargs
            return {"status": "success", "steps": {"load": {"total_records": 5}}}

    monkeypatch.setattr(
        task_worker.plugin_manager,
        "discover_plugins",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        task_worker.plugin_manager,
        "get_plugin",
        lambda name: FakePlugin(),
    )
    monkeypatch.setattr(task_worker, "_detect_plugin_param_style", lambda plugin: "trade_date")

    from stock_datasource.core import trade_calendar as trade_calendar_module

    monkeypatch.setattr(
        trade_calendar_module.trade_calendar_service,
        "is_trading_day",
        lambda day, market=None: True,
    )

    result_queue = Queue()
    task_worker._run_plugin_in_subprocess(
        {
            "plugin_name": "tushare_daily",
            "task_type": "incremental",
            "trade_dates": [],
            "task_id": "test-1",
            "data_source": "qmt",
        },
        result_queue,
    )

    success, records, _error_type, _message = result_queue.get(timeout=2)
    assert success is True
    assert records == 5
    assert captured["kwargs"].get("data_source") == "qmt"


def test_multi_source_plugin_configs_expose_available_sources():
    """Selected historical plugins advertise their provider choices in config."""
    from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin
    from stock_datasource.plugins.tushare_stk_mins.plugin import TuShareStkMinsPlugin

    daily_config = TuShareDailyPlugin().get_config()
    mins_config = TuShareStkMinsPlugin().get_config()

    assert daily_config["data_source"] == "tushare"
    assert daily_config["available_data_sources"] == ["tushare", "qmt"]
    assert mins_config["data_source"] == "tushare"
    assert mins_config["available_data_sources"] == ["tushare", "qmt"]
