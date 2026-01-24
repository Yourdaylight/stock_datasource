"""TuShare index classify (申万行业分类) query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    if pd.isna(obj):
        return None
    return obj


class TuShareIndexClassifyService(BaseService):
    """Query service for TuShare index classify data."""
    
    def __init__(self):
        super().__init__("tushare_index_classify")
    
    @query_method(
        description="Query industry classification by level",
        params=[
            QueryParam(name="level", type="str", description="Level L1/L2/L3", required=True),
            QueryParam(name="src", type="str", description="Source SW2021/SW/MSCI", required=False),
        ]
    )
    def get_index_classify_by_level(self, level: str, src: Optional[str] = None) -> List[Dict[str, Any]]:
        where = f"level = '{level}'"
        if src:
            where += f" AND src = '{src}'"
        query = f"""
        SELECT index_code, industry_name, level, industry_code, is_pub, parent_code, src
        FROM dim_index_classify WHERE {where} ORDER BY index_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Query all industry classifications",
        params=[
            QueryParam(name="src", type="str", description="Source SW2021/SW/MSCI", required=False),
        ]
    )
    def get_all_index_classify(self, src: Optional[str] = None) -> List[Dict[str, Any]]:
        where = "1=1"
        if src:
            where = f"src = '{src}'"
        query = f"""
        SELECT index_code, industry_name, level, industry_code, is_pub, parent_code, src
        FROM dim_index_classify WHERE {where} ORDER BY level, index_code
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
    
    @query_method(
        description="Get industry by index code",
        params=[
            QueryParam(name="index_code", type="str", description="Industry index code", required=True),
        ]
    )
    def get_industry_by_code(self, index_code: str) -> List[Dict[str, Any]]:
        query = f"""
        SELECT index_code, industry_name, level, industry_code, is_pub, parent_code, src
        FROM dim_index_classify WHERE index_code = '{index_code}'
        """
        df = self.db.execute_query(query)
        return [{k: _convert_to_json_serializable(v) for k, v in r.items()} for r in df.to_dict('records')]
