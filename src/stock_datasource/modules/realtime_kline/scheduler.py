"""Scheduler for the decoupled realtime kline pipeline.

Manages three independent worker lifecycles:
1. Collector Worker  — every 1.5s, collects snapshots → Redis (latest + stream)
2. Cloud Push Worker — every 2s, sliding-window delta → cloud (hidden, switchable)
3. Minute Sink Worker — every 60s, stream → ClickHouse

All workers are independent: push failure ≠ block collector or sink.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

from . import config as cfg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trading hours check
# ---------------------------------------------------------------------------
def is_trading_time() -> bool:
    now = datetime.now()
    time_str = now.strftime("%H:%M")

    for start, end in cfg.CN_TRADING_HOURS:
        if start <= time_str <= end:
            return True

    for start, end in cfg.HK_TRADING_HOURS:
        if start <= time_str <= end:
            return True

    return False


# ---------------------------------------------------------------------------
# Standalone functions (for external callers / tests)
# ---------------------------------------------------------------------------
def run_collection(markets=None) -> dict:
    from .collector import get_collector
    from .cache import get_cache_store

    collector = get_collector()
    cache = get_cache_store()
    data = collector.collect_all(markets=markets)

    result = {}
    total = 0
    for market_name, rows in data.items():
        if rows:
            count = cache.store_snapshots(market_name, rows)
            cache.update_status(market_name, count)
            result[market_name] = count
            total += count
        else:
            result[market_name] = 0

    logger.info("Kline collection round: %d total, details=%s", total, result)
    return result


def run_push_tick() -> None:
    from .cloud_push import get_push_worker
    worker = get_push_worker()
    worker.tick()


def run_sink_tick() -> dict:
    from .sync_service import get_sink_worker
    worker = get_sink_worker()
    return worker.tick()


def run_sync(date: str | None = None) -> dict:
    """Legacy compat: trigger a single sink tick."""
    return run_sink_tick()


def run_cleanup(date: str | None = None) -> dict:
    from .sync_service import get_sink_worker
    worker = get_sink_worker()
    stream_trimmed = worker.cleanup_streams()
    latest_deleted = worker.cleanup_latest()
    push_cleared = worker.clear_push_state()
    return {
        "stream_trimmed": stream_trimmed,
        "latest_deleted": latest_deleted,
        "push_state_cleared": push_cleared,
    }


# ---------------------------------------------------------------------------
# Worker threads (independent lifecycle)
# ---------------------------------------------------------------------------
class _WorkerThread(threading.Thread):
    """Base worker thread with stop flag."""

    def __init__(self, name: str, interval: float):
        super().__init__(name=name, daemon=True)
        self._interval = interval
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopped(self) -> bool:
        return self._stop_event.is_set()

    def run(self) -> None:
        raise NotImplementedError


class CollectorThread(_WorkerThread):
    def __init__(self):
        from stock_datasource.config.settings import settings
        super().__init__("rt-kline-collector", settings.RT_KLINE_COLLECT_INTERVAL)

    def run(self) -> None:
        from .collector import get_collector
        collector = get_collector()

        logger.info("Collector worker started (interval=%.1fs)", self._interval)
        next_run_at = time.monotonic()

        while not self.stopped:
            if not is_trading_time():
                # idle outside trading hours
                next_run_at = time.monotonic() + 30
                self._stop_event.wait(30)
                continue

            now = time.monotonic()
            if now < next_run_at:
                self._stop_event.wait(next_run_at - now)
                continue

            started_at = time.monotonic()
            try:
                run_collection()
            except Exception as e:
                logger.error("Collector error: %s", e, exc_info=True)

            # Per-market max backoff as target cadence. Schedule from start-time
            # to avoid extra post-round waiting when collection itself is slow.
            interval = max(
                collector.backoff.current_interval(mkt)
                for mkt in cfg.CLICKHOUSE_TABLES
            )
            next_run_at = started_at + interval


class PushThread(_WorkerThread):
    def __init__(self):
        from stock_datasource.config.settings import settings
        super().__init__("rt-kline-push", settings.RT_KLINE_CLOUD_PUSH_INTERVAL)

    def run(self) -> None:
        logger.info("Push worker started (interval=%.1fs)", self._interval)
        while not self.stopped:
            try:
                run_push_tick()
            except Exception as e:
                logger.error("Push worker error: %s", e, exc_info=True)
            self._stop_event.wait(self._interval)


class SinkThread(_WorkerThread):
    def __init__(self):
        from stock_datasource.config.settings import settings
        super().__init__("rt-kline-sink", float(settings.RT_KLINE_SINK_INTERVAL))

    def run(self) -> None:
        logger.info("Sink worker started (interval=%.0fs)", self._interval)
        while not self.stopped:
            if is_trading_time():
                try:
                    run_sink_tick()
                except Exception as e:
                    logger.error("Sink worker error: %s", e, exc_info=True)
            self._stop_event.wait(self._interval)


# ---------------------------------------------------------------------------
# Lifecycle manager
# ---------------------------------------------------------------------------
class RealtimeKlineRuntime:
    """Manages the three independent workers as a single runtime."""

    def __init__(self):
        self._collector: Optional[CollectorThread] = None
        self._push: Optional[PushThread] = None
        self._sink: Optional[SinkThread] = None

    def start(self) -> None:
        from stock_datasource.config.settings import settings

        logger.info("Starting RealtimeKline runtime (decoupled)")

        self._collector = CollectorThread()
        self._collector.start()

        self._sink = SinkThread()
        self._sink.start()

        if settings.RT_KLINE_CLOUD_PUSH_ENABLED:
            self._push = PushThread()
            self._push.start()
        else:
            logger.info("Cloud push disabled (RT_KLINE_CLOUD_PUSH_ENABLED=false)")

    def stop(self) -> None:
        logger.info("Stopping RealtimeKline runtime")
        for w in (self._collector, self._push, self._sink):
            if w is not None:
                w.stop()

        for w in (self._collector, self._push, self._sink):
            if w is not None and w.is_alive():
                w.join(timeout=10)

    def start_push_if_needed(self) -> None:
        """Dynamically start push worker if switch turned on."""
        if self._push is not None and self._push.is_alive():
            return
        self._push = PushThread()
        self._push.start()

    def stop_push(self) -> None:
        """Dynamically stop push worker."""
        if self._push is not None:
            self._push.stop()
            self._push = None

    @property
    def is_running(self) -> bool:
        return self._collector is not None and self._collector.is_alive()

    def health(self) -> dict:
        return {
            "collector": self._collector.is_alive() if self._collector else False,
            "push": self._push.is_alive() if self._push else False,
            "sink": self._sink.is_alive() if self._sink else False,
        }


_runtime: Optional[RealtimeKlineRuntime] = None


def get_runtime() -> RealtimeKlineRuntime:
    global _runtime
    if _runtime is None:
        _runtime = RealtimeKlineRuntime()
    return _runtime


# ---------------------------------------------------------------------------
# APScheduler integration (backward compat)
# ---------------------------------------------------------------------------
def register_realtime_kline_jobs(scheduler) -> None:
    """Register with APScheduler. Starts the independent runtime."""
    rt = get_runtime()
    if not rt.is_running:
        rt.start()
    logger.info("RealtimeKline runtime registered with scheduler")
