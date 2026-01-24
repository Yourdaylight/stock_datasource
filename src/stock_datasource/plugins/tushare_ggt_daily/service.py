"""港股通每日成交统计查询服务"""

from typing import Any, Optional

import pandas as pd

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class GgtDailyService:
    """港股通每日成交统计查询服务"""

    def __init__(self, use_backup: bool = False):
        """初始化服务"""
        if use_backup and settings.BACKUP_CLICKHOUSE_HOST:
            self.client = ClickHouseClient(
                host=settings.BACKUP_CLICKHOUSE_HOST,
                port=settings.BACKUP_CLICKHOUSE_PORT,
                user=settings.BACKUP_CLICKHOUSE_USER,
                password=settings.BACKUP_CLICKHOUSE_PASSWORD,
                database=settings.BACKUP_CLICKHOUSE_DATABASE,
                name="backup",
            )
        else:
            self.client = db_client.primary
        self.table = "stock_datasource.ods_ggt_daily"

    def get_daily_by_date(self, trade_date: str) -> pd.DataFrame:
        """
        获取指定日期港股通成交统计

        Args:
            trade_date: 交易日期

        Returns:
            成交统计数据
        """
        sql = f"SELECT * FROM {self.table} WHERE trade_date = %(trade_date)s"
        return self.client.execute_query(sql, {"trade_date": trade_date})

    def get_daily_by_range(
        self,
        start_date: str,
        end_date: str,
        limit: int = 1000,
    ) -> pd.DataFrame:
        """
        获取日期范围内港股通成交统计

        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数

        Returns:
            成交统计数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            WHERE trade_date >= %(start_date)s AND trade_date <= %(end_date)s
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(
            sql, {"start_date": start_date, "end_date": end_date, "limit": limit}
        )

    def get_latest(self, limit: int = 30) -> pd.DataFrame:
        """
        获取最近N天港股通成交统计

        Args:
            limit: 返回条数

        Returns:
            成交统计数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(sql, {"limit": limit})

    def get_statistics(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        获取日期范围内港股通成交统计汇总

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计汇总数据
        """
        sql = f"""
            SELECT
                count() as trading_days,
                sum(buy_amount) as total_buy_amount,
                sum(sell_amount) as total_sell_amount,
                sum(buy_amount) - sum(sell_amount) as net_amount,
                avg(buy_amount) as avg_buy_amount,
                avg(sell_amount) as avg_sell_amount,
                max(buy_amount) as max_buy_amount,
                max(sell_amount) as max_sell_amount
            FROM {self.table}
            WHERE trade_date >= %(start_date)s AND trade_date <= %(end_date)s
        """
        return self.client.execute_query(
            sql, {"start_date": start_date, "end_date": end_date}
        )

    def get_monthly_statistics(self, year: str) -> pd.DataFrame:
        """
        获取指定年份月度统计

        Args:
            year: 年份（如：2024）

        Returns:
            月度统计数据
        """
        sql = f"""
            SELECT
                substring(trade_date, 1, 6) as month,
                count() as trading_days,
                sum(buy_amount) as total_buy_amount,
                sum(sell_amount) as total_sell_amount,
                sum(buy_amount) - sum(sell_amount) as net_amount
            FROM {self.table}
            WHERE trade_date >= %(start_date)s AND trade_date <= %(end_date)s
            GROUP BY substring(trade_date, 1, 6)
            ORDER BY month
        """
        return self.client.execute_query(
            sql, {"start_date": f"{year}0101", "end_date": f"{year}1231"}
        )
