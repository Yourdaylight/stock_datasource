"""Redis cache store for realtime minute data.

Uses two Redis data structures per code:
- ZSET (score=epoch): time-series minute bars for range queries.
- HASH (latest): most recent bar snapshot for fast ranking / latest queries.
"""

import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from . import config as cfg

logger = logging.getLogger(__name__)


def _safe_value(v: Any) -> Any:
    """Replace NaN/Inf with None for JSON serialization."""
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


class RealtimeMinuteCacheStore:
    """ZSET + HASH dual-structure Redis cache for minute bars."""

    def __init__(self):
        self._redis = None

    # ------------------------------------------------------------------
    # Redis access
    # ------------------------------------------------------------------

    def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            from redis import Redis
            from stock_datasource.config.settings import settings

            if not settings.REDIS_ENABLED:
                return None

            self._redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            self._redis.ping()
            return self._redis
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
            self._redis = None
            return None

    @property
    def available(self) -> bool:
        return self._get_redis() is not None

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _zset_key(market: str, ts_code: str, freq: str, date: str) -> str:
        return f"{cfg.REDIS_KEY_PREFIX_ZSET}:{market}:{ts_code}:{freq}:{date}"

    @staticmethod
    def _latest_key(market: str, ts_code: str, freq: str) -> str:
        return f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:{ts_code}:{freq}"

    @staticmethod
    def _status_key() -> str:
        return cfg.REDIS_KEY_STATUS

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def store_bars(self, df: pd.DataFrame, ttl: int = cfg.REDIS_DEFAULT_TTL) -> int:
        """Write a DataFrame of minute bars into Redis.

        Each row is added to the ZSET (keyed by date) and the latest
        snapshot HASH is updated if the bar is newer.

        Returns the number of bars written.
        """
        redis = self._get_redis()
        if redis is None or df is None or df.empty:
            return 0

        count = 0
        pipe = redis.pipeline(transaction=False)

        for _, row in df.iterrows():
            ts_code = row.get("ts_code", "")
            market = row.get("market_type", "a_stock")
            freq = row.get("freq", "1min")
            trade_time = row.get("trade_time")

            if not ts_code or trade_time is None:
                continue

            # Determine date string and epoch score
            if isinstance(trade_time, pd.Timestamp):
                dt = trade_time.to_pydatetime()
            elif isinstance(trade_time, datetime):
                dt = trade_time
            else:
                try:
                    dt = pd.to_datetime(trade_time)
                except Exception:
                    continue

            date_str = dt.strftime("%Y%m%d")
            epoch = dt.timestamp()

            bar_dict = {
                "ts_code": ts_code,
                "trade_time": dt.strftime("%Y-%m-%d %H:%M:%S"),
                "open": _safe_value(row.get("open")),
                "close": _safe_value(row.get("close")),
                "high": _safe_value(row.get("high")),
                "low": _safe_value(row.get("low")),
                "vol": _safe_value(row.get("vol")),
                "amount": _safe_value(row.get("amount")),
                "market_type": market,
                "freq": freq,
            }
            bar_json = json.dumps(bar_dict, ensure_ascii=False, default=str)

            # ZSET – add bar
            zset_key = self._zset_key(market, ts_code, freq, date_str)
            pipe.zadd(zset_key, {bar_json: epoch})
            pipe.expire(zset_key, ttl)

            # HASH – latest snapshot
            latest_key = self._latest_key(market, ts_code, freq)
            pipe.set(latest_key, bar_json)
            pipe.expire(latest_key, ttl)

            count += 1

        try:
            pipe.execute()
        except Exception as e:
            logger.error("Redis pipeline execute failed: %s", e)
            return 0

        return count

    def update_status(self, market: str, records: int) -> None:
        """Update collection status in Redis."""
        redis = self._get_redis()
        if redis is None:
            return
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            redis.hset(self._status_key(), market, json.dumps({
                "last_collect_time": now_str,
                "records": records,
            }))
            redis.expire(self._status_key(), cfg.REDIS_DEFAULT_TTL)
        except Exception as e:
            logger.warning("Failed to update status: %s", e)

    # ------------------------------------------------------------------
    # Read
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
        """Query bars from ZSET by time range."""
        redis = self._get_redis()
        if redis is None:
            return []

        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        zset_key = self._zset_key(market, ts_code, freq, date)

        min_score = "-inf"
        max_score = "+inf"
        if start_time:
            try:
                min_score = pd.to_datetime(start_time).timestamp()
            except Exception:
                pass
        if end_time:
            try:
                max_score = pd.to_datetime(end_time).timestamp()
            except Exception:
                pass

        try:
            raw = redis.zrangebyscore(zset_key, min_score, max_score)
            return [json.loads(item) for item in raw]
        except Exception as e:
            logger.warning("Redis zrangebyscore failed: %s", e)
            return []

    def get_latest(self, market: str, ts_code: str, freq: str = "1min") -> Optional[Dict[str, Any]]:
        """Get the latest bar snapshot."""
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            data = redis.get(self._latest_key(market, ts_code, freq))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("Redis get latest failed: %s", e)
        return None

    def get_all_latest(self, market: Optional[str] = None, freq: str = "1min") -> List[Dict[str, Any]]:
        """Scan all latest-snapshot keys, optionally filtered by market."""
        redis = self._get_redis()
        if redis is None:
            return []

        pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:*"
        if market:
            pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:*:{freq}"
        else:
            pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:*:*:{freq}"

        results: List[Dict[str, Any]] = []
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                if keys:
                    values = redis.mget(keys)
                    for v in values:
                        if v:
                            results.append(json.loads(v))
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning("Redis scan failed: %s", e)
        return results

    def get_status(self) -> Dict[str, Any]:
        """Get collection status."""
        redis = self._get_redis()
        if redis is None:
            return {}
        try:
            raw = redis.hgetall(self._status_key())
            return {k: json.loads(v) for k, v in raw.items()}
        except Exception as e:
            logger.warning("Redis get status failed: %s", e)
            return {}

    # ------------------------------------------------------------------
    # Bulk read (for sync)
    # ------------------------------------------------------------------

    def get_all_bars_for_date(
        self,
        date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Read ALL bars for a given date across all markets (for sync to ClickHouse)."""
        redis = self._get_redis()
        if redis is None:
            return []

        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        pattern = f"{cfg.REDIS_KEY_PREFIX_ZSET}:*:*:*:{date}"
        all_bars: List[Dict[str, Any]] = []

        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                for key in keys:
                    raw_items = redis.zrange(key, 0, -1)
                    for item in raw_items:
                        all_bars.append(json.loads(item))
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Redis scan for sync failed: %s", e)

        return all_bars

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_date(self, date: str) -> int:
        """Delete all ZSET keys for a specific date."""
        redis = self._get_redis()
        if redis is None:
            return 0

        pattern = f"{cfg.REDIS_KEY_PREFIX_ZSET}:*:*:*:{date}"
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                if keys:
                    deleted += redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Redis cleanup failed: %s", e)
        return deleted

    def cleanup_latest(self) -> int:
        """Delete all latest-snapshot keys."""
        redis = self._get_redis()
        if redis is None:
            return 0

        pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:*"
        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                if keys:
                    deleted += redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.error("Redis cleanup latest failed: %s", e)
        return deleted

    def get_cached_key_count(self) -> int:
        """Count realtime minute keys in Redis."""
        redis = self._get_redis()
        if redis is None:
            return 0
        count = 0
        try:
            for prefix in (cfg.REDIS_KEY_PREFIX_ZSET, cfg.REDIS_KEY_PREFIX_LATEST):
                cursor = 0
                while True:
                    cursor, keys = redis.scan(cursor, match=f"{prefix}:*", count=500)
                    count += len(keys)
                    if cursor == 0:
                        break
        except Exception:
            pass
        return count


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_cache_store: Optional[RealtimeMinuteCacheStore] = None


def get_cache_store() -> RealtimeMinuteCacheStore:
    global _cache_store
    if _cache_store is None:
        _cache_store = RealtimeMinuteCacheStore()
    return _cache_store
