"""Pool Change Sentinel - monitors core pool composition changes."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class PoolChangeSentinel(BaseSentinel):
    """Monitors the quant_core_pool table for composition changes.

    Compares the latest pool update vs the previous update to detect:
    - New stocks entering the core pool
    - Stocks exiting the core pool
    """

    SENTINEL_TYPE: str = "pool_change"
    CATEGORY: AlertCategory = AlertCategory.POOL_CHANGE

    def get_monitoring_description(self) -> str:
        return "监控核心股票池成分变化，识别新进入和退出核心池的股票"

    async def scan(self) -> list[SentinelAlert]:
        """Scan for core pool composition changes."""
        alerts: list[SentinelAlert] = []

        try:
            # Get the two most recent update dates
            date_sql = """
                SELECT DISTINCT update_date
                FROM quant_core_pool
                ORDER BY update_date DESC
                LIMIT 2
            """
            date_df = db_client.execute_query(date_sql)

            if date_df is None or len(date_df) < 2:
                logger.warning("PoolChangeSentinel: 核心池历史不足两期，跳过扫描")
                return []

            latest_date = str(date_df.iloc[0]["update_date"])
            prev_date = str(date_df.iloc[1]["update_date"])

            # Get latest pool composition
            latest_sql = f"""
                SELECT ts_code, stock_name, pool_type, rank, total_score
                FROM quant_core_pool
                WHERE update_date = '{latest_date}'
            """
            latest_pool = db_client.execute_query(latest_sql)

            # Get previous pool composition
            prev_sql = f"""
                SELECT ts_code, stock_name, pool_type, rank, total_score
                FROM quant_core_pool
                WHERE update_date = '{prev_date}'
            """
            prev_pool = db_client.execute_query(prev_sql)

            if latest_pool is None or prev_pool is None:
                return []

            latest_codes = set(latest_pool["ts_code"].tolist())
            prev_codes = set(prev_pool["ts_code"].tolist())

            # New entries: in latest but not in previous
            new_entries = latest_codes - prev_codes
            # Exits: in previous but not in latest
            exits = prev_codes - latest_codes

            # Build name/info lookups
            latest_info = {}
            for _, row in latest_pool.iterrows():
                latest_info[row["ts_code"]] = {
                    "stock_name": row.get("stock_name", row["ts_code"]),
                    "pool_type": row.get("pool_type", ""),
                    "rank": row.get("rank", 0),
                    "total_score": row.get("total_score", 0),
                }

            prev_info = {}
            for _, row in prev_pool.iterrows():
                prev_info[row["ts_code"]] = {
                    "stock_name": row.get("stock_name", row["ts_code"]),
                    "pool_type": row.get("pool_type", ""),
                    "rank": row.get("rank", 0),
                    "total_score": row.get("total_score", 0),
                }

            # Generate alerts for new entries
            for ts_code in new_entries:
                info = latest_info.get(ts_code, {})
                stock_name = info.get("stock_name", ts_code)
                pool_type = info.get("pool_type", "")
                rank = info.get("rank", 0)
                score = info.get("total_score", 0)

                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.WARNING,
                    ts_code=ts_code,
                    signal_type="pool_entry",
                    description=f"{stock_name}({ts_code}) 新进入核心池，"
                                f"池类型={pool_type}，排名第{rank}，综合得分{score:.1f}",
                    metric_name="pool_rank",
                    metric_value=float(rank) if rank else 0,
                    threshold=0,
                    deviation_pct=0,
                    context={
                        "update_date": latest_date,
                        "stock_name": stock_name,
                        "pool_type": pool_type,
                        "rank": rank,
                        "total_score": float(score) if score else 0,
                        "signal": "entry",
                        "prev_date": prev_date,
                    },
                ))

            # Generate alerts for exits
            for ts_code in exits:
                info = prev_info.get(ts_code, {})
                stock_name = info.get("stock_name", ts_code)
                pool_type = info.get("pool_type", "")
                prev_rank = info.get("rank", 0)
                prev_score = info.get("total_score", 0)

                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.WARNING,
                    ts_code=ts_code,
                    signal_type="pool_exit",
                    description=f"{stock_name}({ts_code}) 退出核心池，"
                                f"此前池类型={pool_type}，排名第{prev_rank}，"
                                f"综合得分{prev_score:.1f}",
                    metric_name="pool_rank",
                    metric_value=float(prev_rank) if prev_rank else 0,
                    threshold=0,
                    deviation_pct=0,
                    context={
                        "update_date": latest_date,
                        "stock_name": stock_name,
                        "pool_type": pool_type,
                        "prev_rank": prev_rank,
                        "prev_total_score": float(prev_score) if prev_score else 0,
                        "signal": "exit",
                        "prev_date": prev_date,
                    },
                ))

            # Summary alert if there are significant changes
            if len(new_entries) + len(exits) > 5:
                alerts.append(SentinelAlert(
                    sentinel_type=self.SENTINEL_TYPE,
                    category=self.CATEGORY,
                    severity=AlertSeverity.CRITICAL,
                    signal_type="pool_major_reshuffle",
                    description=f"核心池发生重大调整: {len(new_entries)}只新进，{len(exits)}只退出，"
                                f"更新日期{latest_date}",
                    metric_name="pool_change_count",
                    metric_value=float(len(new_entries) + len(exits)),
                    threshold=5.0,
                    deviation_pct=(len(new_entries) + len(exits)) / max(len(prev_codes), 1) * 100,
                    context={
                        "update_date": latest_date,
                        "prev_date": prev_date,
                        "new_entries_count": len(new_entries),
                        "exits_count": len(exits),
                        "latest_pool_size": len(latest_codes),
                        "prev_pool_size": len(prev_codes),
                    },
                ))

        except Exception as e:
            logger.error(f"PoolChangeSentinel scan error: {e}", exc_info=True)

        return alerts
