"""Cloud push worker for realtime kline delta streaming.

Implements the sliding-window push model from design.md:
- Triggers every 2s, reads 10s sliding window [now-10s, now)
- Computes delta vs last_acked_state per symbol
- Pushes v1 payload to cloud endpoint
- Handles ACK/retry/dead-letter/circuit-breaker
"""

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config as cfg
from .cache import get_cache_store, RealtimeKlineCacheStore
from . import metrics as m

logger = logging.getLogger(__name__)


def _is_push_enabled() -> bool:
    """Check push switch: runtime Redis > env default."""
    from stock_datasource.config.settings import settings
    cache = get_cache_store()
    runtime = cache.get_push_switch()
    if runtime is not None:
        return runtime
    return settings.RT_KLINE_CLOUD_PUSH_ENABLED


class CloudPushWorker:
    """Sliding-window delta push worker (hidden feature, default off)."""

    def __init__(self):
        from stock_datasource.config.settings import settings
        self._settings = settings
        self._cache: RealtimeKlineCacheStore = get_cache_store()
        self._markets = list(cfg.CLICKHOUSE_TABLES.keys())

        # Per-market in-memory backlog (circuit-breaker overflow)
        self._backlog: Dict[str, deque] = {
            mkt: deque(maxlen=settings.RT_KLINE_PUSH_MAX_BACKLOG)
            for mkt in self._markets
        }

        # Per-market continuous-failure tracking
        self._failure_start: Dict[str, Optional[float]] = {mkt: None for mkt in self._markets}

        # Auth token (refreshable)
        self._token: str = settings.RT_KLINE_CLOUD_PUSH_TOKEN
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Main tick — called every 2s by scheduler
    # ------------------------------------------------------------------
    def tick(self) -> None:
        if not _is_push_enabled():
            return

        for market in self._markets:
            try:
                self._process_market(market)
            except Exception as e:
                logger.error("Push tick error for %s: %s", market, e, exc_info=True)

    # ------------------------------------------------------------------
    # Per-market processing
    # ------------------------------------------------------------------
    def _process_market(self, market: str) -> None:
        # Check circuit breaker
        if self._cache.get_circuit_breaker(market):
            # Try recovery probe
            if not self._try_recovery_probe(market):
                return

        # 1) Read 10s sliding window from stream
        window_events = self._read_window(market)
        if not window_events:
            # Still drain backlog if any
            self._drain_backlog(market)
            return

        # 2) Compute deltas
        deltas = self._compute_deltas(market, window_events)
        if not deltas:
            self._drain_backlog(market)
            return

        # 3) Push deltas
        for payload in deltas:
            ok = self._push_one(market, payload)
            if not ok:
                break  # stop on first failure for this market

    # ------------------------------------------------------------------
    # Read sliding window
    # ------------------------------------------------------------------
    def _read_window(self, market: str) -> Dict[str, Dict[str, Any]]:
        """Read events from the last 10s window, return latest per symbol."""
        now_ms = int(time.time() * 1000)
        window_start_ms = now_ms - int(self._settings.RT_KLINE_CLOUD_PUSH_WINDOW * 1000)
        min_id = f"{window_start_ms}-0"

        entries = self._cache.xrange_since(market, min_id=min_id, max_id="+", count=10000)
        # Deduplicate: keep last entry per symbol
        latest_per_symbol: Dict[str, Dict[str, Any]] = {}
        for entry_id, fields in entries:
            ts_code = fields.get("ts_code", "")
            if not ts_code:
                continue
            try:
                payload = json.loads(fields.get("payload", "{}"))
            except json.JSONDecodeError:
                continue
            payload["_stream_id"] = entry_id
            latest_per_symbol[ts_code] = payload

        return latest_per_symbol

    # ------------------------------------------------------------------
    # Compute delta vs last_acked_state
    # ------------------------------------------------------------------
    def _compute_deltas(
        self, market: str, window: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []

        for symbol, current in window.items():
            last_state = self._cache.get_last_acked_state(market, symbol)
            delta_fields: Dict[str, Any] = {}

            for field in cfg.SNAPSHOT_CORE_FIELDS:
                cur_val = current.get(field)
                old_val = last_state.get(field) if last_state else None
                if cur_val != old_val and cur_val is not None:
                    delta_fields[field] = cur_val

            if not delta_fields:
                continue

            event_id = current.get("_stream_id", f"{int(time.time()*1000)}-0")
            payloads.append({
                "schema_version": "v1",
                "event_id": event_id,
                "event_time": datetime.now(timezone.utc).isoformat(),
                "market": market,
                "source_api": current.get("source_api", cfg.MARKET_API_MAP.get(market, "")),
                "symbol": symbol,
                "version": current.get("version", int(time.time() * 1000)),
                "delta": delta_fields,
                "full_ref": {
                    "redis_latest_key": f"{cfg.REDIS_KEY_PREFIX_LATEST}:{market}:{symbol}",
                },
            })

        return payloads

    # ------------------------------------------------------------------
    # Push one payload
    # ------------------------------------------------------------------
    def _push_one(self, market: str, payload: Dict[str, Any]) -> bool:
        url = self._settings.RT_KLINE_CLOUD_PUSH_URL
        if not url:
            logger.debug("No push URL configured, skipping")
            return True

        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        t0 = time.monotonic()
        try:
            resp = self._session.post(url, json=payload, headers=headers, timeout=5)
            latency_ms = (time.monotonic() - t0) * 1000
            m.push_latency(market, latency_ms)

            if resp.status_code == 200:
                return self._handle_ack(market, payload, resp.json())
            elif resp.status_code == 401:
                # Token expired — try refresh once
                if self._refresh_token():
                    headers["Authorization"] = f"Bearer {self._token}"
                    resp = self._session.post(url, json=payload, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        return self._handle_ack(market, payload, resp.json())
                return self._handle_non_retryable(market, payload, resp.status_code)
            elif resp.status_code in (429, 503):
                return self._handle_retryable(market, payload, resp)
            elif resp.status_code >= 500:
                return self._handle_retryable(market, payload, resp)
            else:
                return self._handle_non_retryable(market, payload, resp.status_code)

        except requests.exceptions.Timeout:
            m.push_event(market, "timeout")
            m.push_retry(market)
            self._record_failure(market)
            return False
        except requests.exceptions.ConnectionError:
            m.push_event(market, "connection_error")
            m.push_retry(market)
            self._record_failure(market)
            return False
        except Exception as e:
            logger.error("Push error for %s: %s", market, e)
            m.push_event(market, "error")
            self._record_failure(market)
            return False

    def _handle_ack(self, market: str, payload: Dict[str, Any], ack: Dict[str, Any]) -> bool:
        status = ack.get("status", "")
        code = ack.get("code", -1)

        if status == "ok" and code == 0:
            # Success — update last_acked_state
            symbol = payload["symbol"]
            delta = payload.get("delta", {})
            last_state = self._cache.get_last_acked_state(market, symbol) or {}
            last_state.update(delta)
            self._cache.set_last_acked_state(market, symbol, last_state)

            m.push_event(market, "ok")
            m.push_ack_lag(market, 0)
            self._clear_failure(market)
            return True

        elif status == "retryable":
            m.push_event(market, "retryable")
            m.push_retry(market)
            self._record_failure(market)
            return False

        else:
            return self._handle_non_retryable(market, payload, code)

    def _handle_retryable(self, market: str, payload: Dict[str, Any], resp: Any) -> bool:
        m.push_event(market, "retryable")
        m.push_retry(market)
        # Add to memory backlog for priority retry in next tick
        self._backlog[market].append(payload)
        self._record_failure(market)
        return False

    def _handle_non_retryable(self, market: str, payload: Dict[str, Any], status_code: int) -> bool:
        m.push_event(market, "failed")
        self._cache.push_to_dlq(cfg.REDIS_KEY_DLQ_PUSH, market, {
            "payload": payload,
            "status_code": status_code,
        })
        m.push_dlq_size(market, self._cache.dlq_size(cfg.REDIS_KEY_DLQ_PUSH, market))
        
        # Mark as acked even if failed (to avoid repeat DLQ entries for same version)
        symbol = payload["symbol"]
        delta = payload.get("delta", {})
        last_state = self._cache.get_last_acked_state(market, symbol) or {}
        last_state.update(delta)
        self._cache.set_last_acked_state(market, symbol, last_state)

        self._record_failure(market)
        logger.warning("Non-retryable push failure for %s (status=%s), sent to DLQ", market, status_code)
        return False

    # ------------------------------------------------------------------
    # Failure tracking & circuit breaker
    # ------------------------------------------------------------------
    def _record_failure(self, market: str) -> None:
        if self._failure_start[market] is None:
            self._failure_start[market] = time.time()
        duration_min = (time.time() - self._failure_start[market]) / 60
        if duration_min >= self._settings.RT_KLINE_PUSH_CIRCUIT_BREAKER_MINUTES:
            self._cache.set_circuit_breaker(market, True)
            m.push_circuit_breaker(market, True)
            logger.error("Circuit breaker activated for %s after %.0f min", market, duration_min)

    def _clear_failure(self, market: str) -> None:
        self._failure_start[market] = None
        if self._cache.get_circuit_breaker(market):
            self._cache.set_circuit_breaker(market, False)
            m.push_circuit_breaker(market, False)
            logger.info("Circuit breaker cleared for %s", market)

    def _try_recovery_probe(self, market: str) -> bool:
        """When circuit breaker is active, periodically probe."""
        # Simple: try one dummy call every tick
        url = self._settings.RT_KLINE_CLOUD_PUSH_URL
        if not url:
            return False
        try:
            resp = self._session.get(url, timeout=3)
            if resp.status_code < 500:
                self._cache.set_circuit_breaker(market, False)
                m.push_circuit_breaker(market, False)
                self._failure_start[market] = None
                logger.info("Circuit breaker recovered for %s", market)
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Backlog drain
    # ------------------------------------------------------------------
    def _drain_backlog(self, market: str) -> None:
        backlog = self._backlog[market]
        while backlog:
            payload = backlog[0]
            if self._push_one(market, payload):
                backlog.popleft()
            else:
                break

    # ------------------------------------------------------------------
    # Token refresh
    # ------------------------------------------------------------------
    def _refresh_token(self) -> bool:
        """Try to refresh token from Redis or config center."""
        cache = self._cache
        redis = cache._get_redis()
        if redis is None:
            return False
        try:
            new_token = redis.get("stock:rtk:cloud_push_token")
            if new_token and new_token != self._token:
                self._token = new_token
                return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # DLQ cleanup
    # ------------------------------------------------------------------
    def cleanup_dlq(self) -> Dict[str, int]:
        result = {}
        for market in self._markets:
            removed = self._cache.dlq_trim_old(
                cfg.REDIS_KEY_DLQ_PUSH, market, self._settings.RT_KLINE_PUSH_DLQ_TTL_DAYS
            )
            result[market] = removed
        return result


_push_worker: Optional[CloudPushWorker] = None


def get_push_worker() -> CloudPushWorker:
    global _push_worker
    if _push_worker is None:
        _push_worker = CloudPushWorker()
    return _push_worker
