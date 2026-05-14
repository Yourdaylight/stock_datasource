"""Agent registry — manages lifecycle of all sentinels, analysts, and director."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from ..config import get_sentinel_config
from .base_analyst import BaseAnalyst
from .base_sentinel import BaseSentinel
from .director import InvestmentDirector
from .message_bus import get_message_bus

logger = logging.getLogger(__name__)


class SentinelRegistry:
    """Manages the full lifecycle of the sentinel system."""

    def __init__(self):
        self._sentinels: list[BaseSentinel] = []
        self._analysts: list[BaseAnalyst] = []
        self._director: InvestmentDirector | None = None
        self._initialized = False
        self._last_cycle_time: float = 0

    async def initialize(self) -> None:
        """Initialize all agents and start message bus."""
        if self._initialized:
            return

        # Start Redis message bus
        bus = get_message_bus()
        await bus.connect()
        await bus.start_listener()

        # Create sentinels
        from ..sentinels import create_all_sentinels
        self._sentinels = create_all_sentinels()

        # Create analysts
        from ..analysts import create_all_analysts
        self._analysts = create_all_analysts()

        # Initialize analysts (register subscriptions)
        for analyst in self._analysts:
            await analyst.initialize()

        # Create and initialize director
        self._director = InvestmentDirector()
        await self._director.initialize()

        # Activate Redis subscriptions
        await bus.activate_subscriptions()

        self._initialized = True
        logger.info(
            "SentinelRegistry initialized: %d sentinels, %d analysts, 1 director",
            len(self._sentinels),
            len(self._analysts),
        )

    async def run_scan_cycle(self) -> dict[str, Any]:
        """Run one full scan cycle.

        Phase 1: All sentinels scan in parallel
        Phase 2: Brief wait for Redis message delivery
        Phase 3: All analysts run analysis
        Phase 4: Brief wait for Redis message delivery
        Phase 5: Director produces decision (calls LLM)
        """
        if not self._initialized:
            await self.initialize()

        cycle_result: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "sentinel_alerts": 0,
            "analyst_reports": 0,
            "decision_produced": False,
            "decision": None,
        }

        # Phase 1: All sentinels scan in parallel
        logger.info("=" * 60)
        logger.info("Sentinel scan cycle started")
        logger.info("=" * 60)

        sentinel_tasks = [s.execute_scan() for s in self._sentinels]
        sentinel_results = await asyncio.gather(*sentinel_tasks, return_exceptions=True)

        total_alerts = 0
        for result in sentinel_results:
            if isinstance(result, list):
                total_alerts += len(result)
            elif isinstance(result, Exception):
                logger.error("Sentinel scan error: %s", result)
        cycle_result["sentinel_alerts"] = total_alerts

        logger.info("Phase 1 complete: %d total alerts from %d sentinels", total_alerts, len(self._sentinels))

        # Phase 2: Wait for Redis to deliver messages to analysts
        await asyncio.sleep(1.0)

        # Phase 3: Analysts run analysis
        analyst_tasks = [a.run_analysis_cycle() for a in self._analysts]
        analyst_results = await asyncio.gather(*analyst_tasks, return_exceptions=True)

        reports_produced = 0
        for result in analyst_results:
            if result and not isinstance(result, Exception):
                reports_produced += 1
            elif isinstance(result, Exception):
                logger.error("Analyst analysis error: %s", result)
        cycle_result["analyst_reports"] = reports_produced

        logger.info("Phase 3 complete: %d analyst reports produced", reports_produced)

        # Phase 4: Wait for Redis to deliver reports to director
        await asyncio.sleep(0.5)

        # Phase 5: Director produces decision (LLM call)
        if reports_produced > 0 and self._director:
            trade_date = datetime.now().strftime("%Y%m%d")
            decision = await self._director.produce_decision(trade_date)
            if decision:
                cycle_result["decision_produced"] = True
                cycle_result["decision"] = decision.model_dump()
                # Persist decision
                await self._persist_decision(decision)

        self._last_cycle_time = asyncio.get_event_loop().time()

        logger.info(
            "Scan cycle complete: %d alerts -> %d reports -> decision=%s",
            total_alerts,
            reports_produced,
            cycle_result["decision_produced"],
        )
        return cycle_result

    async def shutdown(self) -> None:
        """Graceful shutdown."""
        bus = get_message_bus()
        await bus.stop()
        self._initialized = False
        logger.info("SentinelRegistry shut down")

    async def _persist_decision(self, decision: InvestmentDecision) -> None:
        """Save decision to ClickHouse."""
        try:
            import json
            import pandas as pd
            from stock_datasource.models.database import db_client

            row = {
                "decision_id": decision.decision_id,
                "trade_date": decision.trade_date,
                "market_regime": decision.market_regime.value,
                "market_risk_level": decision.market_risk_level,
                "suggested_position": decision.suggested_total_position,
                "buy_count": len(decision.buy_candidates),
                "sell_count": len(decision.sell_candidates),
                "confidence": decision.confidence,
                "decision_json": json.dumps(
                    decision.model_dump(), ensure_ascii=False, default=str
                ),
                "created_at": datetime.now(),
            }
            db_client.insert_dataframe("sentinel_decisions", pd.DataFrame([row]))
            logger.info("Decision persisted: %s", decision.decision_id)
        except Exception as e:
            logger.warning("Failed to persist decision: %s", e)

    def get_status(self) -> dict[str, Any]:
        return {
            "initialized": self._initialized,
            "sentinels": [s.get_status() for s in self._sentinels],
            "analysts": [a.get_status() for a in self._analysts],
            "director": self._director.get_status() if self._director else None,
            "message_bus": get_message_bus().get_metrics(),
            "last_cycle_time": self._last_cycle_time,
        }


# Singleton
_registry: SentinelRegistry | None = None


def get_sentinel_registry() -> SentinelRegistry:
    global _registry
    if _registry is None:
        _registry = SentinelRegistry()
    return _registry
