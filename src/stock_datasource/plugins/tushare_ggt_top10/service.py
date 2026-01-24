"""港股通十大成交股查询服务"""

from typing import Any, Optional

import pandas as pd

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class GgtTop10Service:
    """港股通十大成交股查询服务"""

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
        self.table = "stock_datasource.ods_ggt_top10"

    def get_top10_by_date(
        self, trade_date: str, market_type: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取指定日期港股通十大成交股

        Args:
            trade_date: 交易日期
            market_type: 市场类型，2-港股通(沪)，4-港股通(深)

        Returns:
            十大成交股数据
        """
        sql = f"SELECT * FROM {self.table} WHERE trade_date = %(trade_date)s"
        params: dict[str, Any] = {"trade_date": trade_date}

        if market_type:
            sql += " AND market_type = %(market_type)s"
            params["market_type"] = market_type

        sql += " ORDER BY rank ASC"
        return self.client.execute_query(sql, params)

    def get_stock_history(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        获取股票港股通历史

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数

        Returns:
            股票港股通历史数据
        """
        sql = f"SELECT * FROM {self.table} WHERE ts_code = %(ts_code)s"
        params: dict[str, Any] = {"ts_code": ts_code}

        if start_date:
            sql += " AND trade_date >= %(start_date)s"
            params["start_date"] = start_date
        if end_date:
            sql += " AND trade_date <= %(end_date)s"
            params["end_date"] = end_date

        sql += f" ORDER BY trade_date DESC LIMIT %(limit)s"
        params["limit"] = limit
        return self.client.execute_query(sql, params)

    def get_top_net_buy(self, trade_date: str, limit: int = 10) -> pd.DataFrame:
        """
        获取指定日期净买入金额排行

        Args:
            trade_date: 交易日期
            limit: 返回条数

        Returns:
            净买入排行数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            WHERE trade_date = %(trade_date)s
            ORDER BY net_amount DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(sql, {"trade_date": trade_date, "limit": limit})

    def get_top_net_sell(self, trade_date: str, limit: int = 10) -> pd.DataFrame:
        """
        获取指定日期净卖出金额排行

        Args:
            trade_date: 交易日期
            limit: 返回条数

        Returns:
            净卖出排行数据
        """
        sql = f"""
            SELECT * FROM {self.table}
            WHERE trade_date = %(trade_date)s
            ORDER BY net_amount ASC
            LIMIT %(limit)s
        """
        return self.client.execute_query(sql, {"trade_date": trade_date, "limit": limit})

    def get_frequent_stocks(
        self, start_date: str, end_date: str, limit: int = 20
    ) -> pd.DataFrame:
        """
        获取上榜频率排行

        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数

        Returns:
            上榜频率排行数据
        """
        sql = f"""
            SELECT
                ts_code,
                any(name) as name,
                count() as appear_count,
                sum(net_amount) as total_net_amount,
                avg(net_amount) as avg_net_amount
            FROM {self.table}
            WHERE trade_date >= %(start_date)s AND trade_date <= %(end_date)s
            GROUP BY ts_code
            ORDER BY appear_count DESC, total_net_amount DESC
            LIMIT %(limit)s
        """
        return self.client.execute_query(
            sql, {"start_date": start_date, "end_date": end_date, "limit": limit}
        )
