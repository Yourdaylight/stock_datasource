"""港股通每月成交统计查询服务"""

from typing import Any, Optional

import pandas as pd

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class GgtMonthlyService:
    """港股通每月成交统计查询服务"""

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
        self.table = "stock_datasource.ods_ggt_monthly"

    def get_monthly_by_month(self, month: str) -> pd.DataFrame:
        """
        获取指定月份港股通成交统计

        Args:
            month: 交易月份（YYYYMM）

        Returns:
            成交统计数据
        """
        sql = f"SELECT * FROM {self.table} WHERE month = %(month)s"
        return self.client.execute_query(sql, {"month": month})

    def get_monthly_by_range(
        self,
        start_month: str,
        end_month: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        获取月份范围内港股通成交统计

        Args:
            start_month: 开始月份
            end_month: 结束月份
            limit: 返回条数

        Returns:
            成交统计数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            WHERE month >= %(start_month)s AND month <= %(end_month)s
            ORDER BY month DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(
            sql, {"start_month": start_month, "end_month": end_month, "limit": limit}
        )

    def get_latest(self, limit: int = 12) -> pd.DataFrame:
        """
        获取最近N个月港股通成交统计

        Args:
            limit: 返回条数

        Returns:
            成交统计数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            ORDER BY month DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(sql, {"limit": limit})

    def get_yearly_statistics(self, year: str) -> pd.DataFrame:
        """
        获取指定年份港股通成交统计汇总

        Args:
            year: 年份（如：2024）

        Returns:
            统计汇总数据
        """
        sql = f"""
            SELECT
                substring(month, 1, 4) as year,
                count() as months,
                sum(total_buy_amt) as total_buy_amt,
                sum(total_sell_amt) as total_sell_amt,
                sum(total_buy_amt) - sum(total_sell_amt) as net_amount,
                avg(day_buy_amt) as avg_day_buy_amt,
                avg(day_sell_amt) as avg_day_sell_amt
            FROM {self.table}
            WHERE month >= %(start_month)s AND month <= %(end_month)s
            GROUP BY substring(month, 1, 4)
        """
        return self.client.execute_query(
            sql, {"start_month": f"{year}01", "end_month": f"{year}12"}
        )

    def get_all_years_statistics(self) -> pd.DataFrame:
        """
        获取所有年份港股通成交统计汇总

        Returns:
            各年份统计汇总数据
        """
        sql = f"""
            SELECT
                substring(month, 1, 4) as year,
                count() as months,
                sum(total_buy_amt) as total_buy_amt,
                sum(total_sell_amt) as total_sell_amt,
                sum(total_buy_amt) - sum(total_sell_amt) as net_amount
            FROM {self.table}
            GROUP BY substring(month, 1, 4)
            ORDER BY year DESC
        """
        return self.client.execute_query(sql)
