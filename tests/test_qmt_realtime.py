"""Tests for QMT realtime market data module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_normalize_realtime_quotes_maps_aliases():
    """Realtime normalizer maps common QMT quote aliases to canonical fields."""
    from stock_datasource.modules.qmt_realtime.normalizer import (
        normalize_realtime_quotes,
    )

    quotes = normalize_realtime_quotes(
        [
            {
                "code": "000001.SZ",
                "market": "a_stock",
                "lastPrice": 10.5,
                "open": 10.0,
                "high": 10.8,
                "low": 9.9,
                "volume": 10000,
                "turnover": 120000.0,
                "time": "2026-01-02 09:31:00",
                "bidPrice1": 10.49,
                "askPrice1": 10.51,
            }
        ]
    )

    assert quotes == [
        {
            "ts_code": "000001.SZ",
            "market": "a_stock",
            "price": 10.5,
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "vol": 10000,
            "amount": 120000.0,
            "quote_time": "2026-01-02 09:31:00",
            "bid_price_1": 10.49,
            "ask_price_1": 10.51,
            "source": "qmt",
        }
    ]


def test_cache_store_round_trips_latest_quote():
    """In-memory cache stores and retrieves latest quote by market and code."""
    from stock_datasource.modules.qmt_realtime.cache_store import QmtRealtimeCacheStore

    cache = QmtRealtimeCacheStore()
    quote = {"ts_code": "000001.SZ", "market": "a_stock", "price": 10.5}

    cache.set_latest(quote)

    assert cache.get_latest("a_stock", "000001.SZ") == quote
    assert cache.get_all_latest("a_stock") == [quote]


def test_collector_fetches_normalizes_and_caches_quotes():
    """Collector uses gateway client output and writes normalized quotes to cache."""
    from stock_datasource.modules.qmt_realtime.cache_store import QmtRealtimeCacheStore
    from stock_datasource.modules.qmt_realtime.collector import QmtRealtimeCollector

    class FakeClient:
        def __init__(self):
            self.calls = []

        def get_realtime_quotes(self, symbols, market=None):
            self.calls.append({"symbols": symbols, "market": market})
            return [{"code": "000001.SZ", "lastPrice": 10.5, "time": "2026-01-02 09:31:00"}]

    cache = QmtRealtimeCacheStore()
    client = FakeClient()
    collector = QmtRealtimeCollector(client=client, cache=cache)

    quotes = collector.collect(["000001.SZ"], market="a_stock")

    assert client.calls == [{"symbols": ["000001.SZ"], "market": "a_stock"}]
    assert quotes[0]["source"] == "qmt"
    assert cache.get_latest("a_stock", "000001.SZ")["price"] == 10.5


def test_sync_service_writes_cached_quotes_to_db():
    """Sync service writes cached realtime quotes to the configured DB client."""
    from stock_datasource.modules.qmt_realtime.cache_store import QmtRealtimeCacheStore
    from stock_datasource.modules.qmt_realtime.sync_service import (
        QmtRealtimeSyncService,
    )

    class FakeDB:
        def __init__(self):
            self.inserts = []

        def insert_dataframe(self, table_name, data, settings=None):
            self.inserts.append((table_name, data.copy(), settings))

    cache = QmtRealtimeCacheStore()
    cache.set_latest(
        {
            "ts_code": "000001.SZ",
            "market": "a_stock",
            "price": 10.5,
            "quote_time": "2026-01-02 09:31:00",
            "source": "qmt",
        }
    )
    db = FakeDB()
    service = QmtRealtimeSyncService(cache=cache, db=db)

    result = service.sync_latest(market="a_stock")

    assert result == {"status": "success", "table": "ods_qmt_realtime_quote", "records": 1}
    assert db.inserts[0][0] == "ods_qmt_realtime_quote"
    assert db.inserts[0][1].iloc[0]["ts_code"] == "000001.SZ"
