"""Base class for all Analyst Agents (Tier 2).

An analyst subscribes to multiple sentinel topics.
It collects alerts in a buffer, and when it detects a meaningful PATTERN
across multiple alerts, it synthesizes an AnalystReport and escalates upward.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from typing import Any

from ..schemas import AnalystReport, SentinelAlert
from .message_bus import get_message_bus

logger = logging.getLogger(__name__)


class BaseAnalyst(ABC):
    """Abstract base for analyst agents.

    Key behaviors:
    1. Subscribes to multiple sentinel topics on initialize()
    2. Buffers incoming alerts
    3. Runs analysis when threshold reached or CRITICAL alert arrives
    4. Only escalates when conviction > threshold
    """

    ANALYST_TYPE: str = ""
    SUBSCRIBED_PATTERNS: list[str] = []
    MIN_ALERTS_TO_ANALYZE: int = 2
    BUFFER_MAX_SIZE: int = 100

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._alert_buffer: deque[SentinelAlert] = deque(maxlen=self.BUFFER_MAX_SIZE)
        self._last_analysis_time: float = 0
        self._report_count: int = 0
        self._min_conviction: float = self.config.get("min_conviction", 0.3)

    async def initialize(self) -> None:
        """Register subscriptions on the message bus."""
        bus = get_message_bus()
        for pattern in self.SUBSCRIBED_PATTERNS:
            bus.subscribe(pattern, self._on_message_received)
        logger.info(
            "[%s] Initialized, subscribed to: %s",
            self.ANALYST_TYPE,
            self.SUBSCRIBED_PATTERNS,
        )

    async def _on_message_received(self, channel: str, data: str) -> None:
        """Handler for incoming sentinel alerts from Redis."""
        try:
            alert = SentinelAlert.model_validate_json(data)
            self._alert_buffer.append(alert)
            logger.debug(
                "[%s] Received alert from %s: %s",
                self.ANALYST_TYPE,
                alert.sentinel_type,
                alert.description[:50],
            )
        except Exception as e:
            logger.error("[%s] Failed to parse alert: %s", self.ANALYST_TYPE, e)

    async def run_analysis_cycle(self) -> AnalystReport | None:
        """Main analysis entry point.

        1. Check if we have enough alerts to analyze
        2. Call analyze() for pattern detection
        3. If conviction > threshold, publish report to Redis
        """
        alerts = list(self._alert_buffer)
        if len(alerts) < self.MIN_ALERTS_TO_ANALYZE:
            return None

        try:
            report = await self.analyze(alerts)

            if report and report.overall_conviction >= self._min_conviction:
                # Worth escalating
                report.report_id = str(uuid.uuid4())[:12]
                report.analyst_type = self.ANALYST_TYPE
                report.trigger_count = len(alerts)
                # Keep last 20 source alerts for context
                report.source_alerts = alerts[-20:]

                # Publish to Redis
                bus = get_message_bus()
                await bus.publish_report(report)

                self._report_count += 1
                self._alert_buffer.clear()
                self._last_analysis_time = time.time()

                logger.info(
                    "[%s] Report published (conviction=%.2f, insights=%d)",
                    self.ANALYST_TYPE,
                    report.overall_conviction,
                    len(report.insights),
                )
                return report
            else:
                logger.debug("[%s] No significant pattern found", self.ANALYST_TYPE)
                return None

        except Exception as e:
            logger.error("[%s] Analysis failed: %s", self.ANALYST_TYPE, e)
            return None

    @abstractmethod
    async def analyze(self, alerts: list[SentinelAlert]) -> AnalystReport | None:
        """Perform cross-signal analysis on buffered alerts.

        Returns:
            AnalystReport if meaningful pattern found, None otherwise
        """
        pass

    @abstractmethod
    def get_analysis_description(self) -> str:
        """Human-readable description of this analyst's role."""
        pass

    def get_status(self) -> dict[str, Any]:
        return {
            "type": self.ANALYST_TYPE,
            "buffer_size": len(self._alert_buffer),
            "report_count": self._report_count,
            "last_analysis": self._last_analysis_time,
            "subscribed_patterns": self.SUBSCRIBED_PATTERNS,
        }
