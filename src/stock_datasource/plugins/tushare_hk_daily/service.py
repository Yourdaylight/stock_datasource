"""TuShare Hong Kong Stock Daily data query service."""

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


class TuShareHKDailyService(BaseService):
    """Query service for TuShare Hong Kong Stock daily data."""
    
    def __init__(self):
        super().__init__("tushare_hk_daily")
    
    @query_method(
        description="Query HK stock daily data by code and date range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="HK Stock code, e.g., 00001.HK",
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
    def get_by_date_range(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query HK stock daily data by code and date range.
        
        Args:
            ts_code: HK Stock code (e.g., 00001.HK)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of daily data records
        """
        query = """
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
        FROM ods_hk_daily
        WHERE ts_code = %(ts_code)s
        AND trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query all HK stocks' daily data for a specific trade date",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD or YYYY-MM-DD format",
                required=True,
            ),
        ]
    )
    def get_by_trade_date(
        self,
        trade_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query all HK stocks' daily data for a specific trade date.
        
        Args:
            trade_date: Trade date (YYYYMMDD or YYYY-MM-DD)
        
        Returns:
            List of daily data records for all HK stocks
        """
        query = """
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
        FROM ods_hk_daily
        WHERE trade_date = %(trade_date)s
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query, {'trade_date': trade_date})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest HK stock daily data for multiple stocks",
        params=[
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of HK stock codes (e.g., ['00001.HK', '00700.HK'])",
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
    def get_latest(
        self,
        ts_codes: List[str],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query latest HK stock daily data for multiple stocks.
        
        Args:
            ts_codes: List of HK stock codes
            limit: Number of latest records per stock
        
        Returns:
            List of latest daily data records
        """
        query = """
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
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_hk_daily
            WHERE ts_code IN %(ts_codes)s
        )
        WHERE rn <= %(limit)s
        ORDER BY ts_code, trade_date DESC
        """
        
        df = self.db.execute_query(query, {
            'ts_codes': ts_codes,
            'limit': limit
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get HK stock daily data statistics for a date range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="HK Stock code, e.g., 00001.HK",
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
    def get_stats(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Get HK stock daily data statistics for a date range.
        
        Args:
            ts_code: HK Stock code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            Statistics dictionary
        """
        query = """
        SELECT 
            COUNT(*) as trading_days,
            MIN(close) as min_close,
            MAX(close) as max_close,
            AVG(close) as avg_close,
            SUM(vol) as total_volume,
            SUM(amount) as total_amount
        FROM ods_hk_daily
        WHERE ts_code = %(ts_code)s
        AND trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        """
        
        df = self.db.execute_query(query, {
            'ts_code': ts_code,
            'start_date': start_date,
            'end_date': end_date
        })
        if df.empty:
            return {}
        
        return _convert_to_json_serializable(df.iloc[0].to_dict())
    
    @query_method(
        description="Get the latest trade date available in HK daily database",
        params=[]
    )
    def get_latest_trade_date(self) -> Optional[str]:
        """Get the latest trade date available in the HK daily database."""
        query = "SELECT max(trade_date) as max_date FROM ods_hk_daily"
        df = self.db.execute_query(query)
        if df.empty or df.iloc[0]['max_date'] is None:
            return None
        date_val = df.iloc[0]['max_date']
        if hasattr(date_val, 'strftime'):
            return date_val.strftime('%Y-%m-%d')
        return str(date_val).split()[0].split('T')[0]
    
    @query_method(
        description="Get top gainers/losers for a specific trade date",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="top_n",
                type="int",
                description="Number of top stocks to return",
                required=False,
                default=10,
            ),
            QueryParam(
                name="order_by",
                type="str",
                description="Order by field: 'pct_chg' (default), 'amount', 'vol'",
                required=False,
                default="pct_chg",
            ),
            QueryParam(
                name="ascending",
                type="bool",
                description="Sort ascending (losers) or descending (gainers)",
                required=False,
                default=False,
            ),
        ]
    )
    def get_top_movers(
        self,
        trade_date: str,
        top_n: int = 10,
        order_by: str = "pct_chg",
        ascending: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get top gainers or losers for a specific trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            top_n: Number of top stocks to return
            order_by: Field to order by (pct_chg, amount, vol)
            ascending: True for losers, False for gainers
        
        Returns:
            List of top mover records
        """
        # Whitelist validation for order_by field
        allowed_order_fields = {'pct_chg', 'amount', 'vol'}
        if order_by not in allowed_order_fields:
            order_by = 'pct_chg'
        
        order_direction = 'ASC' if ascending else 'DESC'
        
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
        FROM ods_hk_daily
        WHERE trade_date = %(trade_date)s
        ORDER BY {order_by} {order_direction}
        LIMIT %(top_n)s
        """
        
        df = self.db.execute_query(query, {
            'trade_date': trade_date,
            'top_n': top_n
        })
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
