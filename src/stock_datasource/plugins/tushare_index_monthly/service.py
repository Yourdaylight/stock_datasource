"""TuShare index monthly query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y-%m-%d')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in (obj.items() if isinstance(obj, dict) else obj.items())}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareIndexMonthlyService(BaseService):
    """Query service for TuShare index monthly data."""
    
    def __init__(self):
        super().__init__("tushare_index_monthly")
        self.table = "ods_index_monthly"
    
    @query_method(
        description="查询指数月线行情数据",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="TS指数代码，如 000001.SH",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="开始日期 YYYYMMDD格式",
                required=False,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="结束日期 YYYYMMDD格式",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="返回记录数限制",
                required=False,
                default=100,
            ),
        ]
    )
    def get_by_code(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query index monthly data by code and date range.
        
        Args:
            ts_code: TS index code (e.g., 000001.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            limit: Max number of records to return
        
        Returns:
            List of index monthly records
        """
        conditions = ["ts_code = %(ts_code)s"]
        params: Dict[str, Any] = {"ts_code": ts_code, "limit": limit}
        
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
        
        df = self.db.execute_query(query, params)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询指定交易日的所有指数月线数据",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD格式",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="返回记录数限制",
                required=False,
                default=100,
            ),
        ]
    )
    def get_by_date(
        self,
        trade_date: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query all index monthly data for a specific date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            limit: Max number of records to return
        
        Returns:
            List of index monthly records
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
            ORDER BY ts_code
            LIMIT %(limit)s
        """
        
        df = self.db.execute_query(query, {"trade_date": trade_date, "limit": limit})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询指数最新月线数据",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="TS指数代码，如 000001.SH",
                required=True,
            ),
        ]
    )
    def get_latest(
        self,
        ts_code: str,
    ) -> Dict[str, Any]:
        """Query latest monthly data for an index.
        
        Args:
            ts_code: TS index code (e.g., 000001.SH)
        
        Returns:
            Latest index monthly record
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE ts_code = %(ts_code)s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        
        df = self.db.execute_query(query, {"ts_code": ts_code})
        if df.empty:
            return {}
        
        record = df.iloc[0].to_dict()
        return _convert_to_json_serializable(record)
    
    @query_method(
        description="查询月涨幅排行榜",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD格式",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="返回记录数限制",
                required=False,
                default=10,
            ),
        ]
    )
    def get_top_gainers(
        self,
        trade_date: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query top gaining indices for a month.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            limit: Max number of records to return
        
        Returns:
            List of top gaining indices
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND pct_chg IS NOT NULL
            ORDER BY pct_chg DESC
            LIMIT %(limit)s
        """
        
        df = self.db.execute_query(query, {"trade_date": trade_date, "limit": limit})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询月跌幅排行榜",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="交易日期 YYYYMMDD格式",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="返回记录数限制",
                required=False,
                default=10,
            ),
        ]
    )
    def get_top_losers(
        self,
        trade_date: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query top losing indices for a month.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            limit: Max number of records to return
        
        Returns:
            List of top losing indices
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE trade_date = %(trade_date)s
              AND pct_chg IS NOT NULL
            ORDER BY pct_chg ASC
            LIMIT %(limit)s
        """
        
        df = self.db.execute_query(query, {"trade_date": trade_date, "limit": limit})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="查询指数年度月线走势",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="TS指数代码，如 000001.SH",
                required=True,
            ),
            QueryParam(
                name="year",
                type="str",
                description="年份，如 2024",
                required=True,
            ),
        ]
    )
    def get_yearly_trend(
        self,
        ts_code: str,
        year: str,
    ) -> List[Dict[str, Any]]:
        """Query index monthly trend for a specific year.
        
        Args:
            ts_code: TS index code (e.g., 000001.SH)
            year: Year (e.g., 2024)
        
        Returns:
            List of monthly records for the year
        """
        query = f"""
            SELECT *
            FROM {self.table}
            WHERE ts_code = %(ts_code)s
              AND toYear(trade_date) = %(year)s
            ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query, {"ts_code": ts_code, "year": int(year)})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
