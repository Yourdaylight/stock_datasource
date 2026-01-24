"""TuShare index member (指数成分股) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareIndexMemberService(BaseService):
    """Query service for TuShare index member data."""
    
    def __init__(self):
        super().__init__("tushare_index_member")
    
    @query_method(
        description="Query index members by index code",
        params=[
            QueryParam(name="index_code", type="str", description="Index code", required=True),
            QueryParam(name="is_new", type="str", description="Y for current, N for all", required=False),
        ]
    )
    def get_index_member(self, index_code: str, is_new: Optional[str] = None) -> List[Dict[str, Any]]:
        where = f"index_code = '{index_code}'"
        if is_new:
            where += f" AND is_new = '{is_new}'"
        query = f"""
        SELECT index_code, con_code, in_date, out_date, is_new
        FROM ods_index_member WHERE {where} ORDER BY con_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query which indices a stock belongs to",
        params=[
            QueryParam(name="con_code", type="str", description="Stock code", required=True),
        ]
    )
    def get_stock_indices(self, con_code: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT index_code, con_code, in_date, out_date, is_new
        FROM ods_index_member WHERE con_code = '{con_code}' ORDER BY index_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
