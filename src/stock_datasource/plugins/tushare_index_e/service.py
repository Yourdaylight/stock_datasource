"""TuShare index_e (中证指数估值) query service."""

from typing import Any, Dict, List
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareIndexEService(BaseService):
    """Query service for TuShare index_e data."""
    
    def __init__(self):
        super().__init__("tushare_index_e")
    
    @query_method(
        description="Query CSI index valuation by code and date range",
        params=[
            QueryParam(name="ts_code", type="str", description="Index code", required=True),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
        ]
    )
    def get_index_e(self, ts_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv
        FROM ods_index_e
        WHERE ts_code = '{ts_code}' AND trade_date >= '{start_date}' AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query CSI index valuation by date",
        params=[
            QueryParam(name="trade_date", type="str", description="Trade date YYYYMMDD", required=True),
        ]
    )
    def get_index_e_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, trade_date, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_mv
        FROM ods_index_e WHERE trade_date = '{trade_date}' ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
