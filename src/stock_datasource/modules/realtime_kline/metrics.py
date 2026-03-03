"""Lightweight observability metrics for the realtime kline pipeline.

Tracks counters and gauges in-process. Can be extended to export to
Prometheus / StatsD / structured log by swapping the backend.
For now, all metrics live in a thread-safe dict + are periodically
flushed to Redis status hash for the /status endpoint.
"""

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict

logger = logging.getLogger(__name__)


class _Metrics:
    """Thread-safe in-process metric store."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = defaultdict(list)

    # -- counters --
    def inc(self, name: str, delta: int = 1, labels: Dict[str, str] | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += delta

    def counter(self, name: str, labels: Dict[str, str] | None = None) -> int:
        return self._counters.get(self._key(name, labels), 0)

    # -- gauges --
    def set_gauge(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[self._key(name, labels)] = value

    def gauge(self, name: str, labels: Dict[str, str] | None = None) -> float:
        return self._gauges.get(self._key(name, labels), 0.0)

    # -- histograms (simple, capped) --
    def observe(self, name: str, value: float, labels: Dict[str, str] | None = None) -> None:
        key = self._key(name, labels)
        with self._lock:
            buf = self._histograms[key]
            buf.append(value)
            if len(buf) > 1000:
                self._histograms[key] = buf[-500:]

    # -- snapshot --
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
            }

    @staticmethod
    def _key(name: str, labels: Dict[str, str] | None) -> str:
        if not labels:
            return name
        suffix = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{suffix}}}"


# Global singleton
metrics = _Metrics()


# ---------- convenience functions ----------

def collector_call(market: str, success: bool, latency_ms: float) -> None:
    labels = {"market": market}
    metrics.inc("rt_kline_collector_calls_total", labels=labels)
    if success:
        metrics.inc("rt_kline_collector_success_total", labels=labels)
    else:
        metrics.inc("rt_kline_collector_errors_total", labels=labels)
    metrics.observe("rt_kline_collector_latency_ms", latency_ms, labels=labels)


def collector_backoff_level(market: str, level: float) -> None:
    metrics.set_gauge("rt_kline_collector_backoff_level", level, labels={"market": market})


def push_event(market: str, status: str) -> None:
    metrics.inc("rt_kline_push_events_total", labels={"market": market, "status": status})


def push_latency(market: str, ms: float) -> None:
    metrics.observe("rt_kline_push_latency_ms", ms, labels={"market": market})


def push_retry(market: str) -> None:
    metrics.inc("rt_kline_push_retry_count", labels={"market": market})


def push_dlq_size(market: str, size: int) -> None:
    metrics.set_gauge("rt_kline_push_deadletter_size", float(size), labels={"market": market})


def push_circuit_breaker(market: str, active: bool) -> None:
    metrics.set_gauge("rt_kline_push_circuit_breaker_active", 1.0 if active else 0.0, labels={"market": market})


def push_ack_lag(market: str, lag_ms: float) -> None:
    metrics.set_gauge("rt_kline_push_ack_lag_ms", lag_ms, labels={"market": market})


def sink_batch(market: str, success: bool, records: int, latency_ms: float) -> None:
    labels = {"market": market}
    status = "success" if success else "failed"
    metrics.inc("rt_kline_sink_batches_total", labels={**labels, "status": status})
    if success:
        metrics.inc("rt_kline_sink_records_total", delta=records, labels=labels)
    metrics.observe("rt_kline_sink_latency_ms", latency_ms, labels=labels)


def sink_backlog(market: str, depth: int) -> None:
    metrics.set_gauge("rt_kline_sink_backlog_depth", float(depth), labels={"market": market})


def sink_dlq_size(market: str, size: int) -> None:
    metrics.set_gauge("rt_kline_sink_deadletter_size", float(size), labels={"market": market})


def sink_market_failure(market: str) -> None:
    metrics.inc("rt_kline_sink_market_failure_count", labels={"market": market})
