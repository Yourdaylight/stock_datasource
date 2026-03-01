"""Minute sink: Redis Stream → ClickHouse every 60 seconds.

Implements design.md §ClickHouse Minute Sync:
- Read [checkpoint, now) from per-market stream
- Batch write per market in parallel
- Full-window checkpoint commit (all markets OK) OR
  single-market isolation (>3 retries → DLQ)
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config as cfg
from .cache import get_cache_store
from . import metrics as m

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DDL templates — design.md §ClickHouse 表 DDL
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {db}.{table} (
    ts_code      LowCardinality(String)  COMMENT '证券代码',
    trade_date   Date                    COMMENT '交易日期',
    trade_time   String DEFAULT ''       COMMENT '交易时间',
    name         String DEFAULT ''       COMMENT '证券名称',
    open         Nullable(Float64)       COMMENT '开盘价',
    close        Nullable(Float64)       COMMENT '收盘价/最新价',
    high         Nullable(Float64)       COMMENT '最高价',
    low          Nullable(Float64)       COMMENT '最低价',
    pre_close    Nullable(Float64)       COMMENT '昨收价',
    vol          Nullable(Float64)       COMMENT '成交量',
    amount       Nullable(Float64)       COMMENT '成交额',
    pct_chg      Nullable(Float32)       COMMENT '涨跌幅(%)',
    bid          Nullable(Float64)       COMMENT '买一价(港股)',
    ask          Nullable(Float64)       COMMENT '卖一价(港股)',
    collected_at DateTime                COMMENT '采集时间',
    version      Int64                   COMMENT '版本号(毫秒)',
    INDEX idx_ts_code ts_code TYPE bloom_filter GRANULARITY 4
)
ENGINE = ReplacingMergeTree(version)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (ts_code, trade_date, trade_time, version)
COMMENT '{comment}'
"""


def _get_db():
    from stock_datasource.models.database import db_client
    return db_client


class MinuteSinkWorker:
    """Every 60s: read stream checkpoint → batch write ClickHouse → commit."""

    def __init__(self):
        self._cache = get_cache_store()
        self._markets = list(cfg.CLICKHOUSE_TABLES.keys())
        self._ensured_tables: set = set()
        self._market_fail_count: Dict[str, int] = {mkt: 0 for mkt in self._markets}

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------
    def ensure_tables(self) -> bool:
        """Verify all target tables exist. Returns True if all OK."""
        from stock_datasource.config.settings import settings
        db = _get_db()
        all_ok = True
        for market, table in cfg.CLICKHOUSE_TABLES.items():
            if table in self._ensured_tables:
                continue
            try:
                sql = _CREATE_TABLE_SQL.format(
                    db=settings.CLICKHOUSE_DATABASE,
                    table=table,
                    comment=f"{market} 实时日线 tick 数据",
                )
                db.execute(sql)
                self._ensured_tables.add(table)
                logger.info("ClickHouse table %s ensured", table)
            except Exception as e:
                logger.error("Table check failed for %s: %s", table, e)
                all_ok = False
        return all_ok

    # ------------------------------------------------------------------
    # Main tick — called every 60s
    # ------------------------------------------------------------------
    def tick(self) -> Dict[str, Any]:
        self.ensure_tables()

        from stock_datasource.config.settings import settings
        results: Dict[str, Any] = {}
        all_ok = True

        for market in self._markets:
            try:
                ok, count = self._sync_market(market)
                results[market] = {"ok": ok, "records": count}
                if not ok:
                    all_ok = False
            except Exception as e:
                logger.error("Sink tick error for %s: %s", market, e, exc_info=True)
                results[market] = {"ok": False, "records": 0, "error": str(e)}
                all_ok = False

        # Report backlog depths
        for market in self._markets:
            depth = self._cache.xlen(market)
            m.sink_backlog(market, depth)
            m.sink_dlq_size(market, self._cache.dlq_size(cfg.REDIS_KEY_DLQ_SINK, market))

        return {"all_ok": all_ok, "markets": results}

    # ------------------------------------------------------------------
    # Per-market sync
    # ------------------------------------------------------------------
    def _sync_market(self, market: str) -> tuple:
        """Sync one market. Returns (success, record_count)."""
        from stock_datasource.config.settings import settings

        ckpt_key = cfg.REDIS_KEY_CKPT_CH
        last_id = self._cache.get_checkpoint(ckpt_key, market)

        batch_size = max(1000, int(settings.RT_KLINE_SINK_BATCH_SIZE))
        max_batches = max(1, int(settings.RT_KLINE_SINK_MAX_BATCHES_PER_TICK))
        table = cfg.get_table_for_market(market)
        retry_limit = settings.RT_KLINE_SINK_MARKET_RETRY_LIMIT

        total_synced = 0
        current_id = last_id

        for batch_idx in range(max_batches):
            # Read new entries since checkpoint
            entries = self._cache.xread_after(market, last_id=current_id, count=batch_size)
            if not entries:
                break

            # Parse entries into rows
            rows: List[Dict[str, Any]] = []
            max_id = current_id
            for entry_id, fields in entries:
                try:
                    payload = json.loads(fields.get("payload", "{}"))
                    rows.append(payload)
                except json.JSONDecodeError:
                    continue
                max_id = entry_id

            if not rows:
                self._cache.set_checkpoint(ckpt_key, market, max_id)
                current_id = max_id
                continue

            # Build DataFrame
            df = pd.DataFrame(rows)
            df = self._prepare_dataframe(df, market)

            if df.empty:
                self._cache.set_checkpoint(ckpt_key, market, max_id)
                current_id = max_id
                continue

            # Write to ClickHouse with retry
            for attempt in range(retry_limit):
                t0 = time.monotonic()
                try:
                    db = _get_db()
                    db.insert_dataframe(table, df)
                    latency_ms = (time.monotonic() - t0) * 1000
                    count = len(df)

                    m.sink_batch(market, True, count, latency_ms)
                    self._market_fail_count[market] = 0

                    # Commit checkpoint for this batch
                    self._cache.set_checkpoint(ckpt_key, market, max_id)
                    current_id = max_id
                    total_synced += count
                    logger.info(
                        "Synced %d records to %s (market=%s, batch=%d/%d)",
                        count,
                        table,
                        market,
                        batch_idx + 1,
                        max_batches,
                    )
                    break

                except Exception as e:
                    latency_ms = (time.monotonic() - t0) * 1000
                    m.sink_batch(market, False, 0, latency_ms)
                    m.sink_market_failure(market)
                    logger.warning(
                        "ClickHouse insert to %s failed (attempt %d/%d): %s",
                        table, attempt + 1, retry_limit, e,
                    )
                    time.sleep(min(2 ** attempt, 8))
            else:
                # All retries exhausted — isolate this market batch
                self._market_fail_count[market] = self._market_fail_count.get(market, 0) + 1
                logger.error(
                    "Market %s sink failed after %d retries, sending to DLQ (fail_count=%d)",
                    market, retry_limit, self._market_fail_count[market],
                )
                for _, row in df.iterrows():
                    self._cache.push_to_dlq(cfg.REDIS_KEY_DLQ_SINK, market, row.to_dict())
                return (False, total_synced)

        return (True, total_synced)

    # ------------------------------------------------------------------
    # DataFrame preparation
    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame, market: str) -> pd.DataFrame:
        """Normalize types and select columns for ClickHouse insert."""
        if df.empty:
            return df

        columns = [
            "ts_code", "trade_date", "trade_time", "name",
            "open", "close", "high", "low", "pre_close",
            "vol", "amount", "pct_chg",
            "bid", "ask",
            "collected_at", "version",
        ]

        for col in columns:
            if col not in df.columns:
                df[col] = None

        # Type coercions
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d", errors="coerce")
        for col in ("open", "close", "high", "low", "pre_close", "vol", "amount", "pct_chg", "bid", "ask"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "collected_at" in df.columns:
            df["collected_at"] = pd.to_datetime(df["collected_at"], errors="coerce")
        else:
            df["collected_at"] = datetime.now()
        if "version" in df.columns:
            df["version"] = pd.to_numeric(df["version"], errors="coerce").fillna(
                int(datetime.now().timestamp() * 1000)
            ).astype("int64")
        else:
            df["version"] = int(datetime.now().timestamp() * 1000)

        df["name"] = df["name"].fillna("")
        df["trade_time"] = df["trade_time"].fillna("")

        # Drop rows without ts_code
        df = df.dropna(subset=["ts_code"])

        return df[columns] if not df.empty else df

    # ------------------------------------------------------------------
    # Stream cleanup
    # ------------------------------------------------------------------
    def cleanup_streams(self) -> Dict[str, int]:
        """Trim stream entries older than configured TTL."""
        from stock_datasource.config.settings import settings
        result = {}
        for market in self._markets:
            trimmed = self._cache.xtrim_older_than(market, settings.RT_KLINE_STREAM_TTL_HOURS)
            result[market] = trimmed
        return result

    # ------------------------------------------------------------------
    # Cleanup latest keys
    # ------------------------------------------------------------------
    def cleanup_latest(self) -> int:
        return self._cache.cleanup_latest()

    # ------------------------------------------------------------------
    # Clear last_acked_state (called at start of new trading day)
    # ------------------------------------------------------------------
    def clear_push_state(self) -> Dict[str, int]:
        result = {}
        for market in self._markets:
            result[market] = self._cache.clear_last_acked_state(market)
        return result


_sink_worker: Optional[MinuteSinkWorker] = None


def get_sink_worker() -> MinuteSinkWorker:
    global _sink_worker
    if _sink_worker is None:
        _sink_worker = MinuteSinkWorker()
    return _sink_worker
