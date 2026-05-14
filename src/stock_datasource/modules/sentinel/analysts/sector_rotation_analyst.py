"""Sector Rotation Analyst - detects convergent sector-level patterns."""

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


class SectorRotationAnalyst(BaseAnalyst):
    """Detects sector rotation patterns from multiple convergent signals.

    Pattern detection:
    - Multiple stocks in same sector with bullish signals → sector bullish
    - Multiple stocks in same sector with bearish signals → sector bearish
    - Only escalates when convergent patterns found (>=2 signals per sector)
    """

    ANALYST_TYPE: str = "sector_rotation"
    SUBSCRIBED_PATTERNS: list[str] = [
        "sentinel:sector_flow",
        "sentinel:capital_flow:*",
        "sentinel:rps_breakout",
    ]
    MIN_ALERTS_TO_ANALYZE: int = 3

    def get_analysis_description(self) -> str:
        return "分析板块轮动信号，识别资金集中流入/流出的板块趋势"

    async def analyze(self, alerts: list[SentinelAlert]) -> AnalystReport | None:
        """Group alerts by sector and detect convergent patterns."""
        # Group alerts by sector
        sector_alerts: dict[str, list[SentinelAlert]] = defaultdict(list)

        for alert in alerts:
            sector = self._extract_sector(alert)
            if sector:
                sector_alerts[sector].append(alert)

        if not sector_alerts:
            return None

        # Analyze each sector for convergent signals
        sector_view: dict[str, str] = {}
        insights: list[AnalystInsight] = []
        stock_signals: list[StockSignal] = []
        has_convergent_pattern = False

        for sector, sector_alert_list in sector_alerts.items():
            if len(sector_alert_list) < 2:
                # Not enough signals for convergence
                continue

            bullish_count = 0
            bearish_count = 0
            related_stocks: list[str] = []

            for alert in sector_alert_list:
                direction = self._classify_signal_direction(alert)
                if direction == "bullish":
                    bullish_count += 1
                elif direction == "bearish":
                    bearish_count += 1

                if alert.ts_code and alert.ts_code not in related_stocks:
                    related_stocks.append(alert.ts_code)

            # Determine sector view
            if bullish_count >= 2 and bullish_count > bearish_count:
                sector_view[sector] = "bullish"
                has_convergent_pattern = True
                insights.append(AnalystInsight(
                    insight_type="sector_bullish_convergence",
                    description=(
                        f"板块 {sector} 出现多信号看多共振: "
                        f"{bullish_count}个看多信号 vs {bearish_count}个看空信号"
                    ),
                    confidence=min(0.5 + bullish_count * 0.1, 0.9),
                    supporting_alerts=[a.alert_id for a in sector_alert_list],
                    related_stocks=related_stocks,
                ))
                # Generate WATCH signals for related stocks
                for ts_code in related_stocks:
                    stock_signals.append(StockSignal(
                        ts_code=ts_code,
                        action=ActionType.WATCH,
                        confidence=min(0.4 + bullish_count * 0.1, 0.7),
                        reasons=[f"所属板块 {sector} 资金流入共振"],
                    ))

            elif bearish_count >= 2 and bearish_count > bullish_count:
                sector_view[sector] = "bearish"
                has_convergent_pattern = True
                insights.append(AnalystInsight(
                    insight_type="sector_bearish_convergence",
                    description=(
                        f"板块 {sector} 出现多信号看空共振: "
                        f"{bearish_count}个看空信号 vs {bullish_count}个看多信号"
                    ),
                    confidence=min(0.5 + bearish_count * 0.1, 0.9),
                    supporting_alerts=[a.alert_id for a in sector_alert_list],
                    related_stocks=related_stocks,
                ))
                # Generate REDUCE signals for related stocks
                for ts_code in related_stocks:
                    stock_signals.append(StockSignal(
                        ts_code=ts_code,
                        action=ActionType.REDUCE_POSITION,
                        confidence=min(0.4 + bearish_count * 0.1, 0.7),
                        reasons=[f"所属板块 {sector} 资金流出共振"],
                    ))
            else:
                sector_view[sector] = "neutral"

        if not has_convergent_pattern:
            return None

        # Calculate overall conviction based on pattern strength
        conviction = min(
            0.4 + len(insights) * 0.15,
            0.9,
        )

        return AnalystReport(
            analyst_type=self.ANALYST_TYPE,
            sector_view=sector_view,
            stock_signals=stock_signals,
            insights=insights,
            overall_conviction=conviction,
        )

    def _extract_sector(self, alert: SentinelAlert) -> str | None:
        """Extract sector identifier from alert."""
        if alert.sector_code:
            return alert.sector_code
        sector = alert.context.get("sector")
        if sector:
            return sector
        sector_name = alert.context.get("sector_name")
        if sector_name:
            return sector_name
        return None

    def _classify_signal_direction(self, alert: SentinelAlert) -> str:
        """Classify whether an alert signal is bullish or bearish."""
        signal = alert.signal_type.lower()
        description = alert.description.lower()
        context = alert.context

        # Bullish signals
        bullish_keywords = [
            "inflow", "流入", "买入", "golden_cross", "breakout",
            "rps_breakout", "bullish", "看多", "增持",
        ]
        for kw in bullish_keywords:
            if kw in signal or kw in description:
                return "bullish"

        # Bearish signals
        bearish_keywords = [
            "outflow", "流出", "卖出", "death_cross", "breakdown",
            "bearish", "看空", "减持",
        ]
        for kw in bearish_keywords:
            if kw in signal or kw in description:
                return "bearish"

        # Check context direction
        direction = context.get("direction", "")
        if direction in ("bullish", "up", "inflow"):
            return "bullish"
        elif direction in ("bearish", "down", "outflow"):
            return "bearish"

        # Check metric value vs threshold for capital flow
        if alert.category == AlertCategory.CAPITAL:
            if alert.metric_value > alert.threshold:
                return "bullish"
            elif alert.metric_value < -alert.threshold:
                return "bearish"

        return "neutral"
