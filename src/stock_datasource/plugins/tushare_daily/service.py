"""TuShare daily data query service."""

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


class TuShareDailyService(BaseService):
    """Query service for TuShare daily stock data."""
    
    def __init__(self):
        super().__init__("tushare_daily")
    
    @query_method(
        description="Query daily stock data by code and date range",
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
    def get_daily_data(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query daily stock data.
        
        Args:
            code: Stock code (e.g., 000001.SZ)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of daily data records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            vol,
            amount
        FROM ods_daily
        WHERE ts_code = '{code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest daily data for multiple stocks",
        params=[
            QueryParam(
                name="codes",
                type="list",
                description="List of stock codes",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of latest records per stock",
                required=False,
                default=1,
            ),
        ]
    )
    def get_latest_daily(
        self,
        codes: List[str],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query latest daily data for multiple stocks.
        
        Args:
            codes: List of stock codes
            limit: Number of latest records per stock
        
        Returns:
            List of latest daily data records
        """
        codes_str = "','".join(codes)
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            vol,
            amount
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_daily
            WHERE ts_code IN ('{codes_str}')
        )
        WHERE rn <= {limit}
        ORDER BY ts_code, trade_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get daily data statistics for a stock",
        params=[
            QueryParam(
                name="code",
                type="str",
                description="Stock code",
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
    def get_daily_stats(
        self,
        code: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Get daily data statistics for a stock.
        
        Args:
            code: Stock code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            Statistics dictionary
        """
        query = f"""
        SELECT 
            COUNT(*) as trading_days,
            MIN(close) as min_close,
            MAX(close) as max_close,
            AVG(close) as avg_close,
            SUM(vol) as total_volume,
            SUM(amount) as total_amount
        FROM ods_daily
        WHERE ts_code = '{code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return {}
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
