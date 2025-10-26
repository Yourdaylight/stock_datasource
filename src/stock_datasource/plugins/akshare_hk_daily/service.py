"""AKShare Hong Kong daily data query service."""

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


class AKShareHKDailyService(BaseService):
    """Query service for AKShare Hong Kong daily data."""
    
    def __init__(self):
        super().__init__("akshare_hk_daily")
    
    @query_method(
        description="Query Hong Kong daily data by symbol",
        params=[
            QueryParam(
                name="symbol",
                type="str",
                description="Hong Kong stock symbol, e.g., 00700",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=False,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=False,
            ),
        ]
    )
    def get_hk_daily(self, symbol: str, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query Hong Kong daily data by symbol.
        
        Args:
            symbol: Hong Kong stock symbol (e.g., 00700)
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
        
        Returns:
            List of daily data records
        """
        query = f"""
        SELECT 
            symbol,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            amount
        FROM ods_hk_daily
        WHERE symbol = '{symbol}'
        """
        
        if start_date:
            query += f" AND trade_date >= '{start_date}'"
        if end_date:
            query += f" AND trade_date <= '{end_date}'"
        
        query += " ORDER BY trade_date DESC"
        
        df = self.db.execute_query(query)
        return df.to_dict('records')
    
    @query_method(
        description="Query latest Hong Kong daily data",
        params=[
            QueryParam(
                name="symbol",
                type="str",
                description="Hong Kong stock symbol, e.g., 00700",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of records to return (default: 10)",
                required=False,
            ),
        ]
    )
    def get_latest_hk_daily(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Query latest Hong Kong daily data.
        
        Args:
            symbol: Hong Kong stock symbol (e.g., 00700)
            limit: Number of records to return (default: 10)
        
        Returns:
            List of latest daily data records
        """
        query = f"""
        SELECT 
            symbol,
            trade_date,
            open,
            high,
            low,
            close,
            volume,
            amount
        FROM ods_hk_daily
        WHERE symbol = '{symbol}'
        ORDER BY trade_date DESC
        LIMIT {limit}
        """
        
        df = self.db.execute_query(query)
        return df.to_dict('records')
