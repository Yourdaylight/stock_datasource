"""TuShare ths_member (同花顺概念成分) query service."""

from typing import Any, Dict, List
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareThsMemberService(BaseService):
    """Query service for TuShare ths_member data."""
    
    def __init__(self):
        super().__init__("tushare_ths_member")
    
    @query_method(
        description="Query THS concept members by concept code",
        params=[
            QueryParam(name="ts_code", type="str", description="THS concept index code", required=True),
        ]
    )
    def get_ths_member(self, ts_code: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, code, name, weight, in_date, out_date, is_new
        FROM ods_ths_member WHERE ts_code = '{ts_code}' ORDER BY code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query which THS concepts a stock belongs to",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
        ]
    )
    def get_stock_ths_concepts(self, code: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT ts_code, code, name, weight, in_date, out_date, is_new
        FROM ods_ths_member WHERE code = '{code}' ORDER BY ts_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
