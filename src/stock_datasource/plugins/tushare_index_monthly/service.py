"""TuShare index monthly (指数月线行情) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y%m%d')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareIndexMonthlyService(BaseService):
    """Query service for TuShare index monthly data."""
    
    def __init__(self):
        super().__init__("tushare_index_monthly")
    
    @query_method(
        description="Query index monthly data by code and date range",
        params=[
            QueryParam(name="ts_code", type="str", description="Index code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_index_monthly(self, ts_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        FROM ods_index_monthly
        WHERE ts_code = '{ts_code}' AND trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return [_convert_to_json_serializable(r) for r in df.to_dict('records')]
    
    @query_method(
        description="Query index monthly data by date",
        params=[
            QueryParam(name="trade_date", type="str", description="Trade date YYYYMMDD", required=True),
            QueryParam(name="ts_code", type="str", description="Index code (optional)", required=False),
        ]
    )
    def get_index_monthly_by_date(self, trade_date: str, ts_code: Optional[str] = None) -> List[Dict[str, Any]]:
        where = f"trade_date = '{trade_date}'"
        if ts_code:
            where += f" AND ts_code = '{ts_code}'"
        query = f"""
        SELECT ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        FROM ods_index_monthly WHERE {where} ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [_convert_to_json_serializable(r) for r in df.to_dict('records')]
