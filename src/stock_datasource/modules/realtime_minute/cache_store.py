"""SQLite cache store for realtime minute data.

替代 Redis，使用本地 SQLite 文件作为盘中临时缓存。
- WAL 模式，支持并发读写
- 对外接口与 Redis 版本完全兼容
- 收盘后由 sync_service 批量同步到 ClickHouse，再清理
"""

import json
import logging
import math
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config as cfg

logger = logging.getLogger(__name__)

# SQLite 文件路径（可通过环境变量覆盖）
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "rt_minute_cache.db"
)
SQLITE_DB_PATH = os.environ.get("RT_MINUTE_SQLITE_PATH", _DEFAULT_DB_PATH)

# DDL
_DDL_BARS = """
CREATE TABLE IF NOT EXISTS rt_minute_bars (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code     TEXT    NOT NULL,
    market_type TEXT    NOT NULL,
    freq        TEXT    NOT NULL,
    trade_date  TEXT    NOT NULL,   -- YYYYMMDD
    trade_time  TEXT    NOT NULL,   -- YYYY-MM-DD HH:MM:SS
    epoch       REAL    NOT NULL,   -- unix timestamp，用于范围查询
    open        REAL,
    close       REAL,
    high        REAL,
    low         REAL,
    vol         REAL,
    amount      REAL,
    UNIQUE (ts_code, freq, trade_time)  -- 幂等，重复写自动覆盖
);
"""

_DDL_LATEST = """
CREATE TABLE IF NOT EXISTS rt_minute_latest (
    ts_code     TEXT NOT NULL,
    market_type TEXT NOT NULL,
    freq        TEXT NOT NULL,
    trade_time  TEXT NOT NULL,
    epoch       REAL NOT NULL,
    open        REAL,
    close       REAL,
    high        REAL,
    low         REAL,
    vol         REAL,
    amount      REAL,
    PRIMARY KEY (ts_code, freq)
);
"""

_DDL_STATUS = """
CREATE TABLE IF NOT EXISTS rt_minute_status (
    market          TEXT PRIMARY KEY,
    last_collect_time TEXT,
    records         INTEGER
);
"""

_DDL_IDX = """
CREATE INDEX IF NOT EXISTS idx_bars_code_freq_date
    ON rt_minute_bars (ts_code, freq, trade_date);
CREATE INDEX IF NOT EXISTS idx_bars_epoch
    ON rt_minute_bars (epoch);
"""


def _safe_value(v: Any) -> Any:
    """Replace NaN/Inf with None for storage."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


class RealtimeMinuteCacheStore:
    """SQLite-backed cache store for minute bars，接口与 Redis 版本完全兼容。"""

    def __init__(self, db_path: str = SQLITE_DB_PATH):
        self._db_path = db_path
        self._local = threading.local()  # 每个线程独立连接
        self._init_db()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的 SQLite 连接（懒初始化）。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-32000")  # 32MB
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def _tx(self):
        """简单事务上下文管理器。"""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_db(self):
        """建表 + 建索引（幂等）。"""
        try:
            with self._tx() as conn:
                conn.executescript(_DDL_BARS + _DDL_LATEST + _DDL_STATUS + _DDL_IDX)
            logger.info("SQLite cache store initialized: %s", self._db_path)
        except Exception as e:
            logger.error("SQLite init failed: %s", e)

    @property
    def available(self) -> bool:
        """SQLite 始终可用（文件存在即可）。"""
        try:
            self._get_conn()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def store_bars(self, df: pd.DataFrame, ttl: int = cfg.REDIS_DEFAULT_TTL) -> int:
        """将 DataFrame 的分钟 bar 写入 SQLite。

        ttl 参数保留以兼容接口，SQLite 版本不使用（由 cleanup_date 手动清理）。
        返回写入条数。使用向量化操作替代逐行 iterrows，支持大数据量写入。
        """
        if df is None or df.empty:
            return 0

        # --- 向量化预处理 ---
        work = df.copy()

        # 过滤无效行
        work = work.dropna(subset=["ts_code"])
        if "trade_time" not in work.columns:
            return 0

        # Parse trade_time vectorized
        work["trade_time"] = pd.to_datetime(work["trade_time"], errors="coerce")
        work = work.dropna(subset=["trade_time"])
        if work.empty:
            return 0

        # Normalize freq to lowercase
        if "freq" in work.columns:
            work["freq"] = work["freq"].astype(str).str.lower()
        else:
            work["freq"] = "1min"

        # Fill missing market_type
        if "market_type" not in work.columns:
            work["market_type"] = "a_stock"

        # Compute derived columns vectorized
        work["trade_date"] = work["trade_time"].dt.strftime("%Y%m%d")
        work["time_str"] = work["trade_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        work["epoch"] = work["trade_time"].astype(int) / 1e9  # nanoseconds -> seconds

        # Replace NaN/Inf in numeric columns
        for col in ("open", "close", "high", "low", "vol", "amount"):
            if col in work.columns:
                work[col] = work[col].apply(_safe_value)
            else:
                work[col] = None

        # Build bar tuples for rt_minute_bars
        bar_cols = ["ts_code", "market_type", "freq", "trade_date", "time_str", "epoch",
                     "open", "close", "high", "low", "vol", "amount"]
        for c in bar_cols:
            if c not in work.columns:
                work[c] = None
        rows = list(work[bar_cols].itertuples(index=False, name=None))

        if not rows:
            return 0

        # Build latest tuples (same as bar but without trade_date)
        latest_cols = ["ts_code", "market_type", "freq", "time_str", "epoch",
                       "open", "close", "high", "low", "vol", "amount"]
        latest_rows = list(work[latest_cols].itertuples(index=False, name=None))

        try:
            with self._tx() as conn:
                # 幂等写入 bars（UNIQUE 冲突时覆盖）
                conn.executemany(
                    """INSERT INTO rt_minute_bars
                       (ts_code, market_type, freq, trade_date, trade_time, epoch,
                        open, close, high, low, vol, amount)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(ts_code, freq, trade_time) DO UPDATE SET
                           open=excluded.open, close=excluded.close,
                           high=excluded.high, low=excluded.low,
                           vol=excluded.vol, amount=excluded.amount,
                           epoch=excluded.epoch""",
                    rows,
                )
                # 更新 latest（只保留最新一条）
                conn.executemany(
                    """INSERT INTO rt_minute_latest
                       (ts_code, market_type, freq, trade_time, epoch,
                        open, close, high, low, vol, amount)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(ts_code, freq) DO UPDATE SET
                           trade_time=excluded.trade_time,
                           epoch=excluded.epoch,
                           market_type=excluded.market_type,
                           open=excluded.open, close=excluded.close,
                           high=excluded.high, low=excluded.low,
                           vol=excluded.vol, amount=excluded.amount
                       WHERE excluded.epoch >= rt_minute_latest.epoch""",
                    latest_rows,
                )
        except Exception as e:
            logger.error("SQLite store_bars failed: %s", e)
            return 0

        return len(rows)

    def update_status(self, market: str, records: int) -> None:
        """更新采集状态。"""
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self._tx() as conn:
                conn.execute(
                    """INSERT INTO rt_minute_status (market, last_collect_time, records)
                       VALUES (?, ?, ?)
                       ON CONFLICT(market) DO UPDATE SET
                           last_collect_time=excluded.last_collect_time,
                           records=excluded.records""",
                    (market, now_str, records),
                )
        except Exception as e:
            logger.warning("Failed to update status: %s", e)

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def get_bars(
        self,
        market: str,
        ts_code: str,
        freq: str = "1min",
        date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按时间范围查询分钟 bar。"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        params: List[Any] = [ts_code, freq, date]
        sql = """SELECT ts_code, market_type, freq, trade_time,
                        open, close, high, low, vol, amount
                 FROM rt_minute_bars
                 WHERE ts_code=? AND freq=? AND trade_date=?"""

        if start_time:
            try:
                min_epoch = pd.to_datetime(start_time).timestamp()
                sql += " AND epoch >= ?"
                params.append(min_epoch)
            except Exception:
                pass
        if end_time:
            try:
                max_epoch = pd.to_datetime(end_time).timestamp()
                sql += " AND epoch <= ?"
                params.append(max_epoch)
            except Exception:
                pass

        sql += " ORDER BY epoch ASC"

        try:
            conn = self._get_conn()
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("SQLite get_bars failed: %s", e)
            return []

    def get_latest(self, market: str, ts_code: str, freq: str = "1min") -> Optional[Dict[str, Any]]:
        """获取最新一条 bar 快照。"""
        try:
            conn = self._get_conn()
            row = conn.execute(
                """SELECT ts_code, market_type, freq, trade_time,
                          open, close, high, low, vol, amount
                   FROM rt_minute_latest
                   WHERE ts_code=? AND freq=?""",
                (ts_code, freq),
            ).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.warning("SQLite get_latest failed: %s", e)
            return None

    def get_all_latest(self, market: Optional[str] = None, freq: str = "1min") -> List[Dict[str, Any]]:
        """获取所有（或指定市场的）最新快照。"""
        try:
            conn = self._get_conn()
            if market:
                rows = conn.execute(
                    """SELECT ts_code, market_type, freq, trade_time,
                              open, close, high, low, vol, amount
                       FROM rt_minute_latest
                       WHERE market_type=? AND freq=?""",
                    (market, freq),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT ts_code, market_type, freq, trade_time,
                              open, close, high, low, vol, amount
                       FROM rt_minute_latest
                       WHERE freq=?""",
                    (freq,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning("SQLite get_all_latest failed: %s", e)
            return []

    def get_status(self) -> Dict[str, Any]:
        """获取采集状态。"""
        try:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT market, last_collect_time, records FROM rt_minute_status"
            ).fetchall()
            return {
                r["market"]: {
                    "last_collect_time": r["last_collect_time"],
                    "records": r["records"],
                }
                for r in rows
            }
        except Exception as e:
            logger.warning("SQLite get_status failed: %s", e)
            return {}

    # ------------------------------------------------------------------
    # 批量读取（供 sync_service 使用）
    # ------------------------------------------------------------------

    def get_all_bars_for_date(
        self,
        date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """读取指定日期的全部 bar（用于同步到 ClickHouse）。"""
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        try:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT ts_code, market_type, freq, trade_time,
                          open, close, high, low, vol, amount
                   FROM rt_minute_bars
                   WHERE trade_date=?
                   ORDER BY ts_code, freq, epoch""",
                (date,),
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("SQLite get_all_bars_for_date failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def cleanup_date(self, date: str) -> int:
        """删除指定日期的所有 bar 数据。"""
        try:
            with self._tx() as conn:
                cur = conn.execute(
                    "DELETE FROM rt_minute_bars WHERE trade_date=?", (date,)
                )
                return cur.rowcount
        except Exception as e:
            logger.error("SQLite cleanup_date failed: %s", e)
            return 0

    def cleanup_latest(self) -> int:
        """清空最新快照表。"""
        try:
            with self._tx() as conn:
                cur = conn.execute("DELETE FROM rt_minute_latest")
                return cur.rowcount
        except Exception as e:
            logger.error("SQLite cleanup_latest failed: %s", e)
            return 0

    def get_cached_key_count(self) -> int:
        """返回缓存中的 bar 总条数（兼容接口）。"""
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT COUNT(*) FROM rt_minute_bars").fetchone()
            return row[0] if row else 0
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache_store: Optional[RealtimeMinuteCacheStore] = None


def get_cache_store() -> RealtimeMinuteCacheStore:
    global _cache_store
    if _cache_store is None:
        _cache_store = RealtimeMinuteCacheStore()
    return _cache_store
