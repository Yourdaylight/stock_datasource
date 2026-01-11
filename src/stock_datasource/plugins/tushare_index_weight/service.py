"""TuShare index weight query service."""

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


class TuShareIndexWeightService(BaseService):
    """Query service for TuShare index weight data."""
    
    def __init__(self):
        super().__init__("tushare_index_weight")
    
    @query_method(
        description="Query index constituents by date",
        params=[
            QueryParam(
                name="index_code",
                type="str",
                description="Index code, e.g., 399300.SZ",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_index_constituents(
        self,
        index_code: str,
        trade_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query index constituents by date.
        
        Args:
            index_code: Index code (e.g., 399300.SZ)
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            List of constituent stocks and weights
        """
        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = '{index_code}'
        AND trade_date = '{trade_date}'
        ORDER BY weight DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query index constituent weight history",
        params=[
            QueryParam(
                name="index_code",
                type="str",
                description="Index code",
                required=True,
            ),
            QueryParam(
                name="con_code",
                type="str",
                description="Constituent stock code",
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
    def get_constituent_weight_history(
        self,
        index_code: str,
        con_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query index constituent weight history.
        
        Args:
            index_code: Index code
            con_code: Constituent stock code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of weight history records
        """
        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = '{index_code}'
        AND con_code = '{con_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query top N constituents by weight",
        params=[
            QueryParam(
                name="index_code",
                type="str",
                description="Index code",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of top constituents to return",
                required=False,
                default=10,
            ),
        ]
    )
    def get_top_constituents(
        self,
        index_code: str,
        trade_date: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Query top N constituents by weight.
        
        Args:
            index_code: Index code
            trade_date: Trade date in YYYYMMDD format
            limit: Number of top constituents to return
        
        Returns:
            List of top constituents by weight
        """
        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = '{index_code}'
        AND trade_date = '{trade_date}'
        ORDER BY weight DESC
        LIMIT {limit}
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Check if stock is in index",
        params=[
            QueryParam(
                name="index_code",
                type="str",
                description="Index code",
                required=True,
            ),
            QueryParam(
                name="con_code",
                type="str",
                description="Stock code to check",
                required=True,
            ),
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def is_stock_in_index(
        self,
        index_code: str,
        con_code: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """
        Check if stock is in index.
        
        Args:
            index_code: Index code
            con_code: Stock code to check
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            Dictionary with is_member and weight information
        """
        query = f"""
        SELECT 
            index_code,
            con_code,
            trade_date,
            weight
        FROM ods_index_weight
        WHERE index_code = '{index_code}'
        AND con_code = '{con_code}'
        AND trade_date = '{trade_date}'
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return {'is_member': False, 'weight': None}
        
        record = df.iloc[0]
        return _convert_to_json_serializable({
            'is_member': True,
            'weight': float(record['weight'])
        })
