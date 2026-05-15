"""RPS Breakout Sentinel - monitors RPS rank changes for momentum signals."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class RPSBreakoutSentinel(BaseSentinel):
    """Monitors RPS rank changes to identify momentum breakouts and breakdowns.

    Triggers:
    - Stock enters top-10 from below rank 50 (momentum breakout)
    - Stock drops from top-20 to below rank 50 (momentum breakdown)
    """

    SENTINEL_TYPE: str = "rps_breakout"
    CATEGORY: AlertCategory = AlertCategory.RPS

    def get_monitoring_description(self) -> str:
        return "监控股票RPS排名变化，识别动量突破和衰减信号"

    async def scan(self) -> list[SentinelAlert]:
        """Scan RPS rank changes for breakout/breakdown signals."""
        alerts: list[SentinelAlert] = []

        try:
            # Get the two most recent calculation dates
            date_sql = """
                SELECT DISTINCT calc_date
                FROM quant_rps_rank
                ORDER BY calc_date DESC
                LIMIT 2
            """
            date_df = db_client.execute_query(date_sql)

            if date_df is None or len(date_df) < 2:
                logger.warning("RPSBreakoutSentinel: RPS数据不足两期，跳过扫描")
                return []

            latest_date = str(date_df.iloc[0]["calc_date"])
            prev_date = str(date_df.iloc[1]["calc_date"])

            # Get latest RPS rankings
            latest_sql = f"""
                SELECT ts_code, rps_250
                FROM quant_rps_rank
                WHERE calc_date = '{latest_date}'
                ORDER BY rps_250 DESC
            """
            latest_df = db_client.execute_query(latest_sql)

            # Get previous RPS rankings
            prev_sql = f"""
                SELECT ts_code, rps_250
                FROM quant_rps_rank
                WHERE calc_date = '{prev_date}'
                ORDER BY rps_250 DESC
            """
            prev_df = db_client.execute_query(prev_sql)

            if latest_df is None or prev_df is None or len(latest_df) == 0 or len(prev_df) == 0:
                return []

            # Assign rank positions (1 = highest RPS)
            latest_df = latest_df.reset_index(drop=True)
            latest_df["rank"] = latest_df.index + 1
            prev_df = prev_df.reset_index(drop=True)
            prev_df["rank"] = prev_df.index + 1

            # Create lookup dicts
            latest_rank_map = dict(zip(latest_df["ts_code"], latest_df["rank"]))
            prev_rank_map = dict(zip(prev_df["ts_code"], prev_df["rank"]))
            latest_rps_map = dict(zip(latest_df["ts_code"], latest_df["rps_250"]))

            # Get stock names from core pool or basic info
            name_sql = """
                SELECT ts_code, name
                FROM dim_stock_basic
            """
            name_df = db_client.execute_query(name_sql)
            stock_name_map = {}
            if name_df is not None and len(name_df) > 0:
                stock_name_map = dict(zip(name_df["ts_code"], name_df["name"]))

            # Check for breakouts: entered top-10 from below rank 50
            for ts_code, curr_rank in latest_rank_map.items():
                prev_rank = prev_rank_map.get(ts_code)
                if prev_rank is None:
                    continue

                stock_name = stock_name_map.get(ts_code, ts_code)
                rps_value = float(latest_rps_map.get(ts_code, 0))

                # Breakout: entered top-10 from below rank 50
                if curr_rank <= 10 and prev_rank > 50:
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.WARNING,
                        ts_code=ts_code,
                        signal_type="rps_breakout_top10",
                        description=f"{stock_name}({ts_code}) RPS排名从第{prev_rank}名跃升至第{curr_rank}名，"
                                    f"进入前10强，RPS值={rps_value:.1f}，动量爆发",
                        metric_name="rps_rank",
                        metric_value=float(curr_rank),
                        threshold=10.0,
                        deviation_pct=(prev_rank - curr_rank) / prev_rank * 100,
                        context={
                            "calc_date": latest_date,
                            "stock_name": stock_name,
                            "current_rank": curr_rank,
                            "previous_rank": prev_rank,
                            "rps_250": rps_value,
                            "signal": "breakout",
                        },
                    ))

                # Breakdown: dropped from top-20 to below rank 50
                elif curr_rank > 50 and prev_rank <= 20:
                    alerts.append(SentinelAlert(
                        sentinel_type=self.SENTINEL_TYPE,
                        category=self.CATEGORY,
                        severity=AlertSeverity.WARNING,
                        ts_code=ts_code,
                        signal_type="rps_breakdown",
                        description=f"{stock_name}({ts_code}) RPS排名从第{prev_rank}名下滑至第{curr_rank}名，"
                                    f"跌出前20，RPS值={rps_value:.1f}，动量衰减",
                        metric_name="rps_rank",
                        metric_value=float(curr_rank),
                        threshold=50.0,
                        deviation_pct=(curr_rank - prev_rank) / prev_rank * 100,
                        context={
                            "calc_date": latest_date,
                            "stock_name": stock_name,
                            "current_rank": curr_rank,
                            "previous_rank": prev_rank,
                            "rps_250": rps_value,
                            "signal": "breakdown",
                        },
                    ))

        except Exception as e:
            logger.error(f"RPSBreakoutSentinel scan error: {e}", exc_info=True)

        return alerts
