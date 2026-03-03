"""Integration tests for the realtime_minute module.

Tests the full API router layer using FastAPI TestClient.
All external dependencies (Redis, ClickHouse, Tushare) are mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# =============================================================================
# Test API Routes (Integration)
# =============================================================================

class TestRealtimeMinuteAPI:
    """Integration tests for router endpoints via TestClient."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI TestClient with the realtime_minute router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from stock_datasource.modules.realtime_minute.router import router

        app = FastAPI()
        app.include_router(router, prefix="/api/realtime")
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_service(self):
        """Mock the service singleton for all tests."""
        with patch("stock_datasource.modules.realtime_minute.router.get_realtime_minute_service") as mock_get:
            svc = MagicMock()
            mock_get.return_value = svc
            self._svc = svc
            yield svc

    # ------------------------------------------------------------------
    # GET /minute
    # ------------------------------------------------------------------

    def test_get_minute_data(self, client):
        self._svc.get_minute_data.return_value = {
            "ts_code": "600519.SH",
            "freq": "1min",
            "count": 1,
            "data": [{
                "ts_code": "600519.SH",
                "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0,
                "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
            }],
        }
        resp = client.get("/api/realtime/minute?ts_code=600519.SH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ts_code"] == "600519.SH"
        assert data["count"] == 1

    def test_get_minute_data_requires_ts_code(self, client):
        resp = client.get("/api/realtime/minute")
        assert resp.status_code == 422  # Validation error

    def test_get_minute_data_with_params(self, client):
        self._svc.get_minute_data.return_value = {
            "ts_code": "600519.SH", "freq": "5min", "count": 0, "data": [],
        }
        resp = client.get(
            "/api/realtime/minute?ts_code=600519.SH&freq=5min&date=20260301"
            "&start_time=09:30:00&end_time=11:30:00"
        )
        assert resp.status_code == 200
        self._svc.get_minute_data.assert_called_once_with(
            "600519.SH", "5min", "20260301", "09:30:00", "11:30:00"
        )

    # ------------------------------------------------------------------
    # GET /minute/batch
    # ------------------------------------------------------------------

    def test_get_batch_minute_data(self, client):
        self._svc.get_batch_minute_data.return_value = {
            "freq": "1min", "total_codes": 2, "total_bars": 4, "data": {},
        }
        resp = client.get("/api/realtime/minute/batch?ts_codes=600519.SH,600036.SH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_codes"] == 2

    def test_get_batch_minute_data_empty_codes(self, client):
        resp = client.get("/api/realtime/minute/batch?ts_codes=")
        assert resp.status_code == 400

    def test_get_batch_minute_data_too_many_codes(self, client):
        codes = ",".join([f"code{i}.SH" for i in range(51)])
        resp = client.get(f"/api/realtime/minute/batch?ts_codes={codes}")
        assert resp.status_code == 400

    # ------------------------------------------------------------------
    # GET /minute/latest
    # ------------------------------------------------------------------

    def test_get_latest_minute(self, client):
        self._svc.get_latest_minute.return_value = {
            "ts_code": "600519.SH", "close": 1810.0,
        }
        resp = client.get("/api/realtime/minute/latest?ts_code=600519.SH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["close"] == 1810.0

    def test_get_latest_minute_no_data(self, client):
        self._svc.get_latest_minute.return_value = None
        resp = client.get("/api/realtime/minute/latest?ts_code=600519.SH")
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"] is None

    # ------------------------------------------------------------------
    # GET /minute/kline
    # ------------------------------------------------------------------

    def test_get_kline_data(self, client):
        self._svc.get_kline_data.return_value = {
            "ts_code": "600519.SH",
            "freq": "1min",
            "count": 1,
            "klines": [{"time": "2026-03-01 10:00:00", "open": 1800.0}],
        }
        resp = client.get("/api/realtime/minute/kline?ts_code=600519.SH")
        assert resp.status_code == 200

    # ------------------------------------------------------------------
    # GET /status
    # ------------------------------------------------------------------

    def test_get_collect_status(self, client):
        self._svc.get_collect_status.return_value = {
            "is_collecting": False,
            "markets": {},
            "last_collect_time": None,
            "total_cached_keys": 0,
        }
        resp = client.get("/api/realtime/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_collecting"] is False

    # ------------------------------------------------------------------
    # GET /rank/*
    # ------------------------------------------------------------------

    def test_get_top_gainers(self, client):
        self._svc.get_top_gainers.return_value = {
            "rank_type": "gainers", "freq": "1min", "count": 0, "data": [],
        }
        resp = client.get("/api/realtime/rank/gainers")
        assert resp.status_code == 200
        assert resp.json()["rank_type"] == "gainers"

    def test_get_top_losers(self, client):
        self._svc.get_top_losers.return_value = {
            "rank_type": "losers", "freq": "1min", "count": 0, "data": [],
        }
        resp = client.get("/api/realtime/rank/losers")
        assert resp.status_code == 200

    def test_get_top_volume(self, client):
        self._svc.get_top_volume.return_value = {
            "rank_type": "volume", "freq": "1min", "count": 0, "data": [],
        }
        resp = client.get("/api/realtime/rank/volume")
        assert resp.status_code == 200

    def test_get_top_amount(self, client):
        self._svc.get_top_amount.return_value = {
            "rank_type": "amount", "freq": "1min", "count": 0, "data": [],
        }
        resp = client.get("/api/realtime/rank/amount")
        assert resp.status_code == 200

    def test_rank_with_market_filter(self, client):
        self._svc.get_top_gainers.return_value = {
            "rank_type": "gainers", "freq": "1min", "count": 0, "data": [],
        }
        resp = client.get("/api/realtime/rank/gainers?market=etf&limit=10")
        assert resp.status_code == 200
        self._svc.get_top_gainers.assert_called_once_with("1min", "etf", 10)

    # ------------------------------------------------------------------
    # GET /market/*
    # ------------------------------------------------------------------

    def test_get_market_overview(self, client):
        self._svc.get_market_overview.return_value = {
            "freq": "1min", "total": 0, "up_count": 0,
            "down_count": 0, "flat_count": 0,
            "total_vol": None, "total_amount": None, "avg_pct_chg": None,
        }
        resp = client.get("/api/realtime/market/overview")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_market_stats(self, client):
        self._svc.get_market_stats.return_value = {
            "total": 0, "up_count": 0, "down_count": 0,
            "flat_count": 0, "limit_up_count": 0, "limit_down_count": 0,
            "markets": {},
        }
        resp = client.get("/api/realtime/market/stats")
        assert resp.status_code == 200

    # ------------------------------------------------------------------
    # POST /trigger
    # ------------------------------------------------------------------

    def test_trigger_collection(self, client):
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

            resp = client.post("/api/realtime/trigger?freq=1min")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_trigger_collection_failure(self, client):
        with patch("stock_datasource.modules.realtime_minute.collector.get_collector") as mock_get_collector:
            mock_get_collector.side_effect = Exception("Init failed")
            resp = client.post("/api/realtime/trigger")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False

    # ------------------------------------------------------------------
    # POST /refresh-codes
    # ------------------------------------------------------------------

    def test_refresh_codes_success(self, client):
        with patch("stock_datasource.models.database.db_client") as mock_db:
            # A-stock query
            astock_df = pd.DataFrame({"ts_code": ["600519.SH", "600036.SH"]})
            # ETF query
            etf_df = pd.DataFrame({"ts_code": ["510050.SH", "510300.SH"]})
            mock_db.execute_query.side_effect = [astock_df, etf_df]

            resp = client.post("/api/realtime/refresh-codes")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True

    def test_refresh_codes_db_failure(self, client):
        with patch("stock_datasource.models.database.db_client") as mock_db:
            mock_db.execute_query.side_effect = Exception("DB error")
            resp = client.post("/api/realtime/refresh-codes")
            assert resp.status_code == 200
            # Should handle gracefully


# =============================================================================
# Test Data Flow (Collection → Cache → Sync)
# =============================================================================

class TestDataFlow:
    """Test the complete data flow pipeline."""

    def test_collect_store_retrieve_flow(self):
        """Simulate: collect → store_bars → get_bars."""
        with patch("stock_datasource.modules.realtime_minute.collector.settings") as mock_settings, \
             patch("stock_datasource.modules.realtime_minute.collector.ts") as mock_ts:
            mock_settings.TUSHARE_TOKEN = "test_token"
            mock_pro = MagicMock()
            mock_ts.pro_api.return_value = mock_pro

            # Mock rt_min response
            mock_pro.rt_min.return_value = pd.DataFrame({
                "ts_code": ["600519.SH"],
                "trade_time": ["2026-03-01 10:00:00"],
                "open": [1800.0], "close": [1810.0],
                "high": [1820.0], "low": [1790.0],
                "vol": [1000.0], "amount": [18000000.0],
            })

            from stock_datasource.modules.realtime_minute.collector import RealtimeMinuteCollector
            collector = RealtimeMinuteCollector()

            with patch("stock_datasource.modules.realtime_minute.collector.cfg") as mock_cfg:
                mock_cfg.ASTOCK_BATCHES = [["600519.SH"]]
                mock_cfg.MIN_CALL_INTERVAL = 0
                mock_cfg.MAX_RETRIES = 1
                df = collector.collect_astock("1min")

            assert not df.empty
            assert "market_type" in df.columns
            assert df["market_type"].iloc[0] == "a_stock"

    def test_sync_flow(self):
        """Simulate: cache.get_all_bars → sync to ClickHouse."""
        bars = [
            {
                "ts_code": "600519.SH",
                "trade_time": "2026-03-01 10:00:00",
                "open": 1800.0, "close": 1810.0,
                "high": 1820.0, "low": 1790.0,
                "vol": 1000.0, "amount": 18000000.0,
                "market_type": "a_stock", "freq": "1min",
            },
            {
                "ts_code": "510050.SH",
                "trade_time": "2026-03-01 10:00:00",
                "open": 3.0, "close": 3.05,
                "high": 3.08, "low": 2.98,
                "vol": 5000.0, "amount": 15000.0,
                "market_type": "etf", "freq": "1min",
            },
        ]

        with patch("stock_datasource.modules.realtime_minute.sync_service.get_cache_store") as mock_cache, \
             patch("stock_datasource.modules.realtime_minute.sync_service._get_db") as mock_get_db:
            mock_store = MagicMock()
            mock_store.get_all_bars_for_date.return_value = bars
            mock_cache.return_value = mock_store

            mock_db = MagicMock()
            mock_get_db.return_value = mock_db

            from stock_datasource.modules.realtime_minute.sync_service import RealtimeMinuteSyncService
            svc = RealtimeMinuteSyncService()
            svc._ensured = True

            result = svc.sync("20260301")
            assert result["synced"] == 2
            mock_db.insert_dataframe.assert_called_once()

            # Verify DataFrame columns
            call_args = mock_db.insert_dataframe.call_args
            inserted_df = call_args[0][1]
            assert "ts_code" in inserted_df.columns
            assert "freq" in inserted_df.columns
            assert len(inserted_df) == 2


# =============================================================================
# Test Performance (basic checks)
# =============================================================================

class TestPerformance:
    """Basic performance validation tests."""

    def test_large_batch_store(self):
        """Verify store_bars can handle 1000+ rows without error."""
        from stock_datasource.modules.realtime_minute.cache_store import RealtimeMinuteCacheStore
        store = RealtimeMinuteCacheStore()

        n = 1000
        df = pd.DataFrame({
            "ts_code": [f"code{i}.SH" for i in range(n)],
            "trade_time": pd.to_datetime(
                [f"2026-03-01 10:{i // 60:02d}:{i % 60:02d}" for i in range(n)]
            ),
            "open": [100.0 + i * 0.1 for i in range(n)],
            "close": [100.5 + i * 0.1 for i in range(n)],
            "high": [101.0 + i * 0.1 for i in range(n)],
            "low": [99.5 + i * 0.1 for i in range(n)],
            "vol": [1000.0 + i for i in range(n)],
            "amount": [100000.0 + i * 100 for i in range(n)],
            "market_type": ["a_stock"] * n,
            "freq": ["1min"] * n,
        })

        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_pipe.execute.return_value = []
        store._redis = mock_redis

        count = store.store_bars(df)
        assert count == n
        assert mock_pipe.zadd.call_count == n
        assert mock_pipe.set.call_count == n

    def test_ranking_with_many_items(self):
        """Verify ranking handles 500 items correctly."""
        with patch("stock_datasource.modules.realtime_minute.service.get_cache_store") as mock_cache:
            mock_store = MagicMock()
            items = [
                {
                    "ts_code": f"S{i:04d}",
                    "open": 10.0,
                    "close": 10.0 + (i - 250) * 0.01,
                    "vol": float(i * 100),
                    "amount": float(i * 1000),
                }
                for i in range(500)
            ]
            mock_store.get_all_latest.return_value = items
            mock_cache.return_value = mock_store

            from stock_datasource.modules.realtime_minute.service import RealtimeMinuteService
            svc = RealtimeMinuteService()
            svc._cache = mock_store

            result = svc.get_top_gainers(limit=10)
            assert len(result["data"]) == 10
            # Verify sorted descending by pct_chg
            pct_values = [d["pct_chg"] for d in result["data"]]
            assert pct_values == sorted(pct_values, reverse=True)
