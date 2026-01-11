"""TuShare index basic info query service."""

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


class TuShareIndexBasicService(BaseService):
    """Query service for TuShare index basic information data."""
    
    def __init__(self):
        super().__init__("tushare_index_basic")
    
    @query_method(
        description="Query index basic information by code",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Index code, e.g., 000300.SH",
                required=True,
            ),
        ]
    )
    def get_index_info(
        self,
        ts_code: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Query index basic information by code.
        
        Args:
            ts_code: Index code (e.g., 000300.SH)
        
        Returns:
            Index information dictionary or None
        """
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            index_type,
            category,
            base_date,
            base_point,
            list_date,
            weight_rule,
            desc,
            exp_date
        FROM dim_index_basic
        WHERE ts_code = '{ts_code}'
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return None
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
    
    @query_method(
        description="Query indices by market",
        params=[
            QueryParam(
                name="market",
                type="str",
                description="Market code (SSE/SZSE/CSI/CICC/SW/OTH)",
                required=True,
            ),
            QueryParam(
                name="category",
                type="str",
                description="Index category",
                required=False,
            ),
        ]
    )
    def get_indices_by_market(
        self,
        market: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query indices by market.
        
        Args:
            market: Market code (SSE/SZSE/CSI/CICC/SW/OTH)
            category: Index category (optional)
        
        Returns:
            List of index information records
        """
        where_clause = f"WHERE market = '{market}'"
        if category:
            where_clause += f" AND category = '{category}'"
        
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            index_type,
            category,
            base_date,
            list_date,
            weight_rule
        FROM dim_index_basic
        {where_clause}
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Search indices by name",
        params=[
            QueryParam(
                name="keyword",
                type="str",
                description="Search keyword in index name",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of results",
                required=False,
                default=100,
            ),
        ]
    )
    def search_indices(
        self,
        keyword: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search indices by name.
        
        Args:
            keyword: Search keyword in index name
            limit: Maximum number of results
        
        Returns:
            List of matching index information records
        """
        query = f"""
        SELECT 
            ts_code,
            name,
            fullname,
            market,
            publisher,
            category,
            list_date
        FROM dim_index_basic
        WHERE name ILIKE '%{keyword}%'
        OR fullname ILIKE '%{keyword}%'
        LIMIT {limit}
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get all index categories",
        params=[]
    )
    def get_index_categories(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Get all index categories.
        
        Returns:
            List of unique index categories
        """
        query = """
        SELECT DISTINCT category
        FROM dim_index_basic
        WHERE category IS NOT NULL
        ORDER BY category ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
