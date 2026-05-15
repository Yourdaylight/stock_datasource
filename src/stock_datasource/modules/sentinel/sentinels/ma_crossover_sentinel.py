"""MA Crossover Sentinel - monitors MA25/MA120 crossovers for core pool stocks."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class MACrossoverSentinel(BaseSentinel):
    """Monitors MA25/MA120 crossovers for stocks in the core pool.

    Triggers:
    - Golden cross: MA25 crosses above MA120 (bullish)
    - Death cross: MA25 crosses below MA120 (bearish)
    """

    SENTINEL_TYPE: str = "ma_crossover"
    CATEGORY: AlertCategory = AlertCategory.TECHNICAL

    def get_monitoring_description(self) -> str:
        return "监控核心池股票的MA25/MA120均线交叉信号，识别趋势转换"

    async def scan(self) -> list[SentinelAlert]:
        """Scan core pool stocks for MA25/MA120 crossovers."""
        alerts: list[SentinelAlert] = []

        try:
            # Get current core pool stocks
            pool_sql = """
                SELECT ts_code, stock_name
                FROM quant_core_pool
                WHERE update_date = (SELECT max(update_date) FROM quant_core_pool)
            """
            pool_df = db_client.execute_query(pool_sql)

            if pool_df is None or len(pool_df) == 0:
                logger.warning("MACrossoverSentinel: 核心池为空，跳过扫描")
                return []

            ts_codes = pool_df["ts_code"].tolist()
            stock_name_map = dict(zip(pool_df["ts_code"], pool_df["stock_name"]))

            # Batch query: get last 125 days of daily bars for all pool stocks
            codes_str = "', '".join(ts_codes)
            bar_sql = f"""
                SELECT ts_code, trade_date, close
                FROM fact_daily_bar
                WHERE ts_code IN ('{codes_str}')
                ORDER BY ts_code, trade_date DESC
                LIMIT 125 BY ts_code
            """
            bar_df = db_client.execute_query(bar_sql)

            if bar_df is None or len(bar_df) == 0:
                return []

            # Process each stock
            for ts_code in ts_codes:
                stock_data = bar_df[bar_df["ts_code"] == ts_code].copy()
                if len(stock_data) < 120:
                    continue

                stock_data = stock_data.sort_values("trade_date").reset_index(drop=True)

                # Calculate MAs
                stock_data["ma25"] = stock_data["close"].rolling(window=25).mean()
                stock_data["ma120"] = stock_data["close"].rolling(window=120).mean()

                # Need at least 2 valid rows
                valid = stock_data.dropna(subset=["ma25", "ma120"])
                if len(valid) < 2:
                    continue

                latest = valid.iloc[-1]
                previous = valid.iloc[-2]

                curr_ma25 = float(latest["ma25"])
                curr_ma120 = float(latest["ma120"])
                prev_ma25 = float(previous["ma25"])
                prev_ma120 = float(previous["ma120"])

                stock_name = stock_name_map.get(ts_code, ts_code)

                # Golden cross: MA25 crosses above MA120
                if curr_ma25 > curr_ma120 and prev_ma25 <= prev_ma120:
                    deviation = (curr_ma25 - curr_ma120) / curr_ma120 * 100
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.WARNING,
                        ts_code=ts_code,
                        signal_type="golden_cross_ma25_ma120",
                        description=f"{stock_name}({ts_code}) MA25上穿MA120形成金叉，"
                                    f"MA25={curr_ma25:.2f}，MA120={curr_ma120:.2f}，趋势可能转多",
                        metric_name="ma25_ma120_diff",
                        metric_value=curr_ma25,
                        threshold=curr_ma120,
                        deviation_pct=deviation,
                        context={
                            "trade_date": str(latest["trade_date"]),
                            "stock_name": stock_name,
                            "close": float(latest["close"]),
                            "ma25": curr_ma25,
                            "ma120": curr_ma120,
                            "signal": "golden_cross",
                        },
                    ))

                # Death cross: MA25 crosses below MA120
                elif curr_ma25 < curr_ma120 and prev_ma25 >= prev_ma120:
                    deviation = (curr_ma25 - curr_ma120) / curr_ma120 * 100
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.CRITICAL,
                        ts_code=ts_code,
                        signal_type="death_cross_ma25_ma120",
                        description=f"{stock_name}({ts_code}) MA25下穿MA120形成死叉，"
                                    f"MA25={curr_ma25:.2f}，MA120={curr_ma120:.2f}，趋势可能转空",
                        metric_name="ma25_ma120_diff",
                        metric_value=curr_ma25,
                        threshold=curr_ma120,
                        deviation_pct=deviation,
                        context={
                            "trade_date": str(latest["trade_date"]),
                            "stock_name": stock_name,
                            "close": float(latest["close"]),
                            "ma25": curr_ma25,
                            "ma120": curr_ma120,
                            "signal": "death_cross",
                        },
                    ))

        except Exception as e:
            logger.error(f"MACrossoverSentinel scan error: {e}", exc_info=True)

        return alerts
