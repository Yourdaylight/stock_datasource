"""Sector Flow Sentinel - monitors sector-level capital flow anomalies."""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class SectorFlowSentinel(BaseSentinel):
    """Monitors sector-level capital flow aggregated from institutional and hot money data.

    Triggers:
    - Daily sector flow exceeds historical 2-sigma
    - Sudden rank change in sector flow ranking
    """

    SENTINEL_TYPE: str = "sector_flow"
    CATEGORY: AlertCategory = AlertCategory.SECTOR_FLOW

    def get_monitoring_description(self) -> str:
        return "监控行业板块资金流向，识别异常资金集中流入或流出的行业"

    async def scan(self) -> list[SentinelAlert]:
        """Scan sector-level capital flows for anomalies."""
        alerts: list[SentinelAlert] = []

        try:
            # Get institutional net buy aggregated by industry over the last 30 days
            sql = """
                SELECT
                    b.industry,
                    t.trade_date,
                    sum(t.net_buy) AS sector_net_buy
                FROM ods_top_inst t
                INNER JOIN dim_stock_basic b ON t.ts_code = b.ts_code
                WHERE t.trade_date >= toString(addDays(today(), -30))
                GROUP BY b.industry, t.trade_date
                ORDER BY b.industry, t.trade_date
            """
            df_inst = db_client.execute_query(sql)

            # Get hot money (dragon-tiger list) aggregated by industry
            sql_hot = """
                SELECT
                    b.industry,
                    t.trade_date,
                    count(*) AS list_count,
                    sum(t.exalter) AS sector_exalter
                FROM ods_top_list t
                INNER JOIN dim_stock_basic b ON t.ts_code = b.ts_code
                WHERE t.trade_date >= toString(addDays(today(), -30))
                GROUP BY b.industry, t.trade_date
                ORDER BY b.industry, t.trade_date
            """
            df_hot = db_client.execute_query(sql_hot)

            # Process institutional flow by sector
            if df_inst is not None and len(df_inst) > 0:
                alerts.extend(self._check_inst_flow_anomalies(df_inst))

            # Process hot money flow by sector
            if df_hot is not None and len(df_hot) > 0:
                alerts.extend(self._check_hot_money_anomalies(df_hot))

        except Exception as e:
            logger.error(f"SectorFlowSentinel scan error: {e}", exc_info=True)

        return alerts

    def _check_inst_flow_anomalies(self, df) -> list[SentinelAlert]:
        """Check for institutional flow exceeding 2-sigma by sector."""
        alerts: list[SentinelAlert] = []

        for industry, group in df.groupby("industry"):
            if industry is None or len(group) < 5:
                continue

            group = group.sort_values("trade_date")
            values = group["sector_net_buy"].astype(float).values

            # Calculate statistics
            mean_flow = np.mean(values[:-1]) if len(values) > 1 else 0
            std_flow = np.std(values[:-1]) if len(values) > 1 else 0
            latest_flow = float(values[-1])
            latest_date = str(group.iloc[-1]["trade_date"])

            if std_flow == 0:
                continue

            z_score = (latest_flow - mean_flow) / std_flow

            if abs(z_score) > 2.0:
                direction = "流入" if z_score > 0 else "流出"
                severity = AlertSeverity.CRITICAL if abs(z_score) > 3.0 else AlertSeverity.WARNING

                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=severity,
                    sector_code=str(industry),
                    signal_type="sector_inst_flow_anomaly",
                    description=f"{industry}板块机构资金异常{direction}，"
                                f"当日净买入{latest_flow:.0f}万，偏离均值{z_score:.1f}个标准差",
                    metric_name="sector_inst_net_buy",
                    metric_value=latest_flow,
                    threshold=mean_flow + 2.0 * std_flow if z_score > 0 else mean_flow - 2.0 * std_flow,
                    deviation_pct=z_score * 100 / 2.0,
                    context={
                        "trade_date": latest_date,
                        "industry": str(industry),
                        "z_score": round(z_score, 2),
                        "mean_flow": round(mean_flow, 2),
                        "std_flow": round(std_flow, 2),
                        "direction": "inflow" if z_score > 0 else "outflow",
                    },
                ))

        return alerts

    def _check_hot_money_anomalies(self, df) -> list[SentinelAlert]:
        """Check for hot money concentration anomalies by sector."""
        alerts: list[SentinelAlert] = []

        for industry, group in df.groupby("industry"):
            if industry is None or len(group) < 5:
                continue

            group = group.sort_values("trade_date")
            counts = group["list_count"].astype(float).values

            mean_count = np.mean(counts[:-1]) if len(counts) > 1 else 0
            std_count = np.std(counts[:-1]) if len(counts) > 1 else 0
            latest_count = float(counts[-1])
            latest_date = str(group.iloc[-1]["trade_date"])

            if std_count == 0 or mean_count == 0:
                continue

            z_score = (latest_count - mean_count) / std_count

            if z_score > 2.0:
                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.WARNING,
                    sector_code=str(industry),
                    signal_type="sector_hot_money_surge",
                    description=f"{industry}板块游资活跃度异常升高，"
                                f"当日龙虎榜上榜{int(latest_count)}次，历史均值{mean_count:.1f}次",
                    metric_name="sector_hot_money_count",
                    metric_value=latest_count,
                    threshold=mean_count + 2.0 * std_count,
                    deviation_pct=(latest_count - mean_count) / mean_count * 100,
                    context={
                        "trade_date": latest_date,
                        "industry": str(industry),
                        "z_score": round(z_score, 2),
                        "list_count": int(latest_count),
                    },
                ))

        return alerts
