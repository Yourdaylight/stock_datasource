"""TuShare ETF fund daily data query service."""

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


class TuShareETFFundDailyService(BaseService):
    """Query service for TuShare ETF fund daily data."""
    
    def __init__(self):
        super().__init__("tushare_etf_fund_daily")
    
    @query_method(
        description="Query ETF daily data by code and date range",
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
    def get_etf_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """Query ETF daily data by code and date range.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of ETF daily data records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM ods_etf_fund_daily
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest ETF daily data",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of latest records",
                required=False,
                default=10,
            ),
        ]
    )
    def get_latest_etf_daily(
        self,
        ts_code: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Query latest ETF daily data.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
            limit: Number of latest records
        
        Returns:
            List of latest ETF daily data records
        """
        query = f"""
        SELECT 
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            change,
            pct_chg,
            vol,
            amount
        FROM ods_etf_fund_daily
        WHERE ts_code = '{ts_code}'
        ORDER BY trade_date DESC
        LIMIT {limit}
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get ETF daily statistics",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code",
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
    def get_etf_daily_stats(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """Get ETF daily statistics.
        
        Args:
            ts_code: ETF code
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
        FROM ods_etf_fund_daily
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        """
        
        df = self.db.execute_query(query)
        if df.empty:
            return {}
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
