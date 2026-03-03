"""Redis cache store for realtime daily K-line data.

Implements the dual-channel layout specified in design.md:
- latest  : Redis String per symbol (overwrite, low-latency queries)
- stream  : Redis Stream per market (event log for push & sink workers)

Also manages checkpoints, dead-letter queues, and push state.
"""

import json
import logging
import math
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import config as cfg

logger = logging.getLogger(__name__)


def _safe_value(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


class RealtimeKlineCacheStore:
    """Redis dual-channel store: latest (String) + stream (Stream)."""

    def __init__(self):
        self._redis = None

    # ------------------------------------------------------------------
    # Connection
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
    def latest_key(market: str, ts_code: str) -> str:
        return f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:{ts_code}"

    @staticmethod
    def stream_key(market: str) -> str:
        return f"{cfg.REDIS_KEY_PREFIX_STREAM}:{market}"

    @staticmethod
    def checkpoint_key(prefix: str, market: str) -> str:
        return f"{prefix}:{market}"

    # ------------------------------------------------------------------
    # Latest snapshot (String)
    # ------------------------------------------------------------------
    def set_latest(self, market: str, ts_code: str, data: Dict[str, Any]) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            bar_json = json.dumps(data, ensure_ascii=False, default=str)
            redis.setex(self.latest_key(market, ts_code), cfg.CACHE_LATEST_TTL, bar_json)
            return True
        except Exception as e:
            logger.error("Redis set_latest failed for %s:%s: %s", market, ts_code, e)
            return False

    def get_latest(self, market: str, ts_code: str) -> Optional[Dict[str, Any]]:
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            data = redis.get(self.latest_key(market, ts_code))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("Redis get_latest failed: %s", e)
        return None

    def get_all_latest(self, market: Optional[str] = None) -> List[Dict[str, Any]]:
        redis = self._get_redis()
        if redis is None:
            return []
        pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:*" if market else f"{cfg.REDIS_KEY_PREFIX_LATEST}:*"
        results: List[Dict[str, Any]] = []
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=pattern, count=500)
                if keys:
                    for v in redis.mget(keys):
                        if v:
                            results.append(json.loads(v))
                if cursor == 0:
                    break
        except Exception as e:
            logger.warning("Redis scan failed: %s", e)
        return results

    # ------------------------------------------------------------------
    # Stream (XADD / XREAD / XRANGE)
    # ------------------------------------------------------------------
    def xadd_event(self, market: str, event: Dict[str, str]) -> Optional[str]:
        """Append an event to the market stream. Returns stream entry ID."""
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            stream_key = self.stream_key(market)
            entry_id = redis.xadd(
                stream_key,
                event,
                maxlen=cfg.STREAM_MAXLEN_PER_MARKET,
                approximate=True,
            )
            return entry_id
        except Exception as e:
            logger.error("Redis XADD failed for %s: %s", market, e)
            return None

    def xrange_since(
        self, market: str, min_id: str = "-", max_id: str = "+", count: int = 5000
    ) -> List[Tuple[str, Dict[str, str]]]:
        """Read a range of stream entries."""
        redis = self._get_redis()
        if redis is None:
            return []
        try:
            return redis.xrange(self.stream_key(market), min=min_id, max=max_id, count=count)
        except Exception as e:
            logger.error("Redis XRANGE failed for %s: %s", market, e)
            return []

    def xread_after(
        self, market: str, last_id: str = "0-0", count: int = 5000
    ) -> List[Tuple[str, Dict[str, str]]]:
        """Read new entries after last_id (non-blocking)."""
        redis = self._get_redis()
        if redis is None:
            return []
        try:
            result = redis.xread({self.stream_key(market): last_id}, count=count, block=0)
            if result:
                # result = [(stream_key, [(id, fields), ...])]
                return result[0][1]
            return []
        except Exception as e:
            logger.error("Redis XREAD failed for %s: %s", market, e)
            return []

    def xlen(self, market: str) -> int:
        redis = self._get_redis()
        if redis is None:
            return 0
        try:
            return redis.xlen(self.stream_key(market))
        except Exception:
            return 0

    def xtrim_older_than(self, market: str, ttl_hours: int) -> int:
        """Trim stream entries older than ttl_hours. Returns trimmed count."""
        redis = self._get_redis()
        if redis is None:
            return 0
        try:
            cutoff_ms = int((time.time() - ttl_hours * 3600) * 1000)
            min_id = f"{cutoff_ms}-0"
            stream_key = self.stream_key(market)
            entries = redis.xrange(stream_key, min="-", max=min_id, count=1000)
            if not entries:
                return 0
            ids = [e[0] for e in entries]
            for eid in ids:
                redis.xdel(stream_key, eid)
            return len(ids)
        except Exception as e:
            logger.warning("Redis XTRIM failed for %s: %s", market, e)
            return 0

    # ------------------------------------------------------------------
    # Checkpoint management
    # ------------------------------------------------------------------
    def get_checkpoint(self, prefix: str, market: str) -> str:
        """Get the last-consumed stream ID for a consumer."""
        redis = self._get_redis()
        if redis is None:
            return "0-0"
        try:
            val = redis.get(self.checkpoint_key(prefix, market))
            return val or "0-0"
        except Exception:
            return "0-0"

    def set_checkpoint(self, prefix: str, market: str, stream_id: str) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            redis.set(self.checkpoint_key(prefix, market), stream_id)
            return True
        except Exception as e:
            logger.error("Failed to set checkpoint %s:%s: %s", prefix, market, e)
            return False

    # ------------------------------------------------------------------
    # Push switch (runtime)
    # ------------------------------------------------------------------
    def get_push_switch(self) -> Optional[bool]:
        """Read runtime push switch. Returns None if not set (fall back to env)."""
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            val = redis.get(cfg.REDIS_KEY_SWITCH_PUSH)
            if val is None:
                return None
            return val.lower() in ("true", "1", "on")
        except Exception:
            return None

    def set_push_switch(self, enabled: bool, source: str = "api") -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            old_val = redis.get(cfg.REDIS_KEY_SWITCH_PUSH)
            redis.set(cfg.REDIS_KEY_SWITCH_PUSH, "true" if enabled else "false")
            # Audit log
            redis.xadd(cfg.REDIS_KEY_AUDIT_SWITCH, {
                "timestamp": datetime.now().isoformat(),
                "old_state": str(old_val),
                "new_state": "on" if enabled else "off",
                "source": source,
            }, maxlen=10000, approximate=True)
            return True
        except Exception as e:
            logger.error("Failed to set push switch: %s", e)
            return False

    # ------------------------------------------------------------------
    # Last acked state (for delta computation)
    # ------------------------------------------------------------------
    def get_last_acked_state(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            val = redis.hget(f"{cfg.REDIS_KEY_LAST_ACKED}:{market}", symbol)
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    def set_last_acked_state(self, market: str, symbol: str, state: Dict[str, Any]) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            redis.hset(
                f"{cfg.REDIS_KEY_LAST_ACKED}:{market}",
                symbol,
                json.dumps(state, ensure_ascii=False, default=str),
            )
            return True
        except Exception as e:
            logger.error("Failed to set last_acked_state: %s", e)
            return False

    def clear_last_acked_state(self, market: str) -> int:
        redis = self._get_redis()
        if redis is None:
            return 0
        try:
            return redis.delete(f"{cfg.REDIS_KEY_LAST_ACKED}:{market}")
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------
    def get_circuit_breaker(self, market: str) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            val = redis.get(f"{cfg.REDIS_KEY_CIRCUIT_BREAKER}:{market}")
            return val == "1"
        except Exception:
            return False

    def set_circuit_breaker(self, market: str, active: bool) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            redis.set(f"{cfg.REDIS_KEY_CIRCUIT_BREAKER}:{market}", "1" if active else "0")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Dead-letter queues (push & sink)
    # ------------------------------------------------------------------
    def push_to_dlq(self, dlq_prefix: str, market: str, event: Dict[str, Any]) -> bool:
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            key = f"{dlq_prefix}:{market}"
            payload = json.dumps({
                **event,
                "_dlq_time": datetime.now().isoformat(),
            }, ensure_ascii=False, default=str)
            redis.rpush(key, payload)
            return True
        except Exception as e:
            logger.error("DLQ push failed for %s:%s: %s", dlq_prefix, market, e)
            return False

    def dlq_size(self, dlq_prefix: str, market: str) -> int:
        redis = self._get_redis()
        if redis is None:
            return 0
        try:
            return redis.llen(f"{dlq_prefix}:{market}")
        except Exception:
            return 0

    def dlq_trim_old(self, dlq_prefix: str, market: str, max_age_days: int) -> int:
        """Remove DLQ entries older than max_age_days."""
        redis = self._get_redis()
        if redis is None:
            return 0
        key = f"{dlq_prefix}:{market}"
        removed = 0
        try:
            cutoff = time.time() - max_age_days * 86400
            total = redis.llen(key)
            for _ in range(min(total, 1000)):
                raw = redis.lindex(key, 0)
                if not raw:
                    break
                try:
                    entry = json.loads(raw)
                    dlq_time = entry.get("_dlq_time", "")
                    if dlq_time:
                        ts = datetime.fromisoformat(dlq_time).timestamp()
                        if ts < cutoff:
                            redis.lpop(key)
                            removed += 1
                            continue
                except (json.JSONDecodeError, ValueError):
                    pass
                break  # first non-expired entry → stop
        except Exception as e:
            logger.warning("DLQ trim failed: %s", e)
        return removed

    # ------------------------------------------------------------------
    # Status (lightweight metrics in Redis hash)
    # ------------------------------------------------------------------
    def update_status(self, market: str, records: int) -> None:
        redis = self._get_redis()
        if redis is None:
            return
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            redis.hset(cfg.REDIS_KEY_STATUS, market, json.dumps({
                "last_collect_time": now_str,
                "records": records,
            }))
            redis.expire(cfg.REDIS_KEY_STATUS, 30 * 86400)
        except Exception as e:
            logger.warning("Failed to update status: %s", e)

    def get_status(self) -> Dict[str, Any]:
        redis = self._get_redis()
        if redis is None:
            return {}
        try:
            raw = redis.hgetall(cfg.REDIS_KEY_STATUS)
            result = {}
            for k, v in raw.items():
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            return result
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Batch snapshot write (collector → Redis)
    # ------------------------------------------------------------------
    def store_snapshots(self, market: str, rows: List[Dict[str, Any]]) -> int:
        """Write a batch of snapshots to latest + stream."""
        redis = self._get_redis()
        if redis is None or not rows:
            return 0

        from stock_datasource.config.settings import settings

        pipe = redis.pipeline(transaction=False)
        stream_key = self.stream_key(market)
        count = 0

        for bar in rows:
            ts_code = bar.get("ts_code", "")
            if not ts_code:
                continue

            bar_json = json.dumps(bar, ensure_ascii=False, default=str)

            # 1) latest (String)
            pipe.setex(self.latest_key(market, ts_code), settings.RT_KLINE_LATEST_TTL_SECONDS, bar_json)

            # 2) stream (XADD) — flatten key fields for stream entry
            stream_entry = {
                "ts_code": ts_code,
                "market": market,
                "version": str(bar.get("version", "")),
                "payload": bar_json,
            }
            pipe.xadd(stream_key, stream_entry, maxlen=cfg.STREAM_MAXLEN_PER_MARKET, approximate=True)
            count += 1

        try:
            pipe.execute()
        except Exception as e:
            logger.error("Redis pipeline execute failed: %s", e)
            return 0

        return count

    # ------------------------------------------------------------------
    # Cleanup helpers
    # ------------------------------------------------------------------
    def cleanup_latest(self, market: Optional[str] = None) -> int:
        redis = self._get_redis()
        if redis is None:
            return 0
        pattern = f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:*" if market else f"{cfg.REDIS_KEY_PREFIX_LATEST}:*"
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
        redis = self._get_redis()
        if redis is None:
            return 0
        count = 0
        try:
            cursor = 0
            while True:
                cursor, keys = redis.scan(cursor, match=f"{cfg.REDIS_KEY_PREFIX_LATEST}:*", count=500)
                count += len(keys)
                if cursor == 0:
                    break
        except Exception:
            pass
        return count


_cache_store: Optional[RealtimeKlineCacheStore] = None


def get_cache_store() -> RealtimeKlineCacheStore:
    global _cache_store
    if _cache_store is None:
        _cache_store = RealtimeKlineCacheStore()
    return _cache_store
