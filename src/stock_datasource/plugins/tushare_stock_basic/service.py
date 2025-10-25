"""TuShare stock basic information query service."""

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


class TuShareStockBasicService(BaseService):
    """Query service for TuShare stock basic information."""
    
    def __init__(self):
        super().__init__("tushare_stock_basic")
    
    @query_method(
        description="Query stock basic information by code",
        params=[
            QueryParam(
                name="code",
                type="str",
                description="Stock code, e.g., 000001.SZ",
                required=True,
            ),
        ]
    )
    def get_stock_basic(\
        self,
        code: str,
    ) -> List[Dict[str, Any]]:
        """
        Query stock basic information.
        
        Args:
            code: Stock code (e.g., 000001.SZ)
        
        Returns:
            List of stock basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            symbol,
            name,
            area,
            industry,
            market,
            list_date,
            delist_date,
            list_status
        FROM ods_stock_basic
        WHERE ts_code = '{code}'
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query all listed stocks",
        params=[
            QueryParam(
                name="list_status",
                type="str",
                description="List status: L(listed), D(delisted), P(suspended)",
                required=False,
                default="L",
            ),
        ]
    )
    def get_all_stocks(\
        self,
        list_status: str = "L",
    ) -> List[Dict[str, Any]]:
        """
        Query all stocks by list status.
        
        Args:
            list_status: List status (L/D/P)
        
        Returns:
            List of stock basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            symbol,
            name,
            area,
            industry,
            market,
            list_date,
            delist_date,
            list_status
        FROM ods_stock_basic
        WHERE list_status = '{list_status}'
        ORDER BY list_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query stocks by industry",
        params=[
            QueryParam(
                name="industry",
                type="str",
                description="Industry name",
                required=True,
            ),
        ]
    )
    def get_stocks_by_industry(\
        self,
        industry: str,
    ) -> List[Dict[str, Any]]:
        """
        Query stocks by industry.
        
        Args:
            industry: Industry name
        
        Returns:
            List of stock basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            symbol,
            name,
            area,
            industry,
            market,
            list_date,
            delist_date,
            list_status
        FROM ods_stock_basic
        WHERE industry = '{industry}'
        AND list_status = 'L'
        ORDER BY list_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
