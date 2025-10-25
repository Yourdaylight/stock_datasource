"""TuShare trade calendar query service."""

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


class TuShareTradeCalendarService(BaseService):
    """Query service for TuShare trade calendar."""
    
    def __init__(self):
        super().__init__("tushare_trade_calendar")
    
    @query_method(
        description="Query trade calendar by date range",
        params=[
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
            QueryParam(
                name="exchange",
                type="str",
                description="Exchange code (SSE/SZSE)",
                required=False,
                default="SSE",
            ),
        ]
    )
    def get_trade_calendar(\
        self,
        start_date: str,
        end_date: str,
        exchange: str = "SSE",
    ) -> List[Dict[str, Any]]:
        """
        Query trade calendar.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            List of trade calendar records
        """
        query = f"""
        SELECT 
            exchange,
            cal_date,
            is_open,
            pretrade_date
        FROM ods_trade_calendar
        WHERE exchange = '{exchange}'
        AND cal_date >= '{start_date}'
        AND cal_date <= '{end_date}'
        ORDER BY cal_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query trading days by date range",
        params=[
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
            QueryParam(
                name="exchange",
                type="str",
                description="Exchange code (SSE/SZSE)",
                required=False,
                default="SSE",
            ),
        ]
    )
    def get_trading_days(\
        self,
        start_date: str,
        end_date: str,
        exchange: str = "SSE",
    ) -> List[Dict[str, Any]]:
        """
        Query trading days only.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            List of trading day records
        """
        query = f"""
        SELECT 
            exchange,
            cal_date,
            is_open,
            pretrade_date
        FROM ods_trade_calendar
        WHERE exchange = '{exchange}'
        AND cal_date >= '{start_date}'
        AND cal_date <= '{end_date}'
        AND is_open = 1
        ORDER BY cal_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get next trading day",
        params=[
            QueryParam(
                name="date",
                type="str",
                description="Reference date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="exchange",
                type="str",
                description="Exchange code (SSE/SZSE)",
                required=False,
                default="SSE",
            ),
        ]
    )
    def get_next_trading_day(\
        self,
        date: str,
        exchange: str = "SSE",
    ) -> List[Dict[str, Any]]:
        """
        Get next trading day after given date.
        
        Args:
            date: Reference date in YYYYMMDD format
            exchange: Exchange code (SSE/SZSE)
        
        Returns:
            List containing next trading day record
        """
        query = f"""
        SELECT 
            exchange,
            cal_date,
            is_open,
            pretrade_date
        FROM ods_trade_calendar
        WHERE exchange = '{exchange}'
        AND cal_date > '{date}'
        AND is_open = 1
        ORDER BY cal_date ASC
        LIMIT 1
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
