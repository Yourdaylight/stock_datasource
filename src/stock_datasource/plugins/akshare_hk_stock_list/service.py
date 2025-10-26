"""AKShare Hong Kong stock list query service."""

from typing import Any, Dict, List
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


class AKShareHKStockListService(BaseService):
    """Query service for AKShare Hong Kong stock list."""
    
    def __init__(self):
        super().__init__("akshare_hk_stock_list")
    
    @query_method(
        description="Query all Hong Kong stocks",
        params=[]
    )
    def get_all_hk_stocks(self) -> List[Dict[str, Any]]:
        """
        Query all Hong Kong stocks.
        
        Returns:
            List of Hong Kong stock records
        """
        query = """
        SELECT 
            symbol,
            name,
            code,
            list_date,
            market
        FROM ods_hk_stock_list
        ORDER BY symbol
        """
        
        df = self.db.execute_query(query)
        return df.to_dict('records')
    
    @query_method(
        description="Query Hong Kong stock by symbol",
        params=[
            QueryParam(
                name="symbol",
                type="str",
                description="Hong Kong stock symbol",
                required=True,
            ),
        ]
    )
    def get_hk_stock_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Query Hong Kong stock by symbol.
        
        Args:
            symbol: Hong Kong stock symbol
        
        Returns:
            List of matching stock records
        """
        query = f"""
        SELECT 
            symbol,
            name,
            code,
            list_date,
            market
        FROM ods_hk_stock_list
        WHERE symbol = '{symbol}'
        """
        
        df = self.db.execute_query(query)
        return df.to_dict('records')
