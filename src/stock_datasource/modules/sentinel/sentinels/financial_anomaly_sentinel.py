"""Financial Anomaly Sentinel - monitors quarterly financial data for surprises."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class FinancialAnomalySentinel(BaseSentinel):
    """Monitors financial indicator data for anomalies and earnings surprises.

    Triggers:
    - New quarterly report detected (new end_date appears)
    - Revenue surprise: revenue_yoy > 30% change vs prior quarter's yoy
    - Profit surprise: netprofit_yoy > 30% change vs prior quarter's yoy
    """

    SENTINEL_TYPE: str = "financial_anomaly"
    CATEGORY: AlertCategory = AlertCategory.FINANCIAL

    def get_monitoring_description(self) -> str:
        return "监控核心池股票的财务数据异动，识别业绩超预期或低于预期的信号"

    async def scan(self) -> list[SentinelAlert]:
        """Scan financial indicators for surprises."""
        alerts: list[SentinelAlert] = []

        try:
            # Get current core pool
            pool_sql = """
                SELECT ts_code, stock_name
                FROM quant_core_pool
                WHERE update_date = (SELECT max(update_date) FROM quant_core_pool)
            """
            pool_df = db_client.execute_query(pool_sql)

            if pool_df is None or len(pool_df) == 0:
                logger.warning("FinancialAnomalySentinel: 核心池为空，跳过扫描")
                return []

            ts_codes = pool_df["ts_code"].tolist()
            stock_name_map = dict(zip(pool_df["ts_code"], pool_df["stock_name"]))
            codes_str = "', '".join(ts_codes)

            # Get the latest 2 quarters of financial data for pool stocks
            fina_sql = f"""
                SELECT ts_code, end_date, roe, revenue_yoy, netprofit_yoy
                FROM fact_fina_indicator
                WHERE ts_code IN ('{codes_str}')
                ORDER BY ts_code, end_date DESC
                LIMIT 2 BY ts_code
            """
            fina_df = db_client.execute_query(fina_sql)

            if fina_df is None or len(fina_df) == 0:
                return []

            # Process each stock
            for ts_code in ts_codes:
                stock_data = fina_df[fina_df["ts_code"] == ts_code].copy()
                if len(stock_data) == 0:
                    continue

                stock_data = stock_data.sort_values("end_date", ascending=False).reset_index(drop=True)
                stock_name = stock_name_map.get(ts_code, ts_code)

                latest = stock_data.iloc[0]
                latest_end_date = str(latest["end_date"])
                latest_revenue_yoy = self._safe_float(latest.get("revenue_yoy"))
                latest_netprofit_yoy = self._safe_float(latest.get("netprofit_yoy"))
                latest_roe = self._safe_float(latest.get("roe"))

                # If we have two quarters, check for surprises
                if len(stock_data) >= 2:
                    previous = stock_data.iloc[1]
                    prev_revenue_yoy = self._safe_float(previous.get("revenue_yoy"))
                    prev_netprofit_yoy = self._safe_float(previous.get("netprofit_yoy"))

                    # Revenue surprise: absolute change in yoy growth > 30pp
                    if latest_revenue_yoy is not None and prev_revenue_yoy is not None:
                        revenue_change = latest_revenue_yoy - prev_revenue_yoy
                        if abs(revenue_change) > 30:
                            direction = "加速" if revenue_change > 0 else "减速"
                            severity = (
                                AlertSeverity.CRITICAL if abs(revenue_change) > 50
                                else AlertSeverity.WARNING
                            )
                            alerts.append(SentinelAlert(
                                sentinel_type=self.SENTINEL_TYPE,
                                category=self.CATEGORY,
                                severity=severity,
                                ts_code=ts_code,
                                signal_type="revenue_surprise",
                                description=f"{stock_name}({ts_code}) 营收增速大幅{direction}，"
                                            f"最新营收同比{latest_revenue_yoy:.1f}%，"
                                            f"上季{prev_revenue_yoy:.1f}%，变化{revenue_change:+.1f}pp",
                                metric_name="revenue_yoy_change",
                                metric_value=latest_revenue_yoy,
                                threshold=prev_revenue_yoy,
                                deviation_pct=revenue_change,
                                context={
                                    "end_date": latest_end_date,
                                    "stock_name": stock_name,
                                    "revenue_yoy": latest_revenue_yoy,
                                    "prev_revenue_yoy": prev_revenue_yoy,
                                    "change_pp": round(revenue_change, 1),
                                    "direction": "accelerate" if revenue_change > 0 else "decelerate",
                                },
                            ))

                    # Profit surprise: absolute change in yoy growth > 30pp
                    if latest_netprofit_yoy is not None and prev_netprofit_yoy is not None:
                        profit_change = latest_netprofit_yoy - prev_netprofit_yoy
                        if abs(profit_change) > 30:
                            direction = "加速" if profit_change > 0 else "减速"
                            severity = (
                                AlertSeverity.CRITICAL if abs(profit_change) > 50
                                else AlertSeverity.WARNING
                            )
                            alerts.append(SentinelAlert(
                                sentinel_type=self.SENTINEL_TYPE,
                                category=self.CATEGORY,
                                severity=severity,
                                ts_code=ts_code,
                                signal_type="profit_surprise",
                                description=f"{stock_name}({ts_code}) 净利润增速大幅{direction}，"
                                            f"最新净利润同比{latest_netprofit_yoy:.1f}%，"
                                            f"上季{prev_netprofit_yoy:.1f}%，变化{profit_change:+.1f}pp",
                                metric_name="netprofit_yoy_change",
                                metric_value=latest_netprofit_yoy,
                                threshold=prev_netprofit_yoy,
                                deviation_pct=profit_change,
                                context={
                                    "end_date": latest_end_date,
                                    "stock_name": stock_name,
                                    "netprofit_yoy": latest_netprofit_yoy,
                                    "prev_netprofit_yoy": prev_netprofit_yoy,
                                    "change_pp": round(profit_change, 1),
                                    "roe": latest_roe,
                                    "direction": "accelerate" if profit_change > 0 else "decelerate",
                                },
                            ))

                # New quarterly report detection: check if end_date is very recent
                # (within last 7 days suggests a new report just appeared)
                try:
                    end_dt = datetime.strptime(latest_end_date[:10], "%Y-%m-%d") if "-" in latest_end_date else datetime.strptime(latest_end_date[:8], "%Y%m%d")
                    days_since = (datetime.now() - end_dt).days
                    # If the report end_date is within current quarter and very fresh
                    if days_since <= 45 and latest_roe is not None:
                        # This is likely a newly published report
                        alerts.append(SentinelAlert(
                            sentinel_type=self.SENTINEL_TYPE,
                            category=self.CATEGORY,
                            severity=AlertSeverity.INFO,
                            ts_code=ts_code,
                            signal_type="new_quarterly_report",
                            description=f"{stock_name}({ts_code}) 发布新季报(截至{latest_end_date})，"
                                        f"ROE={latest_roe:.2f}%，营收同比{latest_revenue_yoy or 0:.1f}%，"
                                        f"净利润同比{latest_netprofit_yoy or 0:.1f}%",
                            metric_name="roe",
                            metric_value=latest_roe if latest_roe else 0,
                            threshold=0,
                            deviation_pct=0,
                            context={
                                "end_date": latest_end_date,
                                "stock_name": stock_name,
                                "roe": latest_roe,
                                "revenue_yoy": latest_revenue_yoy,
                                "netprofit_yoy": latest_netprofit_yoy,
                                "signal": "new_report",
                            },
                        ))
                except (ValueError, TypeError):
                    pass

        except Exception as e:
            logger.error(f"FinancialAnomalySentinel scan error: {e}", exc_info=True)

        return alerts

    @staticmethod
    def _safe_float(value) -> float | None:
        """Safely convert value to float, return None if not possible."""
        if value is None:
            return None
        try:
            result = float(value)
            # Filter out NaN
            if result != result:  # NaN check
                return None
            return result
        except (ValueError, TypeError):
            return None
