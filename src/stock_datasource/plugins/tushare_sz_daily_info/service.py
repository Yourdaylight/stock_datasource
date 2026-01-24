"""TuShare sz_daily_info (深圳市场每日概况) query service."""

from typing import Any, Dict, List
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareSzDailyInfoService(BaseService):
    """Query service for TuShare sz_daily_info data."""
    
    def __init__(self):
        super().__init__("tushare_sz_daily_info")
    
    @query_method(
        description="Query SZ market daily info by date range",
        params=[
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_sz_daily_info(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT trade_date, ts_code, count, amount, vol, total_share, total_mv, float_share, float_mv
        FROM ods_sz_daily_info
        WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC, ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query SZ market daily info by date",
        params=[
            QueryParam(name="trade_date", type="str", description="Trade date YYYYMMDD", required=True),
        ]
    )
    def get_sz_daily_info_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT trade_date, ts_code, count, amount, vol, total_share, total_mv, float_share, float_mv
        FROM ods_sz_daily_info WHERE trade_date = '{trade_date}' ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
