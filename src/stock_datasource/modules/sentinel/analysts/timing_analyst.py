"""Timing Analyst - determines optimal entry/exit timing for stock signals."""

from __future__ import annotations

import logging
from collections import defaultdict
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


class TimingAnalyst(BaseAnalyst):
    """Determines optimal entry/exit timing by combining multiple signal dimensions.

    Timing logic:
    - If market_risk "bear_cross" → override all buys to WATCH
    - If golden_cross + volume_spike + capital_inflow → "immediate" urgency, confidence 0.9
    - If golden_cross + volume_spike → confidence 0.7
    - If golden_cross alone → "opportunistic", confidence 0.5
    """

    ANALYST_TYPE: str = "timing"
    SUBSCRIBED_PATTERNS: list[str] = [
        "sentinel:ma_crossover:*",
        "sentinel:volume_anomaly:*",
        "sentinel:capital_flow:*",
        "sentinel:market_risk",
    ]
    MIN_ALERTS_TO_ANALYZE: int = 2

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._bear_market_override: bool = False

    def get_analysis_description(self) -> str:
        return "分析最佳入场/出场时机，综合市场环境、技术信号和资金面判断紧迫程度"

    async def analyze(self, alerts: list[SentinelAlert]) -> AnalystReport | None:
        """Analyze timing signals across multiple dimensions."""
        # First check for bear market override
        self._check_market_risk_override(alerts)

        # Group stock-level alerts by ts_code
        stock_alerts: dict[str, list[SentinelAlert]] = defaultdict(list)
        market_alerts: list[SentinelAlert] = []

        for alert in alerts:
            if alert.ts_code:
                stock_alerts[alert.ts_code].append(alert)
            else:
                market_alerts.append(alert)

        if not stock_alerts and not market_alerts:
            return None

        stock_signals: list[StockSignal] = []
        insights: list[AnalystInsight] = []

        for ts_code, ts_alerts in stock_alerts.items():
            signal, urgency = self._evaluate_timing(ts_code, ts_alerts)
            if signal:
                stock_signals.append(signal)

                if signal.confidence >= 0.7:
                    insights.append(AnalystInsight(
                        insight_type="timing_signal",
                        description=(
                            f"{ts_code} 时机信号: {signal.action.value} "
                            f"(紧迫度: {urgency}, 置信度: {signal.confidence:.0%})"
                        ),
                        confidence=signal.confidence,
                        supporting_alerts=[a.alert_id for a in ts_alerts],
                        related_stocks=[ts_code],
                    ))

        # Add bear market override insight if active
        if self._bear_market_override:
            insights.append(AnalystInsight(
                insight_type="bear_market_override",
                description="市场处于空头状态，所有买入信号降级为观察",
                confidence=0.85,
                supporting_alerts=[a.alert_id for a in market_alerts],
            ))

        if not stock_signals and not insights:
            return None

        # Overall conviction based on signal quality
        if stock_signals:
            max_confidence = max(s.confidence for s in stock_signals)
            overall_conviction = min(0.3 + max_confidence * 0.5, 0.9)
        else:
            overall_conviction = 0.5 if self._bear_market_override else 0.3

        return AnalystReport(
            analyst_type=self.ANALYST_TYPE,
            stock_signals=stock_signals,
            insights=insights,
            overall_conviction=overall_conviction,
        )

    def _check_market_risk_override(self, alerts: list[SentinelAlert]) -> None:
        """Check if any market risk alert triggers bear override."""
        for alert in alerts:
            if alert.sentinel_type == "market_risk":
                signal_type = alert.signal_type.lower()
                context_signal = alert.context.get("signal", "")

                if (
                    "death_cross" in signal_type
                    or "bear_cross" in signal_type
                    or "bearish_crossover" in context_signal
                ):
                    self._bear_market_override = True
                    return
                elif (
                    "golden_cross" in signal_type
                    or "bullish_crossover" in context_signal
                ):
                    # Clear bear override on bullish signal
                    self._bear_market_override = False

    def _evaluate_timing(
        self, ts_code: str, alerts: list[SentinelAlert]
    ) -> tuple[StockSignal | None, str]:
        """Evaluate timing for a single stock.

        Returns:
            Tuple of (StockSignal or None, urgency string)
        """
        has_golden_cross = False
        has_death_cross = False
        has_volume_spike = False
        has_capital_inflow = False
        has_capital_outflow = False

        reasons: list[str] = []

        for alert in alerts:
            signal_type = alert.signal_type.lower()

            if "golden_cross" in signal_type:
                has_golden_cross = True
                reasons.append("均线金叉")
            elif "death_cross" in signal_type:
                has_death_cross = True
                reasons.append("均线死叉")

            if "volume_spike" in signal_type or "volume_anomaly" in signal_type:
                has_volume_spike = True
                reasons.append("成交量放大")
            elif alert.category == AlertCategory.VOLUME:
                has_volume_spike = True
                reasons.append("量能异动")

            if alert.category == AlertCategory.CAPITAL:
                direction = alert.context.get("direction", "")
                if direction in ("inflow", "bullish") or alert.metric_value > 0:
                    has_capital_inflow = True
                    reasons.append("资金净流入")
                elif direction in ("outflow", "bearish") or alert.metric_value < 0:
                    has_capital_outflow = True
                    reasons.append("资金净流出")

        # Timing pattern matching
        action: ActionType
        confidence: float
        urgency: str

        if has_golden_cross and has_volume_spike and has_capital_inflow:
            # Triple confirmation → immediate entry
            action = ActionType.BUY
            confidence = 0.9
            urgency = "immediate"
            reasons.insert(0, "三重共振(金叉+放量+资金流入)，立即入场")
        elif has_golden_cross and has_volume_spike:
            # Double confirmation → strong
            action = ActionType.BUY
            confidence = 0.7
            urgency = "strong"
            reasons.insert(0, "双重确认(金叉+放量)，建议近期入场")
        elif has_golden_cross:
            # Single signal → opportunistic
            action = ActionType.BUY
            confidence = 0.5
            urgency = "opportunistic"
            reasons.insert(0, "单一金叉信号，可择机入场")
        elif has_death_cross and has_volume_spike:
            # Urgent exit
            action = ActionType.SELL
            confidence = 0.8
            urgency = "immediate"
            reasons.insert(0, "死叉+放量，建议立即离场")
        elif has_death_cross and has_capital_outflow:
            # Capital confirming exit
            action = ActionType.SELL
            confidence = 0.75
            urgency = "strong"
            reasons.insert(0, "死叉+资金流出，建议尽快离场")
        elif has_death_cross:
            action = ActionType.REDUCE_POSITION
            confidence = 0.55
            urgency = "normal"
            reasons.insert(0, "死叉信号，建议逐步减仓")
        else:
            # No clear timing signal
            return None, "none"

        # Apply bear market override: downgrade all BUY to WATCH
        if self._bear_market_override and action == ActionType.BUY:
            action = ActionType.WATCH
            confidence = min(confidence, 0.5)
            urgency = "deferred"
            reasons.append("(空头市场限制，买入降级为观察)")

        # Deduplicate reasons
        unique_reasons = list(dict.fromkeys(reasons))

        signal = StockSignal(
            ts_code=ts_code,
            action=action,
            confidence=confidence,
            reasons=unique_reasons,
        )

        return signal, urgency
