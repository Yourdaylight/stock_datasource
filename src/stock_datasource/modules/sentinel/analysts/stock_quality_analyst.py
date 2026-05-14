"""Stock Quality Analyst - evaluates individual stock signal quality and generates actions."""

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


class StockQualityAnalyst(BaseAnalyst):
    """Evaluates individual stock signals and produces actionable stock signals.

    Pattern recognition:
    - golden_cross + volume_spike → strong BUY (confidence 0.8)
    - death_cross + volume_spike → urgent SELL (confidence 0.85)
    - golden_cross alone → BUY (confidence 0.6)
    - pool_entry → WATCH (confidence 0.4)
    - pool_exit → REDUCE_POSITION (confidence 0.5)

    Enriches signals with signal_aggregator composite score when possible.
    """

    ANALYST_TYPE: str = "stock_quality"
    SUBSCRIBED_PATTERNS: list[str] = [
        "sentinel:ma_crossover:*",
        "sentinel:volume_anomaly:*",
        "sentinel:financial_anomaly",
        "sentinel:pool_change",
    ]
    MIN_ALERTS_TO_ANALYZE: int = 1  # Single stock signals can be actionable

    def get_analysis_description(self) -> str:
        return "评估个股信号质量，综合技术面、量价、资金池变动产生交易建议"

    async def analyze(self, alerts: list[SentinelAlert]) -> AnalystReport | None:
        """Group alerts by stock and evaluate each stock's signal combination."""
        # Group alerts by ts_code
        stock_alerts: dict[str, list[SentinelAlert]] = defaultdict(list)
        unassigned: list[SentinelAlert] = []

        for alert in alerts:
            if alert.ts_code:
                stock_alerts[alert.ts_code].append(alert)
            else:
                unassigned.append(alert)

        if not stock_alerts:
            return None

        stock_signals: list[StockSignal] = []
        insights: list[AnalystInsight] = []

        for ts_code, stock_alert_list in stock_alerts.items():
            signal = await self._evaluate_stock(ts_code, stock_alert_list)
            if signal:
                stock_signals.append(signal)

                # Generate insight for high-confidence signals
                if signal.confidence >= 0.7:
                    insights.append(AnalystInsight(
                        insight_type="high_confidence_signal",
                        description=(
                            f"{ts_code} 出现高置信度 {signal.action.value} 信号 "
                            f"(置信度: {signal.confidence:.0%}): "
                            f"{', '.join(signal.reasons)}"
                        ),
                        confidence=signal.confidence,
                        supporting_alerts=[a.alert_id for a in stock_alert_list],
                        related_stocks=[ts_code],
                    ))

        if not stock_signals:
            return None

        # Calculate overall conviction from best signal
        max_confidence = max(s.confidence for s in stock_signals)
        overall_conviction = min(
            0.3 + max_confidence * 0.6 + len(stock_signals) * 0.05,
            0.95,
        )

        return AnalystReport(
            analyst_type=self.ANALYST_TYPE,
            stock_signals=stock_signals,
            insights=insights,
            overall_conviction=overall_conviction,
        )

    async def _evaluate_stock(
        self, ts_code: str, alerts: list[SentinelAlert]
    ) -> StockSignal | None:
        """Evaluate a single stock based on its alerts and produce a signal."""
        # Classify alert types present
        has_golden_cross = False
        has_death_cross = False
        has_volume_spike = False
        has_pool_entry = False
        has_pool_exit = False
        has_financial_anomaly = False

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
                reasons.append("放量异动")
            elif alert.category == AlertCategory.VOLUME:
                has_volume_spike = True
                reasons.append("成交量异常")

            if "pool_entry" in signal_type or "pool_add" in signal_type:
                has_pool_entry = True
                reasons.append("进入股票池")
            elif "pool_exit" in signal_type or "pool_remove" in signal_type:
                has_pool_exit = True
                reasons.append("退出股票池")

            if alert.category == AlertCategory.FINANCIAL:
                has_financial_anomaly = True
                reasons.append("财务异常")

        # Pattern matching with confidence scoring
        action: ActionType
        confidence: float

        if has_death_cross and has_volume_spike:
            # Urgent SELL pattern
            action = ActionType.SELL
            confidence = 0.85
            reasons.insert(0, "死叉+放量，强卖出信号")
        elif has_golden_cross and has_volume_spike:
            # Strong BUY pattern
            action = ActionType.BUY
            confidence = 0.8
            reasons.insert(0, "金叉+放量，强买入信号")
        elif has_golden_cross:
            # BUY pattern (alone)
            action = ActionType.BUY
            confidence = 0.6
        elif has_death_cross:
            # SELL pattern (alone)
            action = ActionType.SELL
            confidence = 0.6
        elif has_pool_exit:
            # REDUCE pattern
            action = ActionType.REDUCE_POSITION
            confidence = 0.5
        elif has_pool_entry:
            # WATCH pattern
            action = ActionType.WATCH
            confidence = 0.4
        elif has_financial_anomaly:
            # Financial anomaly → AVOID
            action = ActionType.AVOID
            confidence = 0.6
            reasons.append("财务数据异常，建议回避")
        else:
            # Not enough evidence for a clear signal
            return None

        # Try to enrich with signal_aggregator composite score
        enriched_confidence = await self._enrich_with_composite_score(
            ts_code, confidence
        )

        # Deduplicate reasons
        unique_reasons = list(dict.fromkeys(reasons))

        return StockSignal(
            ts_code=ts_code,
            action=action,
            confidence=enriched_confidence,
            reasons=unique_reasons,
        )

    async def _enrich_with_composite_score(
        self, ts_code: str, base_confidence: float
    ) -> float:
        """Enrich confidence with signal aggregator composite score."""
        try:
            from stock_datasource.modules.signal_aggregator.service import (
                get_signal_aggregator,
            )

            aggregator = get_signal_aggregator()
            result = await aggregator.aggregate_for_stocks([ts_code])

            if result and result.scores:
                score = result.scores[0]
                composite = score.composite_score if hasattr(score, "composite_score") else 0
                # Blend base confidence with composite score
                if composite > 0:
                    # Normalize composite score (typically 0-100) to 0-1
                    normalized = min(composite / 100.0, 1.0)
                    # Weighted blend: 70% pattern-based, 30% aggregator
                    return base_confidence * 0.7 + normalized * 0.3

        except Exception as e:
            logger.debug("Could not enrich with composite score for %s: %s", ts_code, e)

        return base_confidence
