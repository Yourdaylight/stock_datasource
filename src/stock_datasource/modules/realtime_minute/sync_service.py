"""Sync service: flush Redis minute data to ClickHouse after market close.

Handles per-market ClickHouse table creation and data synchronization.
Tables are named ``ods_min_kline_{market}`` and created lazily on first sync.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config as cfg
from .cache_store import get_cache_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ClickHouse table DDL (per-market, no market_type column needed)
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {db}.{table} (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    freq         LowCardinality(String)  COMMENT '分钟频度(1min/5min/15min/30min/60min)',
    trade_time   DateTime                COMMENT '交易时间',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    version      UInt32 DEFAULT toUInt32(toUnixTimestamp(now())) COMMENT '版本号(幂等)',
    _ingested_at DateTime DEFAULT now()  COMMENT '入库时间'
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_time)
ORDER BY (ts_code, freq, trade_time)
COMMENT '{comment}'
"""


def _get_db():
    from stock_datasource.models.database import db_client
    return db_client


class RealtimeMinuteSyncService:
    """Sync cached minute bars from Redis → ClickHouse (per-market tables)."""

    def __init__(self):
        self._ensured_tables: set = set()

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def _table_comment(self, market: str) -> str:
        comments = {
            "a_stock": "A股分钟K线行情数据",
            "etf": "ETF分钟K线行情数据",
            "index": "指数分钟K线行情数据",
            "hk": "港股分钟K线行情数据",
        }
        return comments.get(market, "分钟K线行情数据")

    def ensure_table(self, market: Optional[str] = None) -> None:
        """Create table(s) if they do not exist.

        If *market* is ``None``, ensure all market tables.
        """
        markets = [market] if market else list(cfg.CLICKHOUSE_TABLES.keys())
        for m in markets:
            table = cfg.get_table_for_market(m)
            if table in self._ensured_tables:
                continue
            try:
                db = _get_db()
                from stock_datasource.config.settings import settings
                database = settings.CLICKHOUSE_DATABASE
                sql = _CREATE_TABLE_SQL.format(
                    db=database, table=table, comment=self._table_comment(m)
                )
                db.execute(sql)
                self._ensured_tables.add(table)
                logger.info("ClickHouse table %s ensured (market=%s)", table, m)
            except Exception as e:
                logger.error("Failed to ensure table %s: %s", table, e)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Read today's data from Redis and write to ClickHouse per-market tables.

        Returns a summary dict.
        """
        self.ensure_table()

        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        cache = get_cache_store()
        bars = cache.get_all_bars_for_date(date)

        if not bars:
            logger.info("No bars found in Redis for %s, nothing to sync", date)
            return {"date": date, "synced": 0}

        # Convert to DataFrame
        df = pd.DataFrame(bars)

        # Ensure types
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
        for col in ("open", "close", "high", "low", "vol", "amount"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Ensure market_type and freq present
        if "market_type" not in df.columns:
            df["market_type"] = "a_stock"
        if "freq" not in df.columns:
            df["freq"] = "1min"

        # Drop rows without ts_code or trade_time
        df = df.dropna(subset=["ts_code", "trade_time"])

        if df.empty:
            logger.info("No valid bars to sync for %s", date)
            return {"date": date, "synced": 0}

        # Write to ClickHouse grouped by market
        total_synced = 0
        per_market: Dict[str, int] = {}
        db_cols = ["ts_code", "freq", "trade_time",
                   "open", "close", "high", "low", "vol", "amount"]

        for market, group_df in df.groupby("market_type"):
            table = cfg.get_table_for_market(str(market))
            # Ensure columns
            write_df = group_df.copy()
            for c in db_cols:
                if c not in write_df.columns:
                    write_df[c] = None
            write_df = write_df[db_cols]

            try:
                db = _get_db()
                db.insert_dataframe(table, write_df)
                count = len(write_df)
                total_synced += count
                per_market[str(market)] = count
                logger.info("Synced %d bars to %s for %s", count, table, date)
            except Exception as e:
                logger.error("ClickHouse insert to %s failed: %s", table, e)
                per_market[str(market)] = 0

        return {"date": date, "synced": total_synced, "per_market": per_market}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self, date: Optional[str] = None) -> Dict[str, int]:
        """Remove synced Redis data for a given date."""
        cache = get_cache_store()
        if date is None:
            date = datetime.now().strftime("%Y%m%d")
        deleted = cache.cleanup_date(date)
        latest_deleted = cache.cleanup_latest()
        logger.info("Cleanup for %s: %d zset keys, %d latest keys", date, deleted, latest_deleted)
        return {"zset_deleted": deleted, "latest_deleted": latest_deleted}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_sync_service: Optional[RealtimeMinuteSyncService] = None


def get_sync_service() -> RealtimeMinuteSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = RealtimeMinuteSyncService()
    return _sync_service
