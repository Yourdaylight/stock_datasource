"""TuShare sw_daily (申万行业指数日线) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareSwDailyService(BaseService):
    """Query service for TuShare sw_daily data."""
    
    def __init__(self):
        super().__init__("tushare_sw_daily")
    
    @query_method(
        description="Query SW industry index daily data",
        params=[
            QueryParam(name="ts_code", type="str", description="Industry index code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_sw_daily(self, ts_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, name, open, high, low, close, change, pct_change, vol, amount, pe, pb, float_mv, total_mv
        FROM ods_sw_daily
        WHERE ts_code = '{ts_code}' AND trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query SW industry index daily data by date",
        params=[
            QueryParam(name="trade_date", type="str", description="Trade date YYYYMMDD", required=True),
        ]
    )
    def get_sw_daily_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, name, open, high, low, close, change, pct_change, vol, amount, pe, pb, float_mv, total_mv
        FROM ods_sw_daily WHERE trade_date = '{trade_date}' ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
