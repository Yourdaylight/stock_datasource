"""TuShare adjustment factor query service."""

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


class TuShareAdjFactorService(BaseService):
    """Query service for TuShare adjustment factor data."""
    
    def __init__(self):
        super().__init__("tushare_adj_factor")
    
    @query_method(
        description="Query adjustment factor by code and date range",
        params=[
            QueryParam(
                name="code",
                type="str",
                description="Stock code, e.g., 000001.SZ",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_adj_factor(\
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query adjustment factor data.
        
        Args:
            code: Stock code (e.g., 000001.SZ)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of adjustment factor records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            adj_factor
        FROM ods_adj_factor
        WHERE ts_code = '{code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest adjustment factor for multiple stocks",
        params=[
            QueryParam(
                name="codes",
                type="list",
                description="List of stock codes",
                required=True,
            ),
        ]
    )
    def get_latest_adj_factor(\
        self,
        codes: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Query latest adjustment factor for multiple stocks.
        
        Args:
            codes: List of stock codes
        
        Returns:
            List of latest adjustment factor records
        """
        codes_str = "','".join(codes)
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            adj_factor
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_adj_factor
            WHERE ts_code IN ('{codes_str}')
        )
        WHERE rn = 1
        ORDER BY ts_code
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
