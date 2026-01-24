"""周线行情查询服务"""

from typing import Any

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class WeeklyService:
    """周线行情查询服务"""

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
        self.table = "stock_datasource.ods_weekly"

    def get_weekly_by_code(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        按股票代码获取周线数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回条数限制

        Returns:
            周线数据列表
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

    def get_weekly_by_date(
        self,
        trade_date: str,
        limit: int = 6000,
    ) -> list[dict[str, Any]]:
        """
        获取指定交易日的周线数据

        Args:
            trade_date: 交易日期
            limit: 返回条数限制

        Returns:
            周线数据列表
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
            ORDER BY ts_code
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"trade_date": trade_date, "limit": limit})
        return df.to_dict(orient="records")

    def get_top_gainers(
        self,
        trade_date: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        获取周涨幅榜

        Args:
            trade_date: 交易日期
            limit: 返回条数限制

        Returns:
            涨幅榜数据
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND pct_chg IS NOT NULL
            ORDER BY pct_chg DESC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"trade_date": trade_date, "limit": limit})
        return df.to_dict(orient="records")

    def get_top_losers(
        self,
        trade_date: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        获取周跌幅榜

        Args:
            trade_date: 交易日期
            limit: 返回条数限制

        Returns:
            跌幅榜数据
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND pct_chg IS NOT NULL
            ORDER BY pct_chg ASC
            LIMIT %(limit)s
        """

        df = self.client.execute_query(query, {"trade_date": trade_date, "limit": limit})
        return df.to_dict(orient="records")

    def get_weekly_statistics(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        获取周线统计信息

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            统计信息
        """
        conditions = ["ts_code = %(ts_code)s"]
        params: dict[str, Any] = {"ts_code": ts_code}

        if start_date:
            conditions.append("trade_date >= %(start_date)s")
            params["start_date"] = start_date
        if end_date:
            conditions.append("trade_date <= %(end_date)s")
            params["end_date"] = end_date

        query = f"""
            SELECT
                count() AS total_weeks,
                min(trade_date) AS first_week,
                max(trade_date) AS last_week,
                avg(pct_chg) AS avg_pct_chg,
                max(pct_chg) AS max_pct_chg,
                min(pct_chg) AS min_pct_chg,
                avg(vol) AS avg_vol,
                avg(amount) AS avg_amount
            FROM {self.table}
            WHERE {' AND '.join(conditions)}
        """

        df = self.client.execute_query(query, params)
        if not df.empty:
            return df.iloc[0].to_dict()
        return {}
