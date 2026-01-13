"""TuShare ETF stk_mins data query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in (obj.items() if isinstance(obj, dict) else obj.items())}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareETFStkMinsService(BaseService):
    """Query service for TuShare ETF stk_mins data."""
    
    def __init__(self):
        super().__init__("tushare_etf_stk_mins")
    
    @query_method(
        description="Query ETF minute data by code, frequency and time range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
                required=True,
            ),
            QueryParam(
                name="freq",
                type="str",
                description="Frequency: 1min/5min/15min/30min/60min",
                required=True,
            ),
            QueryParam(
                name="start_time",
                type="str",
                description="Start time in YYYY-MM-DD HH:MM:SS format",
                required=True,
            ),
            QueryParam(
                name="end_time",
                type="str",
                description="End time in YYYY-MM-DD HH:MM:SS format",
                required=True,
            ),
        ]
    )
    def get_etf_mins(
        self,
        ts_code: str,
        freq: str,
        start_time: str,
        end_time: str,
    ) -> List[Dict[str, Any]]:
        """Query ETF minute data by code, frequency and time range.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
            freq: Frequency (1min/5min/15min/30min/60min)
            start_time: Start time in YYYY-MM-DD HH:MM:SS format
            end_time: End time in YYYY-MM-DD HH:MM:SS format
        
        Returns:
            List of ETF minute data records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_time,
            freq,
            open,
            high,
            low,
            close,
            vol,
            amount
        FROM ods_etf_stk_mins
        WHERE ts_code = '{ts_code}'
        AND freq = '{freq}'
        AND trade_time >= '{start_time}'
        AND trade_time <= '{end_time}'
        ORDER BY trade_time ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest ETF minute data",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
                required=True,
            ),
            QueryParam(
                name="freq",
                type="str",
                description="Frequency: 1min/5min/15min/30min/60min",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of latest records",
                required=False,
                default=100,
            ),
        ]
    )
    def get_latest_etf_mins(
        self,
        ts_code: str,
        freq: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query latest ETF minute data.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
            freq: Frequency (1min/5min/15min/30min/60min)
            limit: Number of latest records
        
        Returns:
            List of latest ETF minute data records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_time,
            freq,
            open,
            high,
            low,
            close,
            vol,
            amount
        FROM ods_etf_stk_mins
        WHERE ts_code = '{ts_code}'
        AND freq = '{freq}'
        ORDER BY trade_time DESC
        LIMIT {limit}
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get ETF minute data statistics",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code",
                required=True,
            ),
            QueryParam(
                name="freq",
                type="str",
                description="Frequency: 1min/5min/15min/30min/60min",
                required=True,
            ),
            QueryParam(
                name="start_time",
                type="str",
                description="Start time in YYYY-MM-DD HH:MM:SS format",
                required=True,
            ),
            QueryParam(
                name="end_time",
                type="str",
                description="End time in YYYY-MM-DD HH:MM:SS format",
                required=True,
            ),
        ]
    )
    def get_etf_mins_stats(
        self,
        ts_code: str,
        freq: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """Get ETF minute data statistics.
        
        Args:
            ts_code: ETF code
            freq: Frequency
            start_time: Start time in YYYY-MM-DD HH:MM:SS format
            end_time: End time in YYYY-MM-DD HH:MM:SS format
        
        Returns:
            Statistics dictionary
        """
        query = f"""
        SELECT 
            COUNT(*) as bar_count,
            MIN(close) as min_close,
            MAX(close) as max_close,
            AVG(close) as avg_close,
            SUM(vol) as total_volume,
            SUM(amount) as total_amount
        FROM ods_etf_stk_mins
        WHERE ts_code = '{ts_code}'
        AND freq = '{freq}'
        AND trade_time >= '{start_time}'
        AND trade_time <= '{end_time}'
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return {}
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
