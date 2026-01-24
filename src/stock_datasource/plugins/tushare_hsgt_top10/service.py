"""沪深股通十大成交股查询服务"""

from typing import Any

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class HsgtTop10Service:
    """沪深股通十大成交股查询服务"""

    def __init__(self, use_backup: bool = False):
        """初始化服务"""
        if use_backup and settings.BACKUP_CLICKHOUSE_HOST:
            self.client = ClickHouseClient(
                host=settings.BACKUP_CLICKHOUSE_HOST,
                port=settings.BACKUP_CLICKHOUSE_PORT,
                user=settings.BACKUP_CLICKHOUSE_USER,
                password=settings.BACKUP_CLICKHOUSE_PASSWORD,
                database=settings.BACKUP_CLICKHOUSE_DATABASE,
                name="backup"
            )
        else:
            self.client = db_client.primary
        self.table = "stock_datasource.ods_hsgt_top10"

    def get_top10_by_date(
        self,
        trade_date: str,
        market_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取指定日期的十大成交股

        Args:
            trade_date: 交易日期
            market_type: 市场类型（1：沪市，3：深市）

        Returns:
            十大成交股列表
        """
        conditions = ["trade_date = %(trade_date)s"]
        params: dict[str, Any] = {"trade_date": trade_date}

        if market_type:
            conditions.append("market_type = %(market_type)s")
            params["market_type"] = market_type

        query = f"""
            SELECT *
            FROM {self.table}
            WHERE {' AND '.join(conditions)}
            ORDER BY market_type, rank
        """

        df = self.client.execute_query(query, params)
        return df.to_dict(orient="records")

    def get_stock_history(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        获取股票的北向资金历史记录

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数限制

        Returns:
            历史记录列表
        """
        conditions = ["ts_code = %(ts_code)s"]
        params: dict[str, Any] = {"ts_code": ts_code, "limit": limit}

        if start_date:
            conditions.append("trade_date >= %(start_date)s")
            params["start_date"] = start_date
        if end_date:
            conditions.append("trade_date <= %(end_date)s")
            params["end_date"] = end_date

        query = f"""
            SELECT *
            FROM {self.table}
            WHERE {' AND '.join(conditions)}
            ORDER BY trade_date DESC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, params)
        return df.to_dict(orient="records")

    def get_top_net_buy(
        self,
        trade_date: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        获取净买入金额最大的股票

        Args:
            trade_date: 交易日期
            limit: 返回条数限制

        Returns:
            净买入排行
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND net_amount IS NOT NULL
            ORDER BY net_amount DESC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"trade_date": trade_date, "limit": limit})
        return df.to_dict(orient="records")

    def get_top_net_sell(
        self,
        trade_date: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        获取净卖出金额最大的股票

        Args:
            trade_date: 交易日期
            limit: 返回条数限制

        Returns:
            净卖出排行
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND net_amount IS NOT NULL
            ORDER BY net_amount ASC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"trade_date": trade_date, "limit": limit})
        return df.to_dict(orient="records")

    def get_frequent_stocks(
        self,
        start_date: str,
        end_date: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        获取期间内上榜次数最多的股票

        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数限制

        Returns:
            上榜频率排行
        """
        query = f"""
            SELECT
                ts_code,
                any(name) AS name,
                count() AS appear_count,
                sum(net_amount) AS total_net_amount,
                avg(net_amount) AS avg_net_amount
            FROM {self.table}
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            GROUP BY ts_code
            ORDER BY appear_count DESC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"start_date": start_date, "end_date": end_date, "limit": limit})
        return df.to_dict(orient="records")
