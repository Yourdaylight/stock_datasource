"""Unit tests for the realtime_minute module.

Covers: schemas, config, collector, cache_store, sync_service, service, scheduler.
All external dependencies (Redis, ClickHouse, Tushare) are mocked.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock

import pandas as pd
import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Test Schemas
# =============================================================================

class TestSchemas:
    """Test Pydantic models and enums."""

    def test_market_type_enum_values(self):
        from stock_datasource.modules.realtime_minute.schemas import MarketType
        assert MarketType.A_STOCK.value == "a_stock"
        assert MarketType.ETF.value == "etf"
        assert MarketType.INDEX.value == "index"
        assert MarketType.HK.value == "hk"

    def test_freq_type_enum_values(self):
        from stock_datasource.modules.realtime_minute.schemas import FreqType
        assert FreqType.MIN_1.value == "1min"
        assert FreqType.MIN_5.value == "5min"
        assert FreqType.MIN_15.value == "15min"
        assert FreqType.MIN_30.value == "30min"
        assert FreqType.MIN_60.value == "60min"

    def test_minute_bar_model(self):
        from stock_datasource.modules.realtime_minute.schemas import MinuteBar
        bar = MinuteBar(
            ts_code="600519.SH",
            trade_time="2026-03-01 10:00:00",
            open=1800.0,
            close=1810.0,
            high=1820.0,
            low=1790.0,
            vol=1000.0,
            amount=18000000.0,
        )
        assert bar.ts_code == "600519.SH"
        assert bar.close == 1810.0
        assert bar.pct_chg is None

    def test_minute_bar_optional_fields(self):
        from stock_datasource.modules.realtime_minute.schemas import MinuteBar
        bar = MinuteBar(ts_code="600519.SH", trade_time="2026-03-01 10:00:00")
        assert bar.open is None
        assert bar.vol is None

    def test_minute_data_response_defaults(self):
        from stock_datasource.modules.realtime_minute.schemas import MinuteDataResponse
        resp = MinuteDataResponse()
        assert resp.count == 0
        assert resp.data == []
        assert resp.freq == "1min"

    def test_batch_minute_data_response(self):
        from stock_datasource.modules.realtime_minute.schemas import BatchMinuteDataResponse
        resp = BatchMinuteDataResponse(freq="5min", total_codes=2, total_bars=10)
        assert resp.freq == "5min"
        assert resp.total_codes == 2

    def test_rank_response(self):
        from stock_datasource.modules.realtime_minute.schemas import RankResponse
        resp = RankResponse(rank_type="gainers")
        assert resp.rank_type == "gainers"
        assert resp.count == 0

    def test_market_overview_response(self):
        from stock_datasource.modules.realtime_minute.schemas import MarketOverviewResponse
        resp = MarketOverviewResponse()
        assert resp.total == 0
        assert resp.avg_pct_chg is None

    def test_market_stats_response(self):
        from stock_datasource.modules.realtime_minute.schemas import MarketStatsResponse
        resp = MarketStatsResponse()
        assert resp.limit_up_count == 0
        assert resp.markets == {}

    def test_collect_status_response(self):
        from stock_datasource.modules.realtime_minute.schemas import CollectStatusResponse
        resp = CollectStatusResponse()
        assert resp.is_collecting is False
        assert resp.total_cached_keys == 0

    def test_trigger_response(self):
        from stock_datasource.modules.realtime_minute.schemas import TriggerResponse
        resp = TriggerResponse(success=True, message="OK")
        assert resp.success is True

    def test_refresh_codes_response(self):
        from stock_datasource.modules.realtime_minute.schemas import RefreshCodesResponse
        resp = RefreshCodesResponse(success=False, message="error")
        assert resp.success is False


# =============================================================================
# Test Config
# =============================================================================

class TestConfig:
    """Test static configuration values."""

    def test_index_codes_non_empty(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert len(cfg.INDEX_CODES) >= 8

    def test_hot_etf_codes_non_empty(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert len(cfg.HOT_ETF_CODES) >= 20

    def test_astock_batches_structure(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert isinstance(cfg.ASTOCK_BATCHES, list)
        assert len(cfg.ASTOCK_BATCHES) >= 1
        assert isinstance(cfg.ASTOCK_BATCHES[0], list)

    def test_hk_codes_non_empty(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert len(cfg.HK_CODES) >= 6

    def test_rate_limit_config(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert cfg.RATE_LIMIT_PER_MINUTE == 120
        assert cfg.MIN_CALL_INTERVAL == pytest.approx(0.5, abs=0.01)

    def test_redis_key_prefixes(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert "zset" in cfg.REDIS_KEY_PREFIX_ZSET
        assert "latest" in cfg.REDIS_KEY_PREFIX_LATEST
        assert "status" in cfg.REDIS_KEY_STATUS

    def test_sync_time_format(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        h, m = cfg.SYNC_TIME.split(":")
        assert int(h) == 15
        assert int(m) == 30

    def test_trading_hours_structure(self):
        from stock_datasource.modules.realtime_minute import config as cfg
        assert len(cfg.CN_TRADING_HOURS) == 2
        assert len(cfg.HK_TRADING_HOURS) == 2
        for start, end in cfg.CN_TRADING_HOURS:
            assert start < end


# =============================================================================
# Test Collector
# =============================================================================

class TestCollector:
    """Test RealtimeMinuteCollector with mocked Tushare API."""

    @pytest.fixture
    def collector(self):
        with patch("stock_datasource.modules.realtime_minute.collector.settings") as mock_settings:
            mock_settings.TUSHARE_TOKEN = "test_token"
            with patch("stock_datasource.modules.realtime_minute.collector.ts") as mock_ts:
                mock_ts.pro_api.return_value = MagicMock()
                from stock_datasource.modules.realtime_minute.collector import RealtimeMinuteCollector
                c = RealtimeMinuteCollector()
                return c

    @pytest.fixture
    def sample_rt_min_df(self):
        """Sample DataFrame mimicking rt_min response."""
        return pd.DataFrame({
            "ts_code": ["600519.SH", "600519.SH"],
            "trade_time": ["2026-03-01 10:00:00", "2026-03-01 10:01:00"],
            "open": [1800.0, 1810.0],
            "close": [1810.0, 1815.0],
            "high": [1820.0, 1818.0],
            "low": [1795.0, 1808.0],
            "vol": [1000.0, 800.0],
            "amount": [18000000.0, 14000000.0],
        })

    def test_collector_init(self, collector):
        assert collector.pro is not None
        assert collector._min_interval > 0

    def test_normalize_empty_df(self, collector):
        from stock_datasource.modules.realtime_minute.schemas import MarketType
        result = collector._normalize(pd.DataFrame(), MarketType.A_STOCK, "1min")
        assert result.empty

    def test_normalize_adds_metadata(self, collector, sample_rt_min_df):
        from stock_datasource.modules.realtime_minute.schemas import MarketType
        result = collector._normalize(sample_rt_min_df, MarketType.A_STOCK, "1min")
        assert "market_type" in result.columns
        assert "freq" in result.columns
        assert result["market_type"].iloc[0] == "a_stock"
        assert result["freq"].iloc[0] == "1min"

    def test_normalize_renames_trade_date(self, collector):
        from stock_datasource.modules.realtime_minute.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["00700.HK"],
            "trade_date": ["2026-03-01 10:00:00"],
            "open": [350.0],
            "close": [355.0],
            "high": [358.0],
            "low": [348.0],
            "vol": [5000.0],
            "amount": [1750000.0],
        })
        result = collector._normalize(df, MarketType.HK, "5min")
        assert "trade_time" in result.columns
        assert result["market_type"].iloc[0] == "hk"

    def test_normalize_fills_missing_columns(self, collector):
        from stock_datasource.modules.realtime_minute.schemas import MarketType
        df = pd.DataFrame({
            "ts_code": ["600000.SH"],
            "trade_time": ["2026-03-01 10:00:00"],
        })
        result = collector._normalize(df, MarketType.A_STOCK, "1min")
        for col in ["open", "close", "high", "low", "vol", "amount"]:
            assert col in result.columns

    def test_collect_astock_with_mock(self, collector, sample_rt_min_df):
        collector._call_rt_min = MagicMock(return_value=sample_rt_min_df)
        with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
            mock_cfg.ASTOCK_BATCHES = [["600519.SH"]]
            result = collector.collect_astock("1min")
            assert not result.empty
            assert "market_type" in result.columns

    def test_collect_etf_with_mock(self, collector, sample_rt_min_df):
        collector._call_rt_min = MagicMock(return_value=sample_rt_min_df)
        with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
            mock_cfg.HOT_ETF_CODES = ["510050.SH"]
            result = collector.collect_etf("1min")
            assert not result.empty

    def test_collect_index_with_mock(self, collector):
        idx_df = pd.DataFrame({
            "ts_code": ["000001.SH"],
            "trade_time": ["2026-03-01 10:00:00"],
            "open": [3200.0], "close": [3210.0],
            "high": [3220.0], "low": [3190.0],
            "vol": [50000.0], "amount": [5000000.0],
        })
        collector._call_rt_idx_min = MagicMock(return_value=idx_df)
        with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
            mock_cfg.INDEX_CODES = ["000001.SH"]
            result = collector.collect_index("1min")
            assert not result.empty
            assert result["market_type"].iloc[0] == "index"

    def test_collect_hk_with_mock(self, collector):
        hk_df = pd.DataFrame({
            "ts_code": ["00700.HK"],
            "trade_time": ["2026-03-01 10:00:00"],
            "open": [350.0], "close": [355.0],
            "high": [358.0], "low": [348.0],
            "vol": [5000.0], "amount": [1750000.0],
        })
        collector._call_hk_mins = MagicMock(return_value=hk_df)
        with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
            mock_cfg.HK_CODES = ["00700.HK"]
            result = collector.collect_hk("1min")
            assert not result.empty
            assert result["market_type"].iloc[0] == "hk"

    def test_collect_all_default_markets(self, collector, sample_rt_min_df):
        collector.collect_astock = MagicMock(return_value=sample_rt_min_df)
        collector.collect_etf = MagicMock(return_value=sample_rt_min_df)
        collector.collect_index = MagicMock(return_value=sample_rt_min_df)
        collector.collect_hk = MagicMock(return_value=sample_rt_min_df)

        result = collector.collect_all("1min")
        assert "a_stock" in result
        assert "etf" in result
        assert "index" in result
        assert "hk" in result
        assert not result["a_stock"].empty

    def test_collect_all_selected_markets(self, collector, sample_rt_min_df):
        collector.collect_astock = MagicMock(return_value=sample_rt_min_df)
        collector.collect_etf = MagicMock(return_value=pd.DataFrame())

        result = collector.collect_all("1min", markets=["a_stock", "etf"])
        assert "a_stock" in result
        assert "etf" in result
        assert "index" not in result

    def test_collect_all_unknown_market(self, collector):
        result = collector.collect_all("1min", markets=["unknown"])
        assert "unknown" not in result

    def test_collect_astock_handles_api_failure(self, collector):
        collector._call_rt_min = MagicMock(side_effect=Exception("API error"))
        with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
            mock_cfg.ASTOCK_BATCHES = [["600519.SH"]]
            result = collector.collect_astock("1min")
            assert result.empty

    def test_rate_limit_sleeps(self, collector):
        """Verify rate limiter enforces minimum interval."""
        import time
        collector._last_call_time = time.time()
        collector._min_interval = 0.1
        start = time.time()
        collector._rate_limit()
        elapsed = time.time() - start
        assert elapsed >= 0.05  # Should have slept some time


# =============================================================================
# Test CacheStore
# =============================================================================

class TestCacheStore:
    """Test RealtimeMinuteCacheStore with mocked Redis."""

    @pytest.fixture
    def cache_store(self):
        from stock_datasource.modules.realtime_minute.cache_store import RealtimeMinuteCacheStore
        store = RealtimeMinuteCacheStore()
        return store

    @pytest.fixture
    def mock_redis(self, cache_store):
        mock_r = MagicMock()
        mock_r.ping.return_value = True
        cache_store._redis = mock_r
        return mock_r

    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame({
            "ts_code": ["600519.SH"],
            "trade_time": pd.to_datetime(["2026-03-01 10:00:00"]),
            "open": [1800.0],
            "close": [1810.0],
            "high": [1820.0],
            "low": [1790.0],
            "vol": [1000.0],
            "amount": [18000000.0],
            "market_type": ["a_stock"],
            "freq": ["1min"],
        })

    def test_zset_key_format(self, cache_store):
        key = cache_store._zset_key("a_stock", "600519.SH", "1min", "20260301")
        assert "zset" in key
        assert "a_stock" in key
        assert "600519.SH" in key
        assert "20260301" in key

    def test_latest_key_format(self, cache_store):
        key = cache_store._latest_key("etf", "510050.SH", "1min")
        assert "latest" in key
        assert "etf" in key
        assert "510050.SH" in key

    def test_available_returns_false_without_redis(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            assert cache_store.available is False

    def test_available_returns_true_with_redis(self, cache_store, mock_redis):
        assert cache_store.available is True

    def test_store_bars_returns_zero_when_no_redis(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            result = cache_store.store_bars(pd.DataFrame({"ts_code": ["X"]}))
            assert result == 0

    def test_store_bars_returns_zero_for_empty_df(self, cache_store, mock_redis):
        result = cache_store.store_bars(pd.DataFrame())
        assert result == 0

    def test_store_bars_writes_to_pipeline(self, cache_store, mock_redis, sample_df):
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = []

        count = cache_store.store_bars(sample_df)
        assert count == 1
        assert mock_pipe.zadd.called
        assert mock_pipe.set.called
        assert mock_pipe.expire.called
        mock_pipe.execute.assert_called_once()

    def test_store_bars_skips_rows_without_ts_code(self, cache_store, mock_redis):
        df = pd.DataFrame({
            "ts_code": [None],
            "trade_time": pd.to_datetime(["2026-03-01 10:00:00"]),
            "market_type": ["a_stock"],
            "freq": ["1min"],
        })
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = []

        count = cache_store.store_bars(df)
        assert count == 0

    def test_store_bars_handles_pipeline_error(self, cache_store, mock_redis, sample_df):
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.side_effect = Exception("Redis error")

        count = cache_store.store_bars(sample_df)
        assert count == 0

    def test_get_bars_returns_empty_when_no_redis(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            result = cache_store.get_bars("a_stock", "600519.SH")
            assert result == []

    def test_get_bars_returns_parsed_data(self, cache_store, mock_redis):
        bar_json = json.dumps({"ts_code": "600519.SH", "close": 1810.0})
        mock_redis.zrangebyscore.return_value = [bar_json]
        result = cache_store.get_bars("a_stock", "600519.SH", "1min", "20260301")
        assert len(result) == 1
        assert result[0]["ts_code"] == "600519.SH"

    def test_get_bars_with_time_range(self, cache_store, mock_redis):
        mock_redis.zrangebyscore.return_value = []
        result = cache_store.get_bars(
            "a_stock", "600519.SH", "1min", "20260301",
            start_time="2026-03-01 09:30:00",
            end_time="2026-03-01 11:30:00",
        )
        assert result == []
        # Verify min/max score were set (not -inf/+inf)
        call_args = mock_redis.zrangebyscore.call_args
        assert call_args[0][1] != "-inf"
        assert call_args[0][2] != "+inf"

    def test_get_latest_returns_none_when_no_redis(self, cache_store):
        with patch.object(cache_store, "_get_redis", return_value=None):
            result = cache_store.get_latest("a_stock", "600519.SH")
            assert result is None

    def test_get_latest_returns_data(self, cache_store, mock_redis):
        bar_json = json.dumps({"ts_code": "600519.SH", "close": 1810.0})
        mock_redis.get.return_value = bar_json
        result = cache_store.get_latest("a_stock", "600519.SH")
        assert result["close"] == 1810.0

    def test_get_latest_returns_none_when_no_data(self, cache_store, mock_redis):
        mock_redis.get.return_value = None
        result = cache_store.get_latest("a_stock", "600519.SH")
        assert result is None

    def test_get_all_latest_with_market_filter(self, cache_store, mock_redis):
        bar_json = json.dumps({"ts_code": "600519.SH", "close": 1810.0})
        mock_redis.scan.return_value = (0, ["key1"])
        mock_redis.mget.return_value = [bar_json]
        result = cache_store.get_all_latest(market="a_stock", freq="1min")
        assert len(result) == 1

    def test_get_all_latest_without_market(self, cache_store, mock_redis):
        mock_redis.scan.return_value = (0, [])
        result = cache_store.get_all_latest(freq="1min")
        assert result == []

    def test_get_status_empty(self, cache_store, mock_redis):
        mock_redis.hgetall.return_value = {}
        result = cache_store.get_status()
        assert result == {}

    def test_get_status_with_data(self, cache_store, mock_redis):
        mock_redis.hgetall.return_value = {
            "a_stock": json.dumps({"last_collect_time": "2026-03-01 10:00:00", "records": 100}),
        }
        result = cache_store.get_status()
        assert "a_stock" in result
        assert result["a_stock"]["records"] == 100

    def test_update_status(self, cache_store, mock_redis):
        cache_store.update_status("a_stock", 100)
        assert mock_redis.hset.called
        assert mock_redis.expire.called

    def test_get_all_bars_for_date(self, cache_store, mock_redis):
        bar_json = json.dumps({"ts_code": "600519.SH"})
        mock_redis.scan.return_value = (0, ["key1"])
        mock_redis.zrange.return_value = [bar_json]
        result = cache_store.get_all_bars_for_date("20260301")
        assert len(result) == 1

    def test_cleanup_date(self, cache_store, mock_redis):
        mock_redis.scan.return_value = (0, ["key1", "key2"])
        mock_redis.delete.return_value = 2
        deleted = cache_store.cleanup_date("20260301")
        assert deleted == 2

    def test_cleanup_latest(self, cache_store, mock_redis):
        mock_redis.scan.return_value = (0, ["key1"])
        mock_redis.delete.return_value = 1
        deleted = cache_store.cleanup_latest()
        assert deleted == 1

    def test_get_cached_key_count(self, cache_store, mock_redis):
        mock_redis.scan.side_effect = [
            (0, ["k1", "k2"]),  # ZSET prefix
            (0, ["k3"]),        # LATEST prefix
        ]
        count = cache_store.get_cached_key_count()
        assert count == 3

    def test_safe_value_replaces_nan(self):
        from stock_datasource.modules.realtime_minute.cache_store import _safe_value
        assert _safe_value(float("nan")) is None
        assert _safe_value(float("inf")) is None
        assert _safe_value(1.5) == 1.5
        assert _safe_value("hello") == "hello"

    def test_store_bars_handles_string_trade_time(self, cache_store, mock_redis):
        """Verify store_bars can handle trade_time as a string."""
        df = pd.DataFrame({
            "ts_code": ["600519.SH"],
            "trade_time": ["2026-03-01 10:00:00"],
            "open": [1800.0], "close": [1810.0],
            "high": [1820.0], "low": [1790.0],
            "vol": [1000.0], "amount": [18000000.0],
            "market_type": ["a_stock"],
            "freq": ["1min"],
        })
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = []
        count = cache_store.store_bars(df)
        assert count == 1


# =============================================================================
# Test SyncService
# =============================================================================

class TestSyncService:
    """Test RealtimeMinuteSyncService with mocked Redis and ClickHouse."""

    @pytest.fixture
    def sync_service(self):
        from stock_datasource.modules.realtime_minute.sync_service import RealtimeMinuteSyncService
        svc = RealtimeMinuteSyncService()
        return svc

    def test_init_table_name(self, sync_service):
        assert sync_service._ensured_tables == set()

    def test_ensure_table_creates_table(self, sync_service):
        with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db, \
             patch("stock_datasource.config.settings.settings") as mock_settings:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_settings.CLICKHOUSE_DATABASE = "test_db"
            sync_service.ensure_table("a_stock")
            mock_db.execute.assert_called_once()
            assert "ods_min_kline_cn" in sync_service._ensured_tables

    def test_ensure_table_skips_if_already_ensured(self, sync_service):
        sync_service._ensured_tables.add("ods_min_kline_cn")
        with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
            sync_service.ensure_table("a_stock")
            mock_get_db.assert_not_called()

    def test_ensure_table_handles_error(self, sync_service):
        with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
            mock_get_db.side_effect = Exception("DB error")
            sync_service.ensure_table("a_stock")
            assert "ods_min_kline_cn" not in sync_service._ensured_tables

    def test_ensure_table_all_markets(self, sync_service):
        with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db, \
             patch("stock_datasource.config.settings.settings") as mock_settings:
            mock_db = MagicMock()
            mock_get_db.return_value = mock_db
            mock_settings.CLICKHOUSE_DATABASE = "test_db"
            sync_service.ensure_table()  # No market = all markets
            assert mock_db.execute.call_count == 4  # cn, etf, index, hk

    def test_sync_no_data(self, sync_service):
        sync_service._ensured_tables = {"ods_min_kline_cn", "ods_min_kline_etf", "ods_min_kline_index", "ods_min_kline_hk"}
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_store.get_all_bars_for_date.return_value = []
            mock_cache.return_value = mock_store
            result = sync_service.sync("20260301")
            assert result["synced"] == 0

    def test_sync_with_data(self, sync_service):
        sync_service._ensured_tables = {"ods_min_kline_cn", "ods_min_kline_etf", "ods_min_kline_index", "ods_min_kline_hk"}
        bars = [
            {
                "ts_code": "600519.SH",
                "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0,
                "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
                "market_type": "a_stock", "freq": "1min",
            },
        ]
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_store.get_all_bars_for_date.return_value = bars
            mock_cache.return_value = mock_store

            with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                result = sync_service.sync("20260301")
                assert result["synced"] == 1
                mock_db.insert_dataframe.assert_called_once()
                # Verify it wrote to the correct per-market table
                call_args = mock_db.insert_dataframe.call_args
                assert call_args[0][0] == "ods_min_kline_cn"

    def test_sync_handles_insert_error(self, sync_service):
        sync_service._ensured_tables = {"ods_min_kline_cn", "ods_min_kline_etf", "ods_min_kline_index", "ods_min_kline_hk"}
        bars = [
            {
                "ts_code": "600519.SH",
                "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0,
                "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
                "market_type": "a_stock", "freq": "1min",
            },
        ]
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_store.get_all_bars_for_date.return_value = bars
            mock_cache.return_value = mock_store

            with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_db.insert_dataframe.side_effect = Exception("Insert failed")
                mock_get_db.return_value = mock_db
                result = sync_service.sync("20260301")
                assert result["synced"] == 0

    def test_sync_multi_market(self, sync_service):
        """Test that sync correctly splits data into per-market tables."""
        sync_service._ensured_tables = {"ods_min_kline_cn", "ods_min_kline_etf", "ods_min_kline_index", "ods_min_kline_hk"}
        bars = [
            {
                "ts_code": "600519.SH", "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0, "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
                "market_type": "a_stock", "freq": "1min",
            },
            {
                "ts_code": "510050.SH", "trade_time": "2026-03-01 10:00:00",
                "open": 3.2, "close": 3.3, "high": 3.35, "low": 3.18,
                "vol": 5000.0, "amount": 16000.0,
                "market_type": "etf", "freq": "1min",
            },
        ]
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_store.get_all_bars_for_date.return_value = bars
            mock_cache.return_value = mock_store

            with patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
                mock_db = MagicMock()
                mock_get_db.return_value = mock_db
                result = sync_service.sync("20260301")
                assert result["synced"] == 2
                assert mock_db.insert_dataframe.call_count == 2
                tables_written = {c[0][0] for c in mock_db.insert_dataframe.call_args_list}
                assert "ods_min_kline_cn" in tables_written
                assert "ods_min_kline_etf" in tables_written

    def test_cleanup_delegates_to_cache(self, sync_service):
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_store.cleanup_date.return_value = 5
            mock_store.cleanup_latest.return_value = 3
            mock_cache.return_value = mock_store

            result = sync_service.cleanup("20260301")
            assert result["zset_deleted"] == 5
            assert result["latest_deleted"] == 3


# =============================================================================
# Test Service (query layer)
# =============================================================================

class TestService:
    """Test RealtimeMinuteService query logic."""

    @pytest.fixture
    def service(self):
        with patch("stock_datasource.modules.realtime_minute.service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            mock_cache.return_value = mock_store
            from stock_datasource.modules.realtime_minute.service import RealtimeMinuteService
            svc = RealtimeMinuteService()
            svc._cache = mock_store
            return svc

    def test_detect_market_hk(self):
        from stock_datasource.modules.realtime_minute.service import _detect_market
        assert _detect_market("00700.HK") == "hk"

    def test_detect_market_etf(self):
        from stock_datasource.modules.realtime_minute.service import _detect_market
        assert _detect_market("510050.SH") == "etf"
        assert _detect_market("159915.SZ") == "etf"

    def test_detect_market_index(self):
        from stock_datasource.modules.realtime_minute.service import _detect_market
        # 000001.SH is in INDEX_CODES
        assert _detect_market("000001.SH") == "index"

    def test_detect_market_astock(self):
        from stock_datasource.modules.realtime_minute.service import _detect_market
        assert _detect_market("600519.SH") == "a_stock"

    def test_get_minute_data_from_cache(self, service):
        service._cache.get_bars.return_value = [
            {"ts_code": "600519.SH", "close": 1810.0, "trade_time": "2026-03-01 10:00:00"},
        ]
        result = service.get_minute_data("600519.SH")
        assert result["count"] == 1
        assert result["ts_code"] == "600519.SH"

    def test_get_minute_data_fallback_to_clickhouse(self, service):
        service._cache.get_bars.return_value = []
        with patch("stock_datasource.modules.realtime_minute.service._execute_query") as mock_query:
            mock_query.return_value = [
                {"ts_code": "600519.SH", "close": 1810.0, "trade_time": "2026-03-01 10:00:00"},
            ]
            result = service.get_minute_data("600519.SH", date="20260301")
            assert result["count"] == 1
            mock_query.assert_called_once()

    def test_get_batch_minute_data(self, service):
        service._cache.get_bars.return_value = [
            {"ts_code": "600519.SH", "close": 1810.0, "trade_time": "2026-03-01 10:00:00"},
        ]
        result = service.get_batch_minute_data(["600519.SH", "600036.SH"])
        assert result["total_codes"] == 2
        assert "600519.SH" in result["data"]

    def test_get_latest_minute(self, service):
        service._cache.get_latest.return_value = {"ts_code": "600519.SH", "close": 1810.0}
        result = service.get_latest_minute("600519.SH")
        assert result["close"] == 1810.0

    def test_get_collect_status(self, service):
        service._cache.get_status.return_value = {
            "a_stock": {"last_collect_time": "2026-03-01 10:00:00", "records": 100},
        }
        service._cache.get_cached_key_count.return_value = 50
        result = service.get_collect_status()
        assert result["total_cached_keys"] == 50
        assert "a_stock" in result["markets"]
        assert result["last_collect_time"] == "2026-03-01 10:00:00"

    def test_get_top_gainers(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000},
        ]
        result = service.get_top_gainers()
        assert result["rank_type"] == "gainers"
        # A has positive pct_chg, B has negative
        assert result["data"][0]["ts_code"] == "A"

    def test_get_top_losers(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000},
        ]
        result = service.get_top_losers()
        assert result["rank_type"] == "losers"
        assert result["data"][0]["ts_code"] == "B"

    def test_get_top_volume(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000},
        ]
        result = service.get_top_volume()
        assert result["rank_type"] == "volume"
        assert result["data"][0]["ts_code"] == "B"  # Higher vol

    def test_get_top_amount(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000},
        ]
        result = service.get_top_amount()
        assert result["rank_type"] == "amount"
        assert result["data"][0]["ts_code"] == "B"  # Higher amount

    def test_rank_limit(self, service):
        items = [
            {"ts_code": f"S{i}", "open": 10.0, "close": 10.0 + i, "vol": i * 10, "amount": i * 100}
            for i in range(30)
        ]
        service._cache.get_all_latest.return_value = items
        result = service.get_top_gainers(limit=5)
        assert len(result["data"]) == 5

    def test_rank_handles_zero_open(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "X", "open": 0, "close": 10.0, "vol": 100, "amount": 1000},
        ]
        result = service.get_top_gainers()
        assert result["data"][0]["pct_chg"] == 0

    def test_get_market_overview_empty(self, service):
        service._cache.get_all_latest.return_value = []
        result = service.get_market_overview()
        assert result["total"] == 0
        assert result["avg_pct_chg"] is None

    def test_get_market_overview_with_data(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000},
            {"ts_code": "C", "open": 10.0, "close": 10.0, "vol": 150, "amount": 1500},
        ]
        result = service.get_market_overview()
        assert result["total"] == 3
        assert result["up_count"] == 1
        assert result["down_count"] == 1
        assert result["flat_count"] == 1
        assert result["total_vol"] == 450.0
        assert result["total_amount"] == 4500.0

    def test_get_market_stats_with_limit_up(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "vol": 100, "amount": 1000, "market_type": "a_stock"},
            {"ts_code": "B", "open": 10.0, "close": 9.0, "vol": 200, "amount": 2000, "market_type": "a_stock"},
        ]
        result = service.get_market_stats()
        assert result["total"] == 2
        assert result["up_count"] == 1
        assert result["down_count"] == 1
        assert "a_stock" in result["markets"]

    def test_get_market_stats_limit_up_detection(self, service):
        service._cache.get_all_latest.return_value = [
            {"ts_code": "A", "open": 10.0, "close": 11.0, "market_type": "a_stock"},  # +10%
        ]
        result = service.get_market_stats()
        assert result["limit_up_count"] == 1

    def test_get_kline_data(self, service):
        service._cache.get_bars.return_value = [
            {
                "ts_code": "600519.SH", "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0, "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
            },
        ]
        result = service.get_kline_data("600519.SH")
        assert result["count"] == 1
        kline = result["klines"][0]
        assert kline["time"] == "2026-03-01 10:00:00"
        assert kline["open"] == 1800.0
        assert kline["volume"] == 1000.0

    def test_query_clickhouse_parameterized(self, service):
        """Verify ClickHouse fallback uses parameterized SQL."""
        with patch("stock_datasource.modules.realtime_minute.service._execute_query") as mock_query:
            mock_query.return_value = []
            service._query_clickhouse("600519.SH", "1min", "20260301")
            args, kwargs = mock_query.call_args
            query = args[0]
            params = args[1]
            assert "%(ts_code)s" in query
            assert "%(freq)s" in query
            assert params["ts_code"] == "600519.SH"
            assert params["freq"] == "1min"


# =============================================================================
# Test Scheduler
# =============================================================================

class TestScheduler:
    """Test scheduler functions."""

    def test_is_trading_time_during_morning(self):
        from stock_datasource.modules.realtime_minute.scheduler import is_trading_time
        with patch("stock_datasource.modules.realtime_minute.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 10, 0, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            assert is_trading_time() is True

    def test_is_trading_time_during_afternoon(self):
        from stock_datasource.modules.realtime_minute.scheduler import is_trading_time
        with patch("stock_datasource.modules.realtime_minute.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 14, 0, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            assert is_trading_time() is True

    def test_is_trading_time_outside_hours(self):
        from stock_datasource.modules.realtime_minute.scheduler import is_trading_time
        with patch("stock_datasource.modules.realtime_minute.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 3, 2, 20, 0, 0)
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)
            assert is_trading_time() is False

    def test_run_collection(self):
        with patch("stock_datasource.modules.realtime_minute.collector.get_collector") as mock_get_collector, \
             patch("stock_datasource.modules.realtime_minute.cache_store.get_cache_store") as mock_get_cache:
            mock_collector = MagicMock()
            mock_collector.collect_all.return_value = {
                "a_stock": pd.DataFrame({"ts_code": ["600519.SH"]}),
            }
            mock_get_collector.return_value = mock_collector

            mock_store = MagicMock()
            mock_store.store_bars.return_value = 1
            mock_get_cache.return_value = mock_store

            from stock_datasource.modules.realtime_minute.scheduler import run_collection
            result = run_collection()
            assert result["a_stock"] == 1

    def test_run_sync(self):
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_sync_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.sync.return_value = {"date": "20260301", "synced": 100}
            mock_get_svc.return_value = mock_svc

            from stock_datasource.modules.realtime_minute.scheduler import run_sync
            result = run_sync("20260301")
            assert result["synced"] == 100

    def test_run_cleanup(self):
        with patch("stock_datasource.modules.realtime_minute.sync_service.get_sync_service") as mock_get_svc:
            mock_svc = MagicMock()
            mock_svc.cleanup.return_value = {"zset_deleted": 5, "latest_deleted": 3}
            mock_get_svc.return_value = mock_svc

            from stock_datasource.modules.realtime_minute.scheduler import run_cleanup
            result = run_cleanup("20260301")
            assert result["zset_deleted"] == 5

    def test_register_realtime_jobs(self):
        from stock_datasource.modules.realtime_minute.scheduler import register_realtime_jobs
        mock_scheduler = MagicMock()
        register_realtime_jobs(mock_scheduler)
        assert mock_scheduler.add_job.call_count == 3
        job_ids = [call.kwargs.get("id") or call[1].get("id", "") for call in mock_scheduler.add_job.call_args_list]
        assert "rt_minute_collect" in job_ids
        assert "rt_minute_sync" in job_ids
        assert "rt_minute_cleanup" in job_ids
