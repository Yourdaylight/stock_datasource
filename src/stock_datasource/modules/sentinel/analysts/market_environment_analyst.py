"""Market Environment Analyst - classifies market regime and escalates on regime changes."""

from __future__ import annotations

import logging
from typing import Any

from ..core.base_analyst import BaseAnalyst
from ..schemas import (
    AlertCategory,
    AnalystInsight,
    AnalystReport,
    MarketRegime,
    SentinelAlert,
    StockSignal,
    ActionType,
)

logger = logging.getLogger(__name__)


class MarketEnvironmentAnalyst(BaseAnalyst):
    """Classifies market regime and escalates on regime changes or critical alerts.

    Determines overall market state:
    - BULL: Index above MA250, trending up
    - BEAR: Index below MA250, trending down
    - CONSOLIDATION: Index near MA250, no clear trend
    - TRANSITION_UP: Recently crossed above MA250
    - TRANSITION_DOWN: Recently crossed below MA250
    """

    ANALYST_TYPE: str = "market_environment"
    SUBSCRIBED_PATTERNS: list[str] = ["sentinel:market_risk", "sentinel:news_sentiment"]
    MIN_ALERTS_TO_ANALYZE: int = 1  # Market risk is critical enough for single alert

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._current_regime: MarketRegime | None = None
        self._previous_regime: MarketRegime | None = None

    def get_analysis_description(self) -> str:
        return "分析市场整体环境，识别牛熊转换和市场风险状态变化"

    async def analyze(self, alerts: list[SentinelAlert]) -> AnalystReport | None:
        """Classify market regime from alerts and external data."""
        # Classify regime from alerts
        new_regime = self._classify_regime(alerts)
        is_critical = any(a.severity.value == "critical" for a in alerts)
        regime_changed = (
            new_regime != self._current_regime and self._current_regime is not None
        )

        # Only escalate on regime change or critical alerts
        if not regime_changed and not is_critical:
            # Still update internal state
            self._current_regime = new_regime
            return None

        # Get additional context from SignalGenerator
        market_risk_context = await self._get_market_risk_context()

        # Build insights
        insights: list[AnalystInsight] = []
        conviction = 0.5

        if regime_changed:
            self._previous_regime = self._current_regime
            insights.append(AnalystInsight(
                insight_type="regime_change",
                description=(
                    f"市场状态从 {self._current_regime.value if self._current_regime else 'unknown'} "
                    f"转变为 {new_regime.value}"
                ),
                confidence=0.8,
                supporting_alerts=[a.alert_id for a in alerts],
            ))
            conviction = 0.8

        if is_critical:
            critical_alerts = [a for a in alerts if a.severity.value == "critical"]
            for alert in critical_alerts:
                insights.append(AnalystInsight(
                    insight_type="critical_market_signal",
                    description=alert.description,
                    confidence=0.9,
                    supporting_alerts=[alert.alert_id],
                ))
            conviction = max(conviction, 0.85)

        # Enrich with market risk data
        if market_risk_context:
            risk_level = market_risk_context.get("risk_level", "normal")
            if risk_level == "danger":
                conviction = max(conviction, 0.9)
                insights.append(AnalystInsight(
                    insight_type="market_risk_elevated",
                    description=(
                        f"沪深300处于年线下方，风险等级: {risk_level}，"
                        f"建议仓位: {market_risk_context.get('suggested_position', 1.0):.0%}"
                    ),
                    confidence=0.85,
                ))

        self._current_regime = new_regime

        return AnalystReport(
            analyst_type=self.ANALYST_TYPE,
            market_regime=new_regime,
            insights=insights,
            overall_conviction=conviction,
            sector_view={},
            stock_signals=[],
        )

    def _classify_regime(self, alerts: list[SentinelAlert]) -> MarketRegime:
        """Classify market regime based on alert signals."""
        for alert in alerts:
            signal = alert.signal_type
            context = alert.context

            if signal == "ma250_golden_cross":
                return MarketRegime.TRANSITION_UP
            elif signal == "ma250_death_cross":
                return MarketRegime.TRANSITION_DOWN
            elif signal == "ma250_extreme_deviation":
                deviation = alert.deviation_pct
                if deviation > 5.0:
                    return MarketRegime.BULL
                elif deviation < -5.0:
                    return MarketRegime.BEAR

            # Check context for additional signals
            ctx_signal = context.get("signal", "")
            if ctx_signal == "bullish_crossover":
                return MarketRegime.TRANSITION_UP
            elif ctx_signal == "bearish_crossover":
                return MarketRegime.TRANSITION_DOWN

        # Default: maintain current or consolidation
        if self._current_regime:
            # Evolve transitions into full regimes
            if self._current_regime == MarketRegime.TRANSITION_UP:
                return MarketRegime.BULL
            elif self._current_regime == MarketRegime.TRANSITION_DOWN:
                return MarketRegime.BEAR
            return self._current_regime

        return MarketRegime.CONSOLIDATION

    async def _get_market_risk_context(self) -> dict[str, Any]:
        """Query SignalGenerator for additional market risk context."""
        try:
            from stock_datasource.modules.quant.signal_generator import get_signal_generator

            generator = get_signal_generator()
            risk_status = await generator.check_market_risk()
            return {
                "risk_level": risk_status.risk_level,
                "suggested_position": risk_status.suggested_position,
                "index_close": risk_status.index_close,
                "index_ma250": risk_status.index_ma250,
                "is_above_ma250": risk_status.is_above_ma250,
            }
        except Exception as e:
            logger.warning("Failed to get market risk context: %s", e)
            return {}
