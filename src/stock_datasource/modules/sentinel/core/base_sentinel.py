"""Base class for all Data Sentinels (Tier 1).

A sentinel monitors ONE specific data point or narrow aspect.
It stays SILENT unless it detects an anomaly worth reporting.
"""

from __future__ import annotations

import logging
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any

from ..schemas import AlertCategory, AlertSeverity, SentinelAlert
from .message_bus import get_message_bus

logger = logging.getLogger(__name__)


class BaseSentinel(ABC):
    """Abstract base for all sentinels.

    Lifecycle:
    1. __init__: Configure monitoring parameters
    2. scan(): Called periodically. Returns alerts if anomaly detected.
    3. execute_scan(): Wraps scan() with cooldown filtering and publishing.
    """

    SENTINEL_TYPE: str = ""
    CATEGORY: AlertCategory = AlertCategory.TECHNICAL

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._last_scan_time: float = 0
        self._alert_count: int = 0
        self._consecutive_silent: int = 0
        self._cooldown_seconds: int = self.config.get("cooldown_seconds", 3600)
        self._last_alerts: dict[str, float] = {}  # cooldown_key → timestamp

    @abstractmethod
    async def scan(self) -> list[SentinelAlert]:
        """Perform one scan cycle.

        Returns:
            List of alerts (empty = nothing abnormal, stay silent)
        """
        pass

    @abstractmethod
    def get_monitoring_description(self) -> str:
        """Human-readable description of what this sentinel monitors."""
        pass

    async def execute_scan(self) -> list[SentinelAlert]:
        """Execute scan with cooldown filtering and Redis publishing."""
        start = time.time()
        try:
            alerts = await self.scan()

            # Apply cooldown filter
            filtered_alerts = []
            for alert in alerts:
                cooldown_key = (
                    f"{alert.sentinel_type}:"
                    f"{alert.ts_code or alert.sector_code or alert.index_code or 'global'}:"
                    f"{alert.signal_type}"
                )
                last_fired = self._last_alerts.get(cooldown_key, 0)
                if time.time() - last_fired >= self._cooldown_seconds:
                    filtered_alerts.append(alert)
                    self._last_alerts[cooldown_key] = time.time()
                else:
                    logger.debug(
                        "Alert suppressed by cooldown: %s (%.0fs ago)",
                        cooldown_key,
                        time.time() - last_fired,
                    )

            # Publish to Redis
            if filtered_alerts:
                bus = get_message_bus()
                for alert in filtered_alerts:
                    if not alert.alert_id:
                        alert.alert_id = str(uuid.uuid4())[:12]
                    await bus.publish_alert(alert)
                    self._alert_count += 1

            # Track silence streaks
            if filtered_alerts:
                self._consecutive_silent = 0
            else:
                self._consecutive_silent += 1

            self._last_scan_time = time.time()
            elapsed = int((time.time() - start) * 1000)

            if filtered_alerts:
                logger.info(
                    "[%s] Scan: %d alerts fired (%dms)",
                    self.SENTINEL_TYPE,
                    len(filtered_alerts),
                    elapsed,
                )

            return filtered_alerts

        except Exception as e:
            logger.error("[%s] Scan failed: %s", self.SENTINEL_TYPE, e)
            return []

    def get_status(self) -> dict[str, Any]:
        return {
            "type": self.SENTINEL_TYPE,
            "category": self.CATEGORY.value,
            "last_scan": self._last_scan_time,
            "alert_count": self._alert_count,
            "consecutive_silent": self._consecutive_silent,
            "description": self.get_monitoring_description(),
        }
