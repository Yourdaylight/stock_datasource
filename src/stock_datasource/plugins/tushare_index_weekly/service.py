"""TuShare index weekly (指数周线行情) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y%m%d')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in (obj.items() if isinstance(obj, dict) else obj.items())}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareIndexWeeklyService(BaseService):
    """Query service for TuShare index weekly data (指数周线行情)."""
    
    def __init__(self):
        super().__init__("tushare_index_weekly")
    
    @query_method(
        description="Query index weekly data by code and date range (按指数代码和日期范围查询周线数据)",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Index code, e.g., 000001.SH (指数代码)",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format (开始日期)",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format (结束日期)",
                required=True,
            ),
        ]
    )
    def get_index_weekly(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query index weekly data by code and date range.
        
        Args:
            ts_code: Index code (e.g., 000001.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of index weekly records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM ods_index_weekly
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest index weekly data for a specific date (查询指定日期的周线数据)",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format (交易日期)",
                required=True,
            ),
            QueryParam(
                name="ts_code",
                type="str",
                description="Index code (optional), if not provided returns all indices (指数代码，可选)",
                required=False,
            ),
        ]
    )
    def get_index_weekly_by_date(
        self,
        trade_date: str,
        ts_code: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query index weekly data for a specific date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            ts_code: Optional index code
        
        Returns:
            List of index weekly records
        """
        where_clause = f"trade_date = '{trade_date}'"
        if ts_code:
            where_clause += f" AND ts_code = '{ts_code}'"
        
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM ods_index_weekly
        WHERE {where_clause}
        ORDER BY ts_code
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get latest weekly data for multiple indices (获取多个指数的最新周线数据)",
        params=[
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of index codes (指数代码列表)",
                required=True,
            ),
        ]
    )
    def get_latest_index_weekly(
        self,
        ts_codes: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Query latest weekly data for multiple indices.
        
        Args:
            ts_codes: List of index codes
        
        Returns:
            List of latest index weekly records
        """
        codes_str = "','".join(ts_codes)
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_index_weekly
            WHERE ts_code IN ('{codes_str}')
        )
        WHERE rn = 1
        ORDER BY ts_code
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
