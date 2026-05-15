"""Capital Flow Sentinel - monitors institutional, hot money, and northbound capital flows."""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class CapitalFlowSentinel(BaseSentinel):
    """Monitors per-stock capital flow from institutions and northbound channels.

    Triggers:
    - Net institutional buy exceeds threshold
    - Northbound flow reversal (significant change in direction)
    """

    SENTINEL_TYPE: str = "capital_flow"
    CATEGORY: AlertCategory = AlertCategory.CAPITAL

    def get_monitoring_description(self) -> str:
        return "监控核心池股票的机构资金和北向资金异动，识别主力资金进出信号"

    async def scan(self) -> list[SentinelAlert]:
        """Scan capital flow data for core pool stocks."""
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
                logger.warning("CapitalFlowSentinel: 核心池为空，跳过扫描")
                return []

            ts_codes = pool_df["ts_code"].tolist()
            stock_name_map = dict(zip(pool_df["ts_code"], pool_df["stock_name"]))
            codes_str = "', '".join(ts_codes)

            # Check institutional net buy
            alerts.extend(self._check_institutional_flow(codes_str, ts_codes, stock_name_map))

            # Check northbound flow
            alerts.extend(self._check_northbound_flow(codes_str, ts_codes, stock_name_map))

        except Exception as e:
            logger.error(f"CapitalFlowSentinel scan error: {e}", exc_info=True)

        return alerts

    def _check_institutional_flow(
        self, codes_str: str, ts_codes: list[str], stock_name_map: dict
    ) -> list[SentinelAlert]:
        """Check for significant institutional net buying/selling."""
        alerts: list[SentinelAlert] = []

        try:
            inst_sql = f"""
                SELECT ts_code, trade_date, net_buy
                FROM ods_top_inst
                WHERE ts_code IN ('{codes_str}')
                ORDER BY ts_code, trade_date DESC
                LIMIT 10 BY ts_code
            """
            inst_df = db_client.execute_query(inst_sql)

            if inst_df is None or len(inst_df) == 0:
                return []

            for ts_code in ts_codes:
                stock_data = inst_df[inst_df["ts_code"] == ts_code]
                if len(stock_data) == 0:
                    continue

                stock_data = stock_data.sort_values("trade_date")
                stock_name = stock_name_map.get(ts_code, ts_code)

                net_buys = stock_data["net_buy"].astype(float).values
                latest_buy = float(net_buys[-1])
                latest_date = str(stock_data.iloc[-1]["trade_date"])

                # Calculate historical stats
                if len(net_buys) >= 3:
                    hist_mean = float(np.mean(net_buys[:-1]))
                    hist_std = float(np.std(net_buys[:-1]))

                    if hist_std > 0:
                        z_score = (latest_buy - hist_mean) / hist_std
                    else:
                        z_score = 0
                else:
                    z_score = 0
                    hist_mean = 0

                # Significant institutional net buy (z > 2)
                if z_score > 2.0 and latest_buy > 0:
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.WARNING,
                        ts_code=ts_code,
                        signal_type="inst_heavy_buy",
                        description=f"{stock_name}({ts_code}) 机构大幅净买入{latest_buy:.0f}万，"
                                    f"为近期均值的{z_score:.1f}个标准差，主力可能进场",
                        metric_name="inst_net_buy",
                        metric_value=latest_buy,
                        threshold=hist_mean + 2.0 * hist_std if hist_std > 0 else latest_buy,
                        deviation_pct=z_score * 50,
                        context={
                            "trade_date": latest_date,
                            "stock_name": stock_name,
                            "net_buy": latest_buy,
                            "z_score": round(z_score, 2),
                            "direction": "buy",
                        },
                    ))

                # Significant institutional net sell (z < -2)
                elif z_score < -2.0 and latest_buy < 0:
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.WARNING,
                        ts_code=ts_code,
                        signal_type="inst_heavy_sell",
                        description=f"{stock_name}({ts_code}) 机构大幅净卖出{abs(latest_buy):.0f}万，"
                                    f"偏离均值{abs(z_score):.1f}个标准差，主力可能离场",
                        metric_name="inst_net_buy",
                        metric_value=latest_buy,
                        threshold=hist_mean - 2.0 * hist_std if hist_std > 0 else latest_buy,
                        deviation_pct=z_score * 50,
                        context={
                            "trade_date": latest_date,
                            "stock_name": stock_name,
                            "net_buy": latest_buy,
                            "z_score": round(z_score, 2),
                            "direction": "sell",
                        },
                    ))

        except Exception as e:
            logger.debug(f"CapitalFlowSentinel institutional check error: {e}")

        return alerts

    def _check_northbound_flow(
        self, codes_str: str, ts_codes: list[str], stock_name_map: dict
    ) -> list[SentinelAlert]:
        """Check for northbound capital flow reversals."""
        alerts: list[SentinelAlert] = []

        try:
            hsgt_sql = f"""
                SELECT ts_code, trade_date, vol
                FROM ods_hsgt_top10
                WHERE ts_code IN ('{codes_str}')
                ORDER BY ts_code, trade_date DESC
                LIMIT 10 BY ts_code
            """
            hsgt_df = db_client.execute_query(hsgt_sql)

            if hsgt_df is None or len(hsgt_df) == 0:
                return []

            for ts_code in ts_codes:
                stock_data = hsgt_df[hsgt_df["ts_code"] == ts_code]
                if len(stock_data) < 5:
                    continue

                stock_data = stock_data.sort_values("trade_date")
                stock_name = stock_name_map.get(ts_code, ts_code)

                vols = stock_data["vol"].astype(float).values
                latest_date = str(stock_data.iloc[-1]["trade_date"])

                # Check for flow reversal: last 3 days vs previous 3 days
                if len(vols) >= 6:
                    recent_avg = float(np.mean(vols[-3:]))
                    prev_avg = float(np.mean(vols[-6:-3]))

                    if prev_avg == 0:
                        continue

                    change_pct = (recent_avg - prev_avg) / abs(prev_avg) * 100

                    # Significant northbound flow increase
                    if change_pct > 100:
                        alerts.append(SentinelAlert(
                            sentinel_type=self.SENTINEL_TYPE,
                            category=self.CATEGORY,
                            severity=AlertSeverity.WARNING,
                            ts_code=ts_code,
                            signal_type="northbound_flow_surge",
                            description=f"{stock_name}({ts_code}) 北向资金近3日大幅增持，"
                                        f"较前期增加{change_pct:.0f}%，外资看好",
                            metric_name="northbound_flow_change",
                            metric_value=recent_avg,
                            threshold=prev_avg,
                            deviation_pct=change_pct,
                            context={
                                "trade_date": latest_date,
                                "stock_name": stock_name,
                                "recent_avg_vol": round(recent_avg, 2),
                                "prev_avg_vol": round(prev_avg, 2),
                                "change_pct": round(change_pct, 1),
                                "direction": "increase",
                            },
                        ))

                    # Significant northbound flow decrease / reversal
                    elif change_pct < -50 and prev_avg > 0:
                        alerts.append(SentinelAlert(
                            sentinel_type=self.SENTINEL_TYPE,
                            category=self.CATEGORY,
                            severity=AlertSeverity.WARNING,
                            ts_code=ts_code,
                            signal_type="northbound_flow_reversal",
                            description=f"{stock_name}({ts_code}) 北向资金近3日大幅减持，"
                                        f"较前期减少{abs(change_pct):.0f}%，外资可能撤退",
                            metric_name="northbound_flow_change",
                            metric_value=recent_avg,
                            threshold=prev_avg,
                            deviation_pct=change_pct,
                            context={
                                "trade_date": latest_date,
                                "stock_name": stock_name,
                                "recent_avg_vol": round(recent_avg, 2),
                                "prev_avg_vol": round(prev_avg, 2),
                                "change_pct": round(change_pct, 1),
                                "direction": "decrease",
                            },
                        ))

        except Exception as e:
            logger.debug(f"CapitalFlowSentinel northbound check error: {e}")

        return alerts
