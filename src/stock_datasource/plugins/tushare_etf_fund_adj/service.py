"""TuShare ETF fund adjustment factor query service."""

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


class TuShareETFFundAdjService(BaseService):
    """Query service for TuShare ETF fund adjustment factor data."""
    
    def __init__(self):
        super().__init__("tushare_etf_fund_adj")
    
    @query_method(
        description="Query ETF adjustment factor by code and date range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
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
    def get_etf_adj_factor(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Query ETF adjustment factor by code and date range.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of ETF adjustment factor records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            adj_factor
        FROM ods_etf_fund_adj
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest ETF adjustment factor",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
                required=True,
            ),
        ]
    )
    def get_latest_adj_factor(self, ts_code: str) -> Dict[str, Any]:
        """Query latest ETF adjustment factor.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
        
        Returns:
            Latest adjustment factor record
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            adj_factor
        FROM ods_etf_fund_adj
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date DESC
        LIMIT 1
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return {}
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
    
    @query_method(
        description="Query adjustment factors for multiple ETFs on a date",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_adj_factors_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        """Query adjustment factors for all ETFs on a specific date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            List of adjustment factor records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            adj_factor
        FROM ods_etf_fund_adj
        WHERE trade_date = '{trade_date}'
        ORDER BY ts_code
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
