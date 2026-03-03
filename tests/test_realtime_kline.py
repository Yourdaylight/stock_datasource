"""Tests for the decoupled realtime daily K-line pipeline.

Covers:
- config: key patterns, table mapping
- schemas: model validation
- cache: dual-channel store (latest + stream + checkpoints + push state)
- collector: BackoffController adaptive logic, normalization
- cloud_push: sliding-window delta, push switch, circuit breaker, DLQ
- sync_service: MinuteSinkWorker tick, prepare_dataframe, cleanup
- scheduler: RealtimeKlineRuntime lifecycle, trading hours check
- metrics: counter/gauge/histogram thread-safe ops
- service: query layer fallback (Redis → ClickHouse)
- router: API endpoints (status, trigger, sync, push switch, metrics)
"""

import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ===================================================================
# 1. Config
# ===================================================================
class TestConfig:
    def test_clickhouse_tables_all_markets(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert set(cfg.CLICKHOUSE_TABLES.keys()) == {"a_stock", "etf", "index", "hk"}

    def test_get_table_for_market(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert cfg.get_table_for_market("a_stock") == "ods_rt_kline_tick_cn"
        assert cfg.get_table_for_market("hk") == "ods_rt_kline_tick_hk"
        # Unknown market falls back to a_stock
        assert cfg.get_table_for_market("unknown") == "ods_rt_kline_tick_cn"

    def test_market_api_map(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert cfg.MARKET_API_MAP["a_stock"] == "rt_k"
        assert cfg.MARKET_API_MAP["hk"] == "rt_hk_k"

    def test_redis_key_patterns(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert "stock:rtk:" in cfg.REDIS_KEY_PREFIX_LATEST
        assert "stock:rtk:" in cfg.REDIS_KEY_PREFIX_STREAM

    def test_backoff_levels(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert cfg.BACKOFF_LEVELS == [1.5, 3.0, 5.0]
        assert cfg.BACKOFF_FAIL_THRESHOLD == 3
        assert cfg.BACKOFF_RECOVER_THRESHOLD == 5

    def test_snapshot_core_fields(self):
        from stock_datasource.modules.realtime_kline import config as cfg
        assert "close" in cfg.SNAPSHOT_CORE_FIELDS
        assert "vol" in cfg.SNAPSHOT_CORE_FIELDS


# ===================================================================
# 2. Schemas
# ===================================================================
class TestSchemas:
    def test_daily_kline_bar(self):
        from stock_datasource.modules.realtime_kline.schemas import DailyKlineBar
        bar = DailyKlineBar(ts_code="000001.SZ", close=10.5, version=1000)
        assert bar.ts_code == "000001.SZ"
        assert bar.version == 1000

    def test_collect_status_response(self):
        from stock_datasource.modules.realtime_kline.schemas import CollectStatusResponse
        resp = CollectStatusResponse(
            is_running=True,
            workers={"collector": True, "push": False, "sink": True},
            push_enabled=False,
        )
        assert resp.is_running is True
        assert resp.push_enabled is False

    def test_push_switch_request(self):
        from stock_datasource.modules.realtime_kline.schemas import PushSwitchRequest
        req = PushSwitchRequest(enabled=True)
        assert req.enabled is True

    def test_metrics_response(self):
        from stock_datasource.modules.realtime_kline.schemas import MetricsResponse
        r = MetricsResponse(counters={"a": 1}, gauges={"b": 2.0})
        assert r.counters["a"] == 1


# ===================================================================
# 3. Cache Store
# ===================================================================
class TestCacheStore:
    @pytest.fixture
    def cache_store(self):
        import stock_datasource.modules.realtime_kline.cache as cache_mod
        cache_mod._cache_store = None
        from stock_datasource.modules.realtime_kline.cache import RealtimeKlineCacheStore
        store = RealtimeKlineCacheStore()
        return store

    @pytest.fixture
    def mock_redis(self, cache_store):
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        cache_store._redis = mock_r
        return mock_r

    # -- latest --
    def test_set_and_get_latest(self, cache_store, mock_redis):
        data = {"ts_code": "000001.SZ", "close": 10.5}
        cache_store.set_latest("a_stock", "000001.SZ", data)
        assert mock_redis.setex.called

        mock_redis.get.return_value = json.dumps(data)
        result = cache_store.get_latest("a_stock", "000001.SZ")
        assert result["ts_code"] == "000001.SZ"

    def test_get_latest_redis_unavailable(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            assert cache_store.get_latest("a_stock", "000001.SZ") is None

    def test_get_all_latest(self, cache_store, mock_redis):
        bar = {"ts_code": "000001.SZ", "close": 10.0}
        mock_redis.scan.return_value = (0, ["stock:rtk:latest:a_stock:000001.SZ"])
        mock_redis.mget.return_value = [json.dumps(bar)]
        items = cache_store.get_all_latest(market="a_stock")
        assert len(items) == 1
        assert items[0]["ts_code"] == "000001.SZ"

    # -- stream --
    def test_xadd_event(self, cache_store, mock_redis):
        mock_redis.xadd.return_value = "1234-0"
        eid = cache_store.xadd_event("a_stock", {"ts_code": "000001.SZ", "payload": "{}"})
        assert eid == "1234-0"

    def test_xrange_since(self, cache_store, mock_redis):
        mock_redis.xrange.return_value = [("1234-0", {"payload": "{}"})]
        entries = cache_store.xrange_since("a_stock", min_id="1000-0")
        assert len(entries) == 1

    def test_xread_after(self, cache_store, mock_redis):
        mock_redis.xread.return_value = [
            ("stock:rtk:stream:a_stock", [("1-0", {"payload": "{}"})])
        ]
        entries = cache_store.xread_after("a_stock", last_id="0-0")
        assert len(entries) == 1

    def test_xlen(self, cache_store, mock_redis):
        mock_redis.xlen.return_value = 42
        assert cache_store.xlen("a_stock") == 42

    # -- checkpoint --
    def test_checkpoint_get_set(self, cache_store, mock_redis):
        mock_redis.get.return_value = "999-0"
        assert cache_store.get_checkpoint("stock:rtk:ckpt:clickhouse", "a_stock") == "999-0"

        cache_store.set_checkpoint("stock:rtk:ckpt:clickhouse", "a_stock", "1000-0")
        assert mock_redis.set.called

    def test_checkpoint_defaults_to_zero(self, cache_store, mock_redis):
        mock_redis.get.return_value = None
        assert cache_store.get_checkpoint("ckpt", "a_stock") == "0-0"

    # -- push switch --
    def test_push_switch_get_set(self, cache_store, mock_redis):
        mock_redis.get.return_value = "true"
        assert cache_store.get_push_switch() is True

        mock_redis.get.return_value = "false"
        assert cache_store.get_push_switch() is False

    def test_push_switch_none_fallback(self, cache_store, mock_redis):
        mock_redis.get.return_value = None
        assert cache_store.get_push_switch() is None

    def test_set_push_switch_audit(self, cache_store, mock_redis):
        mock_redis.get.return_value = "false"
        cache_store.set_push_switch(True, source="api")
        mock_redis.set.assert_called()
        mock_redis.xadd.assert_called()

    # -- circuit breaker --
    def test_circuit_breaker(self, cache_store, mock_redis):
        mock_redis.get.return_value = "1"
        assert cache_store.get_circuit_breaker("a_stock") is True

        cache_store.set_circuit_breaker("a_stock", False)
        mock_redis.set.assert_called()

    # -- DLQ --
    def test_push_to_dlq(self, cache_store, mock_redis):
        ok = cache_store.push_to_dlq("stock:rtk:deadletter:push", "a_stock", {"test": 1})
        assert ok is True
        assert mock_redis.rpush.called

    def test_dlq_size(self, cache_store, mock_redis):
        mock_redis.llen.return_value = 5
        assert cache_store.dlq_size("stock:rtk:deadletter:push", "a_stock") == 5

    # -- store_snapshots batch --
    def test_store_snapshots(self, cache_store, mock_redis):
        with patch("stock_datasource.config.settings.settings") as mock_settings:
            mock_settings.RT_KLINE_LATEST_TTL_SECONDS = 86400
            mock_pipe = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe
            mock_pipe.execute.return_value = []

            rows = [
                {"ts_code": "000001.SZ", "close": 10.5, "version": 1000, "market": "a_stock"},
                {"ts_code": "000002.SZ", "close": 20.0, "version": 1000, "market": "a_stock"},
            ]
            count = cache_store.store_snapshots("a_stock", rows)
            assert count == 2
            assert mock_pipe.setex.call_count == 2
            assert mock_pipe.xadd.call_count == 2
            mock_pipe.execute.assert_called_once()

    def test_store_snapshots_redis_unavailable(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            count = cache_store.store_snapshots("a_stock", [{"ts_code": "x"}])
            assert count == 0

    # -- last acked state --
    def test_last_acked_state(self, cache_store, mock_redis):
        state = {"close": 10.0, "vol": 100}
        mock_redis.hget.return_value = json.dumps(state)
        result = cache_store.get_last_acked_state("a_stock", "000001.SZ")
        assert result["close"] == 10.0

        cache_store.set_last_acked_state("a_stock", "000001.SZ", {"close": 11.0})
        mock_redis.hset.assert_called()

    # -- status --
    def test_update_and_get_status(self, cache_store, mock_redis):
        cache_store.update_status("a_stock", 500)
        assert mock_redis.hset.called

        mock_redis.hgetall.return_value = {
            "a_stock": json.dumps({"last_collect_time": "2026-03-01 10:00:00", "records": 500})
        }
        status = cache_store.get_status()
        assert status["a_stock"]["records"] == 500

    # -- cached key count --
    def test_get_cached_key_count(self, cache_store, mock_redis):
        mock_redis.scan.return_value = (0, ["k1", "k2", "k3"])
        assert cache_store.get_cached_key_count() == 3


# ===================================================================
# 4. BackoffController
# ===================================================================
class TestBackoffController:
    def test_initial_interval(self):
        from stock_datasource.modules.realtime_kline.collector import BackoffController
        bc = BackoffController()
        assert bc.current_interval("a_stock") == 1.5

    def test_failure_escalation(self):
        from stock_datasource.modules.realtime_kline.collector import BackoffController
        bc = BackoffController()
        for _ in range(3):
            bc.record_failure("a_stock")
        assert bc.current_interval("a_stock") == 3.0

        for _ in range(3):
            bc.record_failure("a_stock")
        assert bc.current_interval("a_stock") == 5.0

    def test_failure_no_escalation_beyond_max(self):
        from stock_datasource.modules.realtime_kline.collector import BackoffController
        bc = BackoffController()
        for _ in range(20):
            bc.record_failure("a_stock")
        assert bc.current_interval("a_stock") == 5.0

    def test_recovery(self):
        from stock_datasource.modules.realtime_kline.collector import BackoffController
        bc = BackoffController()
        # Escalate to 3.0
        for _ in range(3):
            bc.record_failure("a_stock")
        assert bc.current_interval("a_stock") == 3.0

        # 5 successes → recover to 1.5
        for _ in range(5):
            bc.record_success("a_stock")
        assert bc.current_interval("a_stock") == 1.5

    def test_independent_markets(self):
        from stock_datasource.modules.realtime_kline.collector import BackoffController
        bc = BackoffController()
        for _ in range(3):
            bc.record_failure("hk")
        assert bc.current_interval("hk") == 3.0
        assert bc.current_interval("a_stock") == 1.5


# ===================================================================
# 5. Collector — normalize
# ===================================================================
class TestCollectorNormalize:
    def test_normalize_basic(self):
        from stock_datasource.modules.realtime_kline.collector import RealtimeKlineCollector
        from stock_datasource.modules.realtime_kline.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "name": ["平安银行"],
            "open": [10.0],
            "close": [10.5],
            "high": [10.8],
            "low": [9.9],
            "pre_close": [10.0],
            "vol": [1000],
            "amount": [10000],
            "pct_chg": [5.0],
            "trade_time": ["2026-03-01 10:00:00"],
        })
        rows = RealtimeKlineCollector._normalize(df, MarketType.A_STOCK)
        assert len(rows) == 1
        r = rows[0]
        assert r["ts_code"] == "000001.SZ"
        assert r["market"] == "a_stock"
        assert r["source_api"] == "rt_k"
        assert isinstance(r["version"], int)
        assert r["collected_at"] is not None

    def test_normalize_empty(self):
        from stock_datasource.modules.realtime_kline.collector import RealtimeKlineCollector
        from stock_datasource.modules.realtime_kline.schemas import MarketType
        rows = RealtimeKlineCollector._normalize(pd.DataFrame(), MarketType.ETF)
        assert rows == []

    def test_normalize_pct_chg_computed(self):
        from stock_datasource.modules.realtime_kline.collector import RealtimeKlineCollector
        from stock_datasource.modules.realtime_kline.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "close": [11.0],
            "pre_close": [10.0],
        })
        rows = RealtimeKlineCollector._normalize(df, MarketType.A_STOCK)
        assert rows[0]["pct_chg"] == pytest.approx(10.0, abs=0.1)

    def test_normalize_nan_safe(self):
        from stock_datasource.modules.realtime_kline.collector import RealtimeKlineCollector
        from stock_datasource.modules.realtime_kline.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "close": [float("nan")],
            "open": [float("inf")],
        })
        rows = RealtimeKlineCollector._normalize(df, MarketType.A_STOCK)
        assert rows[0]["close"] is None
        assert rows[0]["open"] is None

    def test_normalize_hk_no_amount(self):
        from stock_datasource.modules.realtime_kline.collector import RealtimeKlineCollector
        from stock_datasource.modules.realtime_kline.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["00700.HK"],
            "close": [300.0],
            "amount": [99999],
        })
        rows = RealtimeKlineCollector._normalize(df, MarketType.HK)
        assert rows[0]["amount"] is None


# ===================================================================
# 6. Cloud Push Worker
# ===================================================================
class TestCloudPushWorker:
    @pytest.fixture
    def push_worker(self):
        with patch("stock_datasource.config.settings.settings") as mock_s:
            mock_s.RT_KLINE_CLOUD_PUSH_ENABLED = False
            mock_s.RT_KLINE_CLOUD_PUSH_URL = "https://example.com/push"
            mock_s.RT_KLINE_CLOUD_PUSH_TOKEN = "test-token"
            mock_s.RT_KLINE_CLOUD_PUSH_INTERVAL = 2.0
            mock_s.RT_KLINE_CLOUD_PUSH_WINDOW = 10.0
            mock_s.RT_KLINE_PUSH_CIRCUIT_BREAKER_MINUTES = 30
            mock_s.RT_KLINE_PUSH_MAX_BACKLOG = 10000
            mock_s.RT_KLINE_PUSH_DLQ_TTL_DAYS = 7

            with patch("stock_datasource.modules.realtime_kline.cloud_push.get_cache_store") as mock_cache_fn:
                mock_cache = MagicMock()
                mock_cache_fn.return_value = mock_cache
                mock_cache.get_push_switch.return_value = None
                mock_cache.get_circuit_breaker.return_value = False

                import stock_datasource.modules.realtime_kline.cloud_push as cp_mod
                cp_mod._push_worker = None
                from stock_datasource.modules.realtime_kline.cloud_push import CloudPushWorker
                worker = CloudPushWorker()
                worker._cache = mock_cache
                yield worker

    def test_tick_skipped_when_disabled(self, push_worker):
        with patch("stock_datasource.modules.realtime_kline.cloud_push._is_push_enabled", return_value=False):
            push_worker.tick()
            # Should not attempt any stream reads
            push_worker._cache.xrange_since.assert_not_called()

    def test_compute_deltas_detects_change(self, push_worker):
        window = {
            "000001.SZ": {
                "ts_code": "000001.SZ",
                "close": 11.0,
                "vol": 200,
                "open": 10.0,
                "high": 11.5,
                "low": 9.8,
                "amount": 5000,
                "pre_close": 10.0,
                "pct_chg": 10.0,
                "trade_time": "2026-03-01 10:00:00",
                "_stream_id": "1000-0",
            }
        }
        push_worker._cache.get_last_acked_state.return_value = {
            "close": 10.0,
            "vol": 100,
        }
        deltas = push_worker._compute_deltas("a_stock", window)
        assert len(deltas) == 1
        d = deltas[0]
        assert d["schema_version"] == "v1"
        assert d["symbol"] == "000001.SZ"
        assert "close" in d["delta"]
        assert d["delta"]["close"] == 11.0

    def test_compute_deltas_no_change(self, push_worker):
        window = {
            "000001.SZ": {
                "close": 10.0,
                "vol": 100,
                "open": 10.0,
                "high": 10.0,
                "low": 10.0,
                "amount": 5000,
                "pre_close": 10.0,
                "pct_chg": 0.0,
                "trade_time": "2026-03-01 10:00:00",
                "_stream_id": "1000-0",
            }
        }
        push_worker._cache.get_last_acked_state.return_value = {
            "close": 10.0,
            "vol": 100,
            "open": 10.0,
            "high": 10.0,
            "low": 10.0,
            "amount": 5000,
            "pre_close": 10.0,
            "pct_chg": 0.0,
            "trade_time": "2026-03-01 10:00:00",
        }
        deltas = push_worker._compute_deltas("a_stock", window)
        assert len(deltas) == 0

    def test_circuit_breaker_activation(self, push_worker):
        push_worker._settings.RT_KLINE_PUSH_CIRCUIT_BREAKER_MINUTES = 0.0001  # tiny for test
        push_worker._failure_start["a_stock"] = time.time() - 100
        push_worker._record_failure("a_stock")
        push_worker._cache.set_circuit_breaker.assert_called_with("a_stock", True)

    def test_clear_failure_resets_circuit_breaker(self, push_worker):
        push_worker._failure_start["a_stock"] = time.time()
        push_worker._cache.get_circuit_breaker.return_value = True
        push_worker._clear_failure("a_stock")
        push_worker._cache.set_circuit_breaker.assert_called_with("a_stock", False)
        assert push_worker._failure_start["a_stock"] is None


# ===================================================================
# 7. MinuteSinkWorker
# ===================================================================
class TestMinuteSinkWorker:
    @pytest.fixture
    def sink_worker(self):
        import stock_datasource.modules.realtime_kline.sync_service as ss_mod
        ss_mod._sink_worker = None
        with patch("stock_datasource.modules.realtime_kline.sync_service.get_cache_store") as mock_fn:
            mock_cache = MagicMock()
            mock_fn.return_value = mock_cache
            mock_cache.get_checkpoint.return_value = "0-0"
            mock_cache.xread_after.return_value = []
            mock_cache.xlen.return_value = 0
            mock_cache.dlq_size.return_value = 0

            from stock_datasource.modules.realtime_kline.sync_service import MinuteSinkWorker
            worker = MinuteSinkWorker()
            worker._cache = mock_cache
            yield worker

    def test_tick_no_data(self, sink_worker):
        with patch("stock_datasource.modules.realtime_kline.sync_service._get_db") as mock_db:
            mock_db.return_value = MagicMock()
            with patch("stock_datasource.config.settings.settings") as mock_s:
                mock_s.CLICKHOUSE_DATABASE = "test_db"
                result = sink_worker.tick()
                assert result["all_ok"] is True

    def test_prepare_dataframe(self):
        from stock_datasource.modules.realtime_kline.sync_service import MinuteSinkWorker
        df = pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20260301"],
            "close": ["10.5"],
            "vol": ["1000"],
            "version": ["1709274000000"],
        })
        result = MinuteSinkWorker._prepare_dataframe(df, "a_stock")
        assert not result.empty
        assert result["close"].dtype in [float, "float64"]
        assert result["version"].dtype == "int64"
        assert result["trade_time"].iloc[0] == ""

    def test_prepare_dataframe_missing_ts_code(self):
        from stock_datasource.modules.realtime_kline.sync_service import MinuteSinkWorker
        df = pd.DataFrame({
            "ts_code": [None],
            "close": [10.0],
        })
        result = MinuteSinkWorker._prepare_dataframe(df, "a_stock")
        assert result.empty

    def test_sync_market_success(self, sink_worker):
        bar = {"ts_code": "000001.SZ", "close": 10.5, "trade_date": "20260301", "version": 1000}
        sink_worker._cache.xread_after.return_value = [
            ("100-0", {"payload": json.dumps(bar)})
        ]
        with patch("stock_datasource.modules.realtime_kline.sync_service._get_db") as mock_db_fn:
            mock_db = MagicMock()
            mock_db_fn.return_value = mock_db
            with patch("stock_datasource.config.settings.settings") as mock_s:
                mock_s.RT_KLINE_SINK_MARKET_RETRY_LIMIT = 3
                ok, count = sink_worker._sync_market("a_stock")
                assert ok is True
                assert count == 1
                mock_db.insert_dataframe.assert_called_once()
                sink_worker._cache.set_checkpoint.assert_called()

    def test_sync_market_retry_then_dlq(self, sink_worker):
        bar = {"ts_code": "000001.SZ", "close": 10.5, "trade_date": "20260301", "version": 1000}
        sink_worker._cache.xread_after.return_value = [
            ("100-0", {"payload": json.dumps(bar)})
        ]
        with patch("stock_datasource.modules.realtime_kline.sync_service._get_db") as mock_db_fn:
            mock_db = MagicMock()
            mock_db.insert_dataframe.side_effect = Exception("CH down")
            mock_db_fn.return_value = mock_db
            with patch("stock_datasource.config.settings.settings") as mock_s:
                mock_s.RT_KLINE_SINK_MARKET_RETRY_LIMIT = 2
                with patch("time.sleep"):
                    ok, count = sink_worker._sync_market("a_stock")
                    assert ok is False
                    assert count == 0
                    assert mock_db.insert_dataframe.call_count == 2
                    sink_worker._cache.push_to_dlq.assert_called()

    def test_cleanup_streams(self, sink_worker):
        with patch("stock_datasource.config.settings.settings") as mock_s:
            mock_s.RT_KLINE_STREAM_TTL_HOURS = 72
            sink_worker._cache.xtrim_older_than.return_value = 10
            result = sink_worker.cleanup_streams()
            assert all(v == 10 for v in result.values())


# ===================================================================
# 8. Scheduler — RealtimeKlineRuntime
# ===================================================================
class TestScheduler:
    def setup_method(self):
        import stock_datasource.modules.realtime_kline.scheduler as sched_mod
        sched_mod._runtime = None

    def test_is_trading_time(self):
        from stock_datasource.modules.realtime_kline.scheduler import is_trading_time
        with patch("stock_datasource.modules.realtime_kline.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 10, 0, 0)  # Monday 10:00
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = is_trading_time()
            assert result is True

    def test_is_not_trading_time(self):
        from stock_datasource.modules.realtime_kline.scheduler import is_trading_time
        with patch("stock_datasource.modules.realtime_kline.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 20, 0, 0)  # 20:00
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = is_trading_time()
            assert result is False

    def test_runtime_lifecycle(self):
        from stock_datasource.modules.realtime_kline.scheduler import RealtimeKlineRuntime
        rt = RealtimeKlineRuntime()
        assert rt.is_running is False
        health = rt.health()
        assert health["collector"] is False
        assert health["push"] is False
        assert health["sink"] is False

    def test_runtime_start_stop(self):
        from stock_datasource.modules.realtime_kline.scheduler import RealtimeKlineRuntime
        rt = RealtimeKlineRuntime()
        with patch.object(rt, "_collector", MagicMock()), \
             patch.object(rt, "_sink", MagicMock()):
            rt.stop()  # should not raise

    def test_run_collection(self):
        with patch("stock_datasource.modules.realtime_kline.collector.get_collector") as mock_gc, \
             patch("stock_datasource.modules.realtime_kline.cache.get_cache_store") as mock_cs:
            mock_collector = MagicMock()
            mock_gc.return_value = mock_collector
            mock_cache = MagicMock()
            mock_cs.return_value = mock_cache
            mock_collector.collect_all.return_value = {
                "a_stock": [{"ts_code": "000001.SZ"}],
                "etf": [],
            }
            mock_cache.store_snapshots.return_value = 1

            from stock_datasource.modules.realtime_kline.scheduler import run_collection
            result = run_collection()
            assert result["a_stock"] == 1
            assert result["etf"] == 0

    def test_start_push_if_needed(self):
        from stock_datasource.modules.realtime_kline.scheduler import RealtimeKlineRuntime
        rt = RealtimeKlineRuntime()
        with patch("stock_datasource.modules.realtime_kline.scheduler.PushThread") as MockPT:
            mock_thread = MagicMock()
            MockPT.return_value = mock_thread
            rt.start_push_if_needed()
            mock_thread.start.assert_called_once()

    def test_stop_push(self):
        from stock_datasource.modules.realtime_kline.scheduler import RealtimeKlineRuntime
        rt = RealtimeKlineRuntime()
        mock_push = MagicMock()
        rt._push = mock_push
        rt.stop_push()
        mock_push.stop.assert_called_once()
        assert rt._push is None


# ===================================================================
# 9. Metrics
# ===================================================================
class TestMetrics:
    def test_counter_increment(self):
        from stock_datasource.modules.realtime_kline.metrics import _Metrics
        m = _Metrics()
        m.inc("test_counter")
        m.inc("test_counter", delta=2)
        assert m.counter("test_counter") == 3

    def test_gauge_set(self):
        from stock_datasource.modules.realtime_kline.metrics import _Metrics
        m = _Metrics()
        m.set_gauge("test_gauge", 42.0)
        assert m.gauge("test_gauge") == 42.0

    def test_histogram_observe(self):
        from stock_datasource.modules.realtime_kline.metrics import _Metrics
        m = _Metrics()
        for i in range(10):
            m.observe("latency", float(i))
        snap = m.snapshot()
        assert "test_gauge" not in snap["gauges"]

    def test_labels_key(self):
        from stock_datasource.modules.realtime_kline.metrics import _Metrics
        m = _Metrics()
        m.inc("calls", labels={"market": "a_stock"})
        m.inc("calls", labels={"market": "hk"})
        assert m.counter("calls", labels={"market": "a_stock"}) == 1
        assert m.counter("calls", labels={"market": "hk"}) == 1

    def test_snapshot(self):
        from stock_datasource.modules.realtime_kline.metrics import _Metrics
        m = _Metrics()
        m.inc("c1")
        m.set_gauge("g1", 1.0)
        snap = m.snapshot()
        assert "c1" in snap["counters"]
        assert "g1" in snap["gauges"]

    def test_convenience_functions(self):
        from stock_datasource.modules.realtime_kline import metrics as m_mod
        # Reset global metrics
        m_mod.metrics = m_mod._Metrics()
        m_mod.collector_call("a_stock", True, 50.0)
        assert m_mod.metrics.counter("rt_kline_collector_calls_total", labels={"market": "a_stock"}) == 1
        assert m_mod.metrics.counter("rt_kline_collector_success_total", labels={"market": "a_stock"}) == 1

        m_mod.push_event("hk", "ok")
        assert m_mod.metrics.counter("rt_kline_push_events_total", labels={"market": "hk", "status": "ok"}) == 1


# ===================================================================
# 10. Service
# ===================================================================
class TestService:
    def setup_method(self):
        import stock_datasource.modules.realtime_kline.service as svc_mod
        svc_mod._service = None

    def test_get_latest_from_redis(self):
        with patch("stock_datasource.modules.realtime_kline.service.get_cache_store") as mock_fn:
            mock_cache = MagicMock()
            mock_fn.return_value = mock_cache
            mock_cache.get_latest.return_value = {"ts_code": "000001.SZ", "close": 10.0}

            from stock_datasource.modules.realtime_kline.service import RealtimeKlineService
            svc = RealtimeKlineService()
            result = svc.get_latest("000001.SZ", "a_stock")
            assert result["source"] == "redis"
            assert result["data"]["close"] == 10.0

    def test_get_latest_fallback_to_clickhouse(self):
        with patch("stock_datasource.modules.realtime_kline.service.get_cache_store") as mock_fn, \
             patch("stock_datasource.modules.realtime_kline.service._execute_query") as mock_q:
            mock_cache = MagicMock()
            mock_fn.return_value = mock_cache
            mock_cache.get_latest.return_value = None

            mock_q.return_value = [{"ts_code": "000001.SZ", "close": 10.0}]
            from stock_datasource.modules.realtime_kline.service import RealtimeKlineService
            svc = RealtimeKlineService()
            result = svc.get_latest("000001.SZ", "a_stock")
            assert result["source"] == "clickhouse"

    def test_normalize_market_aliases(self):
        from stock_datasource.modules.realtime_kline.service import _normalize_market
        assert _normalize_market("cn") == "a_stock"
        assert _normalize_market("astock") == "a_stock"
        assert _normalize_market("hk") == "hk"
        assert _normalize_market(None) is None

    def test_detect_market(self):
        from stock_datasource.modules.realtime_kline.service import _detect_market
        assert _detect_market("000001.SZ") == "a_stock"
        assert _detect_market("00700.HK") == "hk"
        assert _detect_market("510050.SH") == "etf"

    def test_get_batch_latest(self):
        with patch("stock_datasource.modules.realtime_kline.service.get_cache_store") as mock_fn:
            mock_cache = MagicMock()
            mock_fn.return_value = mock_cache
            mock_cache.get_all_latest.return_value = [
                {"ts_code": "000001.SZ"}, {"ts_code": "000002.SZ"}, {"ts_code": "000003.SZ"}
            ]
            from stock_datasource.modules.realtime_kline.service import RealtimeKlineService
            svc = RealtimeKlineService()
            result = svc.get_batch_latest(limit=2)
            assert result["count"] == 2


# ===================================================================
# 11. Router (API endpoints)
# ===================================================================
class TestRouter:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from stock_datasource.modules.realtime_kline.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/rt-kline")
        return TestClient(app)

    def test_get_latest(self, client):
        with patch("stock_datasource.modules.realtime_kline.router.get_realtime_kline_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc_fn.return_value = mock_svc
            mock_svc.get_latest.return_value = {
                "ts_code": "000001.SZ",
                "market": "a_stock",
                "data": {"ts_code": "000001.SZ", "close": 10.5},
                "source": "redis",
            }
            resp = client.get("/api/rt-kline/latest?ts_code=000001.SZ")
            assert resp.status_code == 200
            assert resp.json()["source"] == "redis"

    def test_get_batch(self, client):
        with patch("stock_datasource.modules.realtime_kline.router.get_realtime_kline_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc_fn.return_value = mock_svc
            mock_svc.get_batch_latest.return_value = {
                "market": None,
                "count": 0,
                "data": [],
            }
            resp = client.get("/api/rt-kline/batch")
            assert resp.status_code == 200

    def test_get_status(self, client):
        with patch("stock_datasource.modules.realtime_kline.router.get_realtime_kline_service") as mock_svc_fn:
            mock_svc = MagicMock()
            mock_svc_fn.return_value = mock_svc
            mock_svc.get_collect_status.return_value = {
                "is_running": True,
                "workers": {"collector": True, "push": False, "sink": True},
                "markets": {},
                "last_collect_time": None,
                "total_cached_keys": 0,
                "push_enabled": False,
            }
            resp = client.get("/api/rt-kline/status")
            assert resp.status_code == 200
            assert resp.json()["is_running"] is True

    def test_runtime_health(self, client):
        with patch("stock_datasource.modules.realtime_kline.scheduler.get_runtime") as mock_rt_fn:
            mock_rt = MagicMock()
            mock_rt_fn.return_value = mock_rt
            mock_rt.is_running = True
            mock_rt.health.return_value = {"collector": True, "push": False, "sink": True}
            resp = client.get("/api/rt-kline/runtime/health")
            assert resp.status_code == 200
            assert resp.json()["workers"]["collector"] is True

    def test_trigger_collection(self, client):
        with patch("stock_datasource.modules.realtime_kline.scheduler.run_collection") as mock_run:
            mock_run.return_value = {"a_stock": 100, "etf": 20}
            resp = client.post("/api/rt-kline/trigger")
            assert resp.status_code == 200
            assert resp.json()["success"] is True
            assert resp.json()["markets_collected"]["a_stock"] == 100

    def test_trigger_sync(self, client):
        with patch("stock_datasource.modules.realtime_kline.scheduler.run_sink_tick") as mock_run:
            mock_run.return_value = {"all_ok": True, "markets": {"a_stock": {"ok": True, "records": 50}}}
            resp = client.post("/api/rt-kline/sync")
            assert resp.status_code == 200
            assert resp.json()["all_ok"] is True

    def test_push_switch_post(self, client):
        with patch("stock_datasource.modules.realtime_kline.cache.get_cache_store") as mock_cs, \
             patch("stock_datasource.modules.realtime_kline.scheduler.get_runtime") as mock_rt_fn:
            mock_cache = MagicMock()
            mock_cs.return_value = mock_cache
            mock_cache.set_push_switch.return_value = True

            mock_rt = MagicMock()
            mock_rt_fn.return_value = mock_rt

            resp = client.post("/api/rt-kline/push/switch", json={"enabled": True})
            assert resp.status_code == 200
            assert resp.json()["enabled"] is True

    def test_push_switch_get(self, client):
        with patch("stock_datasource.modules.realtime_kline.cloud_push._is_push_enabled", return_value=False):
            resp = client.get("/api/rt-kline/push/switch")
            assert resp.status_code == 200
            assert resp.json()["enabled"] is False

    def test_get_metrics(self, client):
        with patch("stock_datasource.modules.realtime_kline.metrics.metrics") as mock_m:
            mock_m.snapshot.return_value = {"counters": {"a": 1}, "gauges": {"b": 2.0}}
            resp = client.get("/api/rt-kline/metrics")
            assert resp.status_code == 200
            assert resp.json()["counters"]["a"] == 1

    def test_trigger_cleanup(self, client):
        with patch("stock_datasource.modules.realtime_kline.scheduler.run_cleanup") as mock_run:
            mock_run.return_value = {
                "stream_trimmed": {"a_stock": 10},
                "latest_deleted": 5,
                "push_state_cleared": {"a_stock": 1},
            }
            resp = client.post("/api/rt-kline/cleanup")
            assert resp.status_code == 200
            assert resp.json()["success"] is True


# ===================================================================
# 12. Integration: Collect → Cache → Sink pipeline
# ===================================================================
class TestPipelineIntegration:
    """End-to-end test: collector output → cache.store_snapshots → sink reads stream → writes CH."""

    def test_collect_to_sink_pipeline(self):
        from stock_datasource.modules.realtime_kline.cache import RealtimeKlineCacheStore
        from stock_datasource.modules.realtime_kline.sync_service import MinuteSinkWorker

        # -- Setup mock Redis with actual data flow simulation --
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        # Simulate store_snapshots writing to stream
        stored_stream: list = []

        def fake_xadd(key, entry, maxlen=None, approximate=True):
            eid = f"{int(time.time()*1000)}-{len(stored_stream)}"
            stored_stream.append((eid, entry))
            return eid

        mock_redis.xadd.side_effect = fake_xadd

        # Simulate xread_after returning stored stream data
        def fake_xread(streams_dict, count=None, block=None):
            if stored_stream:
                key = list(streams_dict.keys())[0]
                return [(key, stored_stream)]
            return None

        mock_redis.xread.side_effect = fake_xread

        # Cache store
        cache = RealtimeKlineCacheStore()
        cache._redis = mock_redis

        # Store snapshots (simulating collector output)
        with patch("stock_datasource.config.settings.settings") as mock_s:
            mock_s.RT_KLINE_LATEST_TTL_SECONDS = 86400
            mock_pipe = MagicMock()
            mock_redis.pipeline.return_value = mock_pipe

            # Make pipeline xadd also call our fake
            mock_pipe.xadd.side_effect = fake_xadd
            mock_pipe.execute.return_value = []

            rows = [
                {"ts_code": "000001.SZ", "close": 10.5, "trade_date": "20260301",
                 "version": 1000, "market": "a_stock", "name": "平安银行",
                 "collected_at": "2026-03-01 10:00:00"},
                {"ts_code": "000002.SZ", "close": 20.0, "trade_date": "20260301",
                 "version": 1000, "market": "a_stock", "name": "万科A",
                 "collected_at": "2026-03-01 10:00:00"},
            ]
            count = cache.store_snapshots("a_stock", rows)
            assert count == 2

        # Now verify sink can read from stream and write to ClickHouse
        assert len(stored_stream) == 2

        sink = MinuteSinkWorker()
        sink._cache = cache
        sink._ensured_tables = set(["ods_rt_kline_tick_cn"])  # skip DDL

        with patch("stock_datasource.modules.realtime_kline.sync_service._get_db") as mock_db_fn, \
             patch("stock_datasource.config.settings.settings") as mock_s:
            mock_db = MagicMock()
            mock_db_fn.return_value = mock_db
            mock_s.RT_KLINE_SINK_MARKET_RETRY_LIMIT = 3
            mock_s.CLICKHOUSE_DATABASE = "test"
            mock_s.RT_KLINE_STREAM_TTL_HOURS = 72

            ok, written = sink._sync_market("a_stock")
            assert ok is True
            assert written == 2
            mock_db.insert_dataframe.assert_called_once()
            # Verify DataFrame structure
            call_args = mock_db.insert_dataframe.call_args
            df = call_args[0][1]
            assert "ts_code" in df.columns
            assert "version" in df.columns
            assert len(df) == 2


# ===================================================================
# 13. Degradation: cloud unreachable, CH down, market isolation
# ===================================================================
class TestDegradation:
    def test_push_timeout_records_failure(self):
        """Network timeout should not crash push worker, just record failure."""
        import requests
        with patch("stock_datasource.config.settings.settings") as mock_s:
            mock_s.RT_KLINE_CLOUD_PUSH_ENABLED = True
            mock_s.RT_KLINE_CLOUD_PUSH_URL = "https://example.com/push"
            mock_s.RT_KLINE_CLOUD_PUSH_TOKEN = "tok"
            mock_s.RT_KLINE_CLOUD_PUSH_INTERVAL = 2.0
            mock_s.RT_KLINE_CLOUD_PUSH_WINDOW = 10.0
            mock_s.RT_KLINE_PUSH_CIRCUIT_BREAKER_MINUTES = 30
            mock_s.RT_KLINE_PUSH_MAX_BACKLOG = 10000
            mock_s.RT_KLINE_PUSH_DLQ_TTL_DAYS = 7

            with patch("stock_datasource.modules.realtime_kline.cloud_push.get_cache_store") as mock_fn:
                mock_cache = MagicMock()
                mock_fn.return_value = mock_cache
                mock_cache.get_circuit_breaker.return_value = False

                import stock_datasource.modules.realtime_kline.cloud_push as cp_mod
                cp_mod._push_worker = None
                from stock_datasource.modules.realtime_kline.cloud_push import CloudPushWorker
                worker = CloudPushWorker()
                worker._cache = mock_cache
                worker._session = MagicMock()
                worker._session.post.side_effect = requests.exceptions.Timeout("timeout")

                payload = {"symbol": "000001.SZ", "delta": {"close": 10}, "version": 1}
                result = worker._push_one("a_stock", payload)
                assert result is False
                assert worker._failure_start["a_stock"] is not None

    def test_sink_single_market_failure_isolation(self):
        """If one market fails, others should continue."""
        import stock_datasource.modules.realtime_kline.sync_service as ss_mod
        ss_mod._sink_worker = None

        mock_cache = MagicMock()
        mock_cache.get_checkpoint.return_value = "0-0"
        mock_cache.xlen.return_value = 0
        mock_cache.dlq_size.return_value = 0

        bar = {"ts_code": "000001.SZ", "close": 10.0, "trade_date": "20260301", "version": 1}

        # a_stock has data and fails; etf has no data
        def xread_side_effect(market, last_id="0-0", count=5000):
            if market == "a_stock":
                return [("100-0", {"payload": json.dumps(bar)})]
            return []

        mock_cache.xread_after.side_effect = xread_side_effect

        from stock_datasource.modules.realtime_kline.sync_service import MinuteSinkWorker
        worker = MinuteSinkWorker()
        worker._cache = mock_cache
        worker._ensured_tables = set(["ods_rt_kline_tick_cn", "ods_rt_kline_tick_etf",
                                       "ods_rt_kline_tick_index", "ods_rt_kline_tick_hk"])

        with patch("stock_datasource.modules.realtime_kline.sync_service._get_db") as mock_db_fn, \
             patch("stock_datasource.config.settings.settings") as mock_s:
            mock_db = MagicMock()
            mock_db.insert_dataframe.side_effect = Exception("CH down")
            mock_db_fn.return_value = mock_db
            mock_s.RT_KLINE_SINK_MARKET_RETRY_LIMIT = 1
            mock_s.CLICKHOUSE_DATABASE = "test"
            mock_s.RT_KLINE_STREAM_TTL_HOURS = 72

            with patch("time.sleep"):
                result = worker.tick()
                # a_stock should fail
                assert result["markets"]["a_stock"]["ok"] is False
                # etf/index/hk should succeed (no data, so ok=True)
                assert result["markets"]["etf"]["ok"] is True
                assert result["markets"]["index"]["ok"] is True

    def test_redis_unavailable_graceful(self):
        """If Redis is down, cache operations return safe defaults."""
        from stock_datasource.modules.realtime_kline.cache import RealtimeKlineCacheStore
        store = RealtimeKlineCacheStore()
        with patch.object(store, "_get_redis", return_value=None):
            assert store.available is False
            assert store.get_latest("a_stock", "x") is None
            assert store.get_all_latest() == []
            assert store.xadd_event("a_stock", {}) is None
            assert store.xrange_since("a_stock") == []
            assert store.xlen("a_stock") == 0
            assert store.get_checkpoint("ckpt", "a_stock") == "0-0"
            assert store.get_push_switch() is None
            assert store.get_circuit_breaker("a_stock") is False
            assert store.dlq_size("dlq", "a_stock") == 0
            assert store.store_snapshots("a_stock", [{"ts_code": "x"}]) == 0
