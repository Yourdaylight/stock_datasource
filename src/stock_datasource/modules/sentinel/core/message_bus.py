"""Redis Pub/Sub message bus for sentinel system.

Handles inter-tier communication:
- Sentinels PUBLISH alerts to sentinel:{type} channels
- Analysts SUBSCRIBE to sentinel:* patterns
- Director SUBSCRIBES to analyst:* patterns
- All messages also written to Redis Stream for persistence/replay
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any, Callable, Coroutine

import redis.asyncio as aioredis

from ..config import SentinelConfig, get_sentinel_config
from ..schemas import AnalystReport, SentinelAlert

logger = logging.getLogger(__name__)


class RedisSentinelBus:
    """Redis-backed message bus for the sentinel system."""

    def __init__(self, config: SentinelConfig | None = None):
        self._config = config or get_sentinel_config()
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._listener_task: asyncio.Task | None = None
        self._running = False
        # Metrics
        self._messages_published = 0
        self._messages_received = 0

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._redis is not None:
            return
        self._redis = aioredis.from_url(
            self._config.redis_url,
            decode_responses=True,
            max_connections=20,
        )
        await self._redis.ping()
        logger.info("RedisSentinelBus connected to %s", self._config.redis_url)

    async def start_listener(self) -> None:
        """Start the subscription listener loop."""
        if self._running:
            return
        await self.connect()
        self._pubsub = self._redis.pubsub()
        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("RedisSentinelBus listener started")

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
        logger.info("RedisSentinelBus stopped")

    def subscribe(self, pattern: str, handler: Callable) -> None:
        """Register a handler for a channel pattern.

        Pattern examples:
            "sentinel:market_risk" - exact channel
            "sentinel:ma_crossover.*" - all ma_crossover sub-channels
            "analyst:*" - all analyst channels
        """
        self._handlers[pattern].append(handler)

    async def activate_subscriptions(self) -> None:
        """Activate all registered subscriptions on Redis pubsub."""
        if not self._pubsub:
            return
        patterns = set()
        for pattern in self._handlers:
            # Convert our pattern format to Redis pattern
            redis_pattern = pattern.replace(".", ":")
            if "*" in redis_pattern:
                patterns.add(redis_pattern)
            else:
                patterns.add(redis_pattern)

        if patterns:
            await self._pubsub.psubscribe(*patterns)
            logger.info("Activated subscriptions: %s", patterns)

    async def publish_alert(self, alert: SentinelAlert) -> None:
        """Publish a sentinel alert to Redis."""
        if not self._redis:
            await self.connect()

        channel = f"{self._config.sentinel_channel_prefix}:{alert.sentinel_type}"
        if alert.ts_code:
            channel += f":{alert.ts_code}"
        elif alert.sector_code:
            channel += f":{alert.sector_code}"

        payload = alert.model_dump_json()

        # Publish to pub/sub channel
        await self._redis.publish(channel, payload)

        # Also write to Redis Stream for persistence
        stream_key = f"stream:{self._config.sentinel_channel_prefix}"
        await self._redis.xadd(
            stream_key,
            {"channel": channel, "payload": payload, "timestamp": str(time.time())},
            maxlen=self._config.redis_stream_maxlen,
        )

        self._messages_published += 1
        logger.debug("Published alert to %s: %s", channel, alert.description[:60])

    async def publish_report(self, report: AnalystReport) -> None:
        """Publish an analyst report to Redis."""
        if not self._redis:
            await self.connect()

        channel = f"{self._config.analyst_channel_prefix}:{report.analyst_type}"
        payload = report.model_dump_json()

        await self._redis.publish(channel, payload)

        # Stream for persistence
        stream_key = f"stream:{self._config.analyst_channel_prefix}"
        await self._redis.xadd(
            stream_key,
            {"channel": channel, "payload": payload, "timestamp": str(time.time())},
            maxlen=self._config.redis_stream_maxlen,
        )

        self._messages_published += 1
        logger.debug("Published report from %s (conviction=%.2f)", report.analyst_type, report.overall_conviction)

    async def _listen_loop(self) -> None:
        """Main listener loop - dispatches messages to registered handlers."""
        await self.activate_subscriptions()

        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if message and message["type"] in ("pmessage", "message"):
                    await self._dispatch(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Listener error: %s", e)
                await asyncio.sleep(1)

    async def _dispatch(self, message: dict) -> None:
        """Dispatch a received message to matching handlers."""
        channel = message.get("channel", "")
        if isinstance(channel, bytes):
            channel = channel.decode()
        data = message.get("data", "")
        if isinstance(data, bytes):
            data = data.decode()

        self._messages_received += 1

        for pattern, handlers in self._handlers.items():
            if self._pattern_matches(pattern, channel):
                for handler in handlers:
                    try:
                        result = handler(channel, data)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error("Handler error for %s: %s", pattern, e)

    @staticmethod
    def _pattern_matches(pattern: str, channel: str) -> bool:
        """Check if a channel matches our pattern format."""
        # Normalize separators
        norm_pattern = pattern.replace(".", ":")
        if norm_pattern == channel:
            return True
        if norm_pattern.endswith(":*"):
            prefix = norm_pattern[:-2]
            return channel.startswith(prefix + ":") or channel == prefix
        if "*" in norm_pattern:
            # Simple wildcard
            prefix = norm_pattern.split("*")[0]
            return channel.startswith(prefix)
        # Prefix match
        return channel.startswith(norm_pattern + ":")

    def get_metrics(self) -> dict[str, Any]:
        return {
            "connected": self._redis is not None,
            "running": self._running,
            "messages_published": self._messages_published,
            "messages_received": self._messages_received,
            "subscription_count": sum(len(h) for h in self._handlers.values()),
        }


# Singleton
_bus: RedisSentinelBus | None = None


def get_message_bus(config: SentinelConfig | None = None) -> RedisSentinelBus:
    global _bus
    if _bus is None:
        _bus = RedisSentinelBus(config)
    return _bus
