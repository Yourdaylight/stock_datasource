"""TuShare Hong Kong Stock Trade Calendar query service."""

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


class TuShareHKTradeCalService(BaseService):
    """Query service for TuShare Hong Kong Stock trade calendar."""
    
    def __init__(self):
        super().__init__("tushare_hk_tradecal")
    
    @query_method(
        description="Query HK trade calendar by date range",
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
        ]
    )
    def get_trade_calendar(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query HK trade calendar.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of trade calendar records
        """
        query = """
        SELECT 
            cal_date,
            is_open,
            pretrade_date
        FROM ods_hk_trade_calendar
        WHERE cal_date >= %(start_date)s
        AND cal_date <= %(end_date)s
        ORDER BY cal_date ASC
        """
        
        df = self.db.execute_query(query, {
            'start_date': start_date,
            'end_date': end_date
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query HK trading days only by date range",
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
        ]
    )
    def get_trading_days(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query HK trading days only (is_open=1).
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of trading day records
        """
        query = """
        SELECT 
            cal_date,
            is_open,
            pretrade_date
        FROM ods_hk_trade_calendar
        WHERE cal_date >= %(start_date)s
        AND cal_date <= %(end_date)s
        AND is_open = 1
        ORDER BY cal_date ASC
        """
        
        df = self.db.execute_query(query, {
            'start_date': start_date,
            'end_date': end_date
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get next HK trading day after given date",
        params=[
            QueryParam(
                name="date",
                type="str",
                description="Reference date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_next_trading_day(
        self,
        date: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get next HK trading day after given date.
        
        Args:
            date: Reference date in YYYYMMDD format
        
        Returns:
            Next trading day record or None
        """
        query = """
        SELECT 
            cal_date,
            is_open,
            pretrade_date
        FROM ods_hk_trade_calendar
        WHERE cal_date > %(date)s
        AND is_open = 1
        ORDER BY cal_date ASC
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'date': date})
        if df.empty:
            return None
        records = df.to_dict('records')
        return _convert_to_json_serializable(records[0]) if records else None
    
    @query_method(
        description="Get previous HK trading day before given date",
        params=[
            QueryParam(
                name="date",
                type="str",
                description="Reference date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_prev_trading_day(
        self,
        date: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get previous HK trading day before given date.
        
        Args:
            date: Reference date in YYYYMMDD format
        
        Returns:
            Previous trading day record or None
        """
        query = """
        SELECT 
            cal_date,
            is_open,
            pretrade_date
        FROM ods_hk_trade_calendar
        WHERE cal_date < %(date)s
        AND is_open = 1
        ORDER BY cal_date DESC
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'date': date})
        if df.empty:
            return None
        records = df.to_dict('records')
        return _convert_to_json_serializable(records[0]) if records else None
    
    @query_method(
        description="Check if a given date is a HK trading day",
        params=[
            QueryParam(
                name="date",
                type="str",
                description="Date to check in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def is_trading_day(
        self,
        date: str,
    ) -> bool:
        """
        Check if a given date is a HK trading day.
        
        Args:
            date: Date to check in YYYYMMDD format
        
        Returns:
            True if trading day, False otherwise
        """
        query = """
        SELECT is_open
        FROM ods_hk_trade_calendar
        WHERE cal_date = %(date)s
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'date': date})
        if df.empty:
            return False
        return bool(df.iloc[0]['is_open'])
    
    @query_method(
        description="Count trading days in a date range",
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
        ]
    )
    def count_trading_days(
        self,
        start_date: str,
        end_date: str,
    ) -> int:
        """
        Count trading days in a date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            Number of trading days
        """
        query = """
        SELECT COUNT(*) as cnt
        FROM ods_hk_trade_calendar
        WHERE cal_date >= %(start_date)s
        AND cal_date <= %(end_date)s
        AND is_open = 1
        """
        
        df = self.db.execute_query(query, {
            'start_date': start_date,
            'end_date': end_date
        })
        if df.empty:
            return 0
        return int(df.iloc[0]['cnt'])
    
    @query_method(
        description="Get N trading days after/before given date",
        params=[
            QueryParam(
                name="date",
                type="str",
                description="Reference date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="n",
                type="int",
                description="Number of trading days (positive=forward, negative=backward)",
                required=True,
            ),
        ]
    )
    def get_offset_trading_day(
        self,
        date: str,
        n: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Get N trading days after (positive n) or before (negative n) given date.
        
        Args:
            date: Reference date in YYYYMMDD format
            n: Number of trading days offset
        
        Returns:
            Trading day record or None
        """
        if n == 0:
            query = """
            SELECT cal_date, is_open, pretrade_date
            FROM ods_hk_trade_calendar
            WHERE cal_date = %(date)s
            LIMIT 1
            """
            df = self.db.execute_query(query, {'date': date})
        elif n > 0:
            query = """
            SELECT cal_date, is_open, pretrade_date
            FROM ods_hk_trade_calendar
            WHERE cal_date > %(date)s
            AND is_open = 1
            ORDER BY cal_date ASC
            LIMIT 1 OFFSET %(offset)s
            """
            df = self.db.execute_query(query, {'date': date, 'offset': n - 1})
        else:
            query = """
            SELECT cal_date, is_open, pretrade_date
            FROM ods_hk_trade_calendar
            WHERE cal_date < %(date)s
            AND is_open = 1
            ORDER BY cal_date DESC
            LIMIT 1 OFFSET %(offset)s
            """
            df = self.db.execute_query(query, {'date': date, 'offset': abs(n) - 1})
        
        if df.empty:
            return None
        records = df.to_dict('records')
        return _convert_to_json_serializable(records[0]) if records else None
