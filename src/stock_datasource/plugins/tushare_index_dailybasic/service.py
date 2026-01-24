"""TuShare index dailybasic (大盘指数每日指标) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y%m%d')
    elif pd.isna(obj):
        return None
    return obj


class TuShareIndexDailybasicService(BaseService):
    """Query service for TuShare index dailybasic data."""
    
    def __init__(self):
        super().__init__("tushare_index_dailybasic")
    
    @query_method(
        description="Query index dailybasic data by code and date range",
        params=[
            QueryParam(name="ts_code", type="str", description="Index code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_index_dailybasic(self, ts_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, total_mv, float_mv, total_share, float_share, free_share,
               turnover_rate, turnover_rate_f, pe, pe_ttm, pb
        FROM ods_index_dailybasic
        WHERE ts_code = '{ts_code}' AND trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query index dailybasic data by date",
        params=[
            QueryParam(name="trade_date", type="str", description="Trade date YYYYMMDD", required=True),
        ]
    )
    def get_index_dailybasic_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, total_mv, float_mv, total_share, float_share, free_share,
               turnover_rate, turnover_rate_f, pe, pe_ttm, pb
        FROM ods_index_dailybasic WHERE trade_date = '{trade_date}' ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
