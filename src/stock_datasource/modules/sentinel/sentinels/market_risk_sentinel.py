"""Market Risk Sentinel - monitors CSI300 vs MA250 for market-level risk signals."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class MarketRiskSentinel(BaseSentinel):
    """Monitors CSI300 (000300.SH) relative to MA250 for market regime shifts.

    Triggers:
    - Index crosses above MA250 (bullish signal)
    - Index crosses below MA250 (bearish signal)
    - Rapid deviation from MA250 exceeding 5% (overextension)
    """

    SENTINEL_TYPE: str = "market_risk"
    CATEGORY: AlertCategory = AlertCategory.MARKET_RISK

    def get_monitoring_description(self) -> str:
        return "监控沪深300指数与250日均线的关系，识别市场整体风险状态变化"

    async def scan(self) -> list[SentinelAlert]:
        """Scan CSI300 vs MA250 for risk signals."""
        alerts: list[SentinelAlert] = []

        try:
            # Fetch last 260 trading days of CSI300 index data
            sql = """
                SELECT ts_code, trade_date, close
                FROM fact_index_daily
                WHERE ts_code = '000300.SH'
                ORDER BY trade_date DESC
                LIMIT 260
            """
            df = db_client.execute_query(sql)

            if df is None or len(df) < 250:
                logger.warning("MarketRiskSentinel: 数据不足250条，跳过扫描")
                return []

            # Sort by date ascending for calculation
            df = df.sort_values("trade_date").reset_index(drop=True)

            # Calculate MA250
            df["ma250"] = df["close"].rolling(window=250).mean()

            # Get the latest two rows with valid MA250
            valid_df = df.dropna(subset=["ma250"])
            if len(valid_df) < 2:
                return []

            latest = valid_df.iloc[-1]
            previous = valid_df.iloc[-2]

            current_close = float(latest["close"])
            current_ma250 = float(latest["ma250"])
            prev_close = float(previous["close"])
            prev_ma250 = float(previous["ma250"])

            # Calculate deviation percentage
            deviation_pct = (current_close - current_ma250) / current_ma250 * 100

            # Check for crossover signals
            prev_above = prev_close > prev_ma250
            curr_above = current_close > current_ma250

            if curr_above and not prev_above:
                # Golden cross: index crossed above MA250
                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.WARNING,
                    index_code="000300.SH",
                    signal_type="ma250_golden_cross",
                    description=f"沪深300突破250日均线，收盘价{current_close:.2f}，MA250={current_ma250:.2f}，"
                                f"偏离度{deviation_pct:.2f}%，市场可能进入多头阶段",
                    metric_name="csi300_vs_ma250",
                    metric_value=current_close,
                    threshold=current_ma250,
                    deviation_pct=deviation_pct,
                    context={
                        "trade_date": str(latest["trade_date"]),
                        "close": current_close,
                        "ma250": current_ma250,
                        "signal": "bullish_crossover",
                    },
                ))

            elif not curr_above and prev_above:
                # Death cross: index crossed below MA250
                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.CRITICAL,
                    index_code="000300.SH",
                    signal_type="ma250_death_cross",
                    description=f"沪深300跌破250日均线，收盘价{current_close:.2f}，MA250={current_ma250:.2f}，"
                                f"偏离度{deviation_pct:.2f}%，市场可能进入空头阶段",
                    metric_name="csi300_vs_ma250",
                    metric_value=current_close,
                    threshold=current_ma250,
                    deviation_pct=deviation_pct,
                    context={
                        "trade_date": str(latest["trade_date"]),
                        "close": current_close,
                        "ma250": current_ma250,
                        "signal": "bearish_crossover",
                    },
                ))

            # Check for rapid deviation > 5%
            if abs(deviation_pct) > 5.0:
                direction = "上方" if deviation_pct > 0 else "下方"
                severity = AlertSeverity.WARNING if abs(deviation_pct) < 8.0 else AlertSeverity.CRITICAL
                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=severity,
                    index_code="000300.SH",
                    signal_type="ma250_extreme_deviation",
                    description=f"沪深300偏离250日均线过大，当前位于MA250{direction}，"
                                f"偏离度{deviation_pct:.2f}%，存在回归风险",
                    metric_name="ma250_deviation_pct",
                    metric_value=deviation_pct,
                    threshold=5.0,
                    deviation_pct=deviation_pct,
                    context={
                        "trade_date": str(latest["trade_date"]),
                        "close": current_close,
                        "ma250": current_ma250,
                        "direction": "above" if deviation_pct > 0 else "below",
                    },
                ))

        except Exception as e:
            logger.error(f"MarketRiskSentinel scan error: {e}", exc_info=True)

        return alerts
