"""TuShare stock ST query service."""

from typing import Any, Dict, List
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


class TuShareStockSTService(BaseService):
    """Query service for TuShare stock ST data."""
    
    def __init__(self):
        super().__init__("tushare_stock_st")
    
    @query_method(
        description="Query ST stocks by trade date",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_st_stocks_by_date(
        self,
        trade_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query ST stocks by trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            List of ST stock records
        """
        query = """
        SELECT 
            ts_code,
            name,
            trade_date,
            type,
            type_name
        FROM ods_stock_st
        WHERE trade_date = %(trade_date)s
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query, {'trade_date': trade_date})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query ST history for a specific stock",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Stock code, e.g., 000001.SZ",
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
    def get_st_history_by_code(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Query ST history for a specific stock.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
        
        Returns:
            List of ST history records
        """
        query = """
        SELECT 
            ts_code,
            name,
            trade_date,
            type,
            type_name
        FROM ods_stock_st
        WHERE ts_code = %(ts_code)s
        """
        params = {'ts_code': ts_code}
        
        if start_date:
            query += " AND trade_date >= %(start_date)s"
            params['start_date'] = start_date
        if end_date:
            query += " AND trade_date <= %(end_date)s"
            params['end_date'] = end_date
        
        query += " ORDER BY trade_date DESC"
        
        df = self.db.execute_query(query, params)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get latest ST stocks list",
        params=[]
    )
    def get_latest_st_stocks(self) -> List[Dict[str, Any]]:
        """
        Get latest ST stocks list.
        
        Returns:
            List of latest ST stock records
        """
        query = """
        SELECT 
            ts_code,
            name,
            trade_date,
            type,
            type_name
        FROM ods_stock_st
        WHERE trade_date = (SELECT max(trade_date) FROM ods_stock_st)
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Check if a stock is ST on a specific date",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Stock code, e.g., 000001.SZ",
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
    def is_stock_st(
        self,
        ts_code: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """
        Check if a stock is ST on a specific date.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            Dict with is_st flag and ST info if applicable
        """
        query = """
        SELECT 
            ts_code,
            name,
            trade_date,
            type,
            type_name
        FROM ods_stock_st
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'ts_code': ts_code, 'trade_date': trade_date})
        
        if df.empty:
            return {"is_st": False, "ts_code": ts_code, "trade_date": trade_date}
        
        record = df.iloc[0].to_dict()
        record = _convert_to_json_serializable(record)
        record["is_st"] = True
        return record
    
    @query_method(
        description="Query ST stocks by date range",
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
    def get_st_stocks_by_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Query ST stocks by date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of ST stock records
        """
        query = """
        SELECT 
            ts_code,
            name,
            trade_date,
            type,
            type_name
        FROM ods_stock_st
        WHERE trade_date >= %(start_date)s
        AND trade_date <= %(end_date)s
        ORDER BY trade_date DESC, ts_code ASC
        """
        
        df = self.db.execute_query(query, {'start_date': start_date, 'end_date': end_date})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
