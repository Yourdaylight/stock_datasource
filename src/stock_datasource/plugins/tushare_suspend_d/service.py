"""每日停复牌信息查询服务"""

from typing import Any

from stock_datasource.models.database import db_client, ClickHouseClient
from stock_datasource.config.settings import settings


class SuspendDService:
    """每日停复牌信息查询服务"""

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
        self.table = "stock_datasource.ods_suspend_d"

    def get_suspended_stocks(
        self,
        trade_date: str,
    ) -> list[dict[str, Any]]:
        """
        获取指定日期停牌股票

        Args:
            trade_date: 交易日期

        Returns:
            停牌股票列表
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND suspend_type = 'S'
            ORDER BY ts_code
        """

        df = self.client.execute_query(query, {"trade_date": trade_date})
        return df.to_dict(orient="records")

    def get_resumed_stocks(
        self,
        trade_date: str,
    ) -> list[dict[str, Any]]:
        """
        获取指定日期复牌股票

        Args:
            trade_date: 交易日期

        Returns:
            复牌股票列表
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND suspend_type = 'R'
            ORDER BY ts_code
        """

        df = self.client.execute_query(query, {"trade_date": trade_date})
        return df.to_dict(orient="records")

    def get_stock_suspend_history(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        获取股票停复牌历史

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            停复牌历史列表
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
            SELECT *
            FROM {self.table}
            WHERE {' AND '.join(conditions)}
            ORDER BY trade_date DESC
        """

        df = self.client.execute_query(query, params)
        return df.to_dict(orient="records")

    def is_stock_suspended(
        self,
        ts_code: str,
        trade_date: str,
    ) -> bool:
        """
        检查股票在指定日期是否停牌

        Args:
            ts_code: 股票代码
            trade_date: 交易日期

        Returns:
            是否停牌
        """
        query = f"""
            SELECT count() AS cnt
            FROM {self.table}
            WHERE ts_code = %(ts_code)s
              AND trade_date = %(trade_date)s
              AND suspend_type = 'S'
        """

        df = self.client.execute_query(query, {"ts_code": ts_code, "trade_date": trade_date})
        return df.iloc[0]["cnt"] > 0 if not df.empty else False

    def get_suspend_statistics(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        """
        获取停复牌统计信息

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            按日期统计的停复牌数量
        """
        query = f"""
            SELECT
                trade_date,
                countIf(suspend_type = 'S') AS suspended_count,
                countIf(suspend_type = 'R') AS resumed_count
            FROM {self.table}
            WHERE trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            GROUP BY trade_date
            ORDER BY trade_date DESC
        """

        df = self.client.execute_query(query, {"start_date": start_date, "end_date": end_date})
        return df.to_dict(orient="records")
