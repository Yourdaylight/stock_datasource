"""TuShare stock HSGT query service."""

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


class TuShareStockHSGTService(BaseService):
    """Query service for TuShare stock HSGT (沪深港通) data."""
    
    def __init__(self):
        super().__init__("tushare_stock_hsgt")
    
    @query_method(
        description="Query HSGT stocks by trade date and type",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="hsgt_type",
                type="str",
                description="Type: HK_SZ(深股通) SZ_HK(港股通深) HK_SH(沪股通) SH_HK(港股通沪)",
                required=False,
            ),
        ]
    )
    def get_hsgt_stocks_by_date(
        self,
        trade_date: str,
        hsgt_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Query HSGT stocks by trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            hsgt_type: Type (optional, returns all if not specified)
        
        Returns:
            List of HSGT stock records
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            type,
            name,
            type_name
        FROM ods_stock_hsgt
        WHERE trade_date = %(trade_date)s
        """
        params = {'trade_date': trade_date}
        
        if hsgt_type:
            query += " AND type = %(hsgt_type)s"
            params['hsgt_type'] = hsgt_type
        
        query += " ORDER BY type, ts_code ASC"
        
        df = self.db.execute_query(query, params)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Check if a stock is in HSGT list on a specific date",
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
    def is_stock_in_hsgt(
        self,
        ts_code: str,
        trade_date: str,
    ) -> Dict[str, Any]:
        """
        Check if a stock is in HSGT list on a specific date.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            Dict with is_hsgt flag and HSGT info if applicable
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            type,
            name,
            type_name
        FROM ods_stock_hsgt
        WHERE ts_code = %(ts_code)s
        AND trade_date = %(trade_date)s
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'ts_code': ts_code, 'trade_date': trade_date})
        
        if df.empty:
            return {"is_hsgt": False, "ts_code": ts_code, "trade_date": trade_date}
        
        record = df.iloc[0].to_dict()
        record = _convert_to_json_serializable(record)
        record["is_hsgt"] = True
        return record
    
    @query_method(
        description="Get latest HSGT stocks list",
        params=[
            QueryParam(
                name="hsgt_type",
                type="str",
                description="Type: HK_SZ(深股通) SZ_HK(港股通深) HK_SH(沪股通) SH_HK(港股通沪)",
                required=False,
            ),
        ]
    )
    def get_latest_hsgt_stocks(
        self,
        hsgt_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Get latest HSGT stocks list.
        
        Args:
            hsgt_type: Type (optional)
        
        Returns:
            List of latest HSGT stock records
        """
        if hsgt_type:
            query = """
            SELECT 
                ts_code,
                trade_date,
                type,
                name,
                type_name
            FROM ods_stock_hsgt
            WHERE type = %(hsgt_type)s
            AND trade_date = (SELECT max(trade_date) FROM ods_stock_hsgt WHERE type = %(hsgt_type)s)
            ORDER BY ts_code ASC
            """
            df = self.db.execute_query(query, {'hsgt_type': hsgt_type})
        else:
            query = """
            SELECT 
                ts_code,
                trade_date,
                type,
                name,
                type_name
            FROM ods_stock_hsgt
            WHERE trade_date = (SELECT max(trade_date) FROM ods_stock_hsgt)
            ORDER BY type, ts_code ASC
            """
            df = self.db.execute_query(query)
        
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query HSGT history for a specific stock",
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
    def get_hsgt_history_by_code(
        self,
        ts_code: str,
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Query HSGT history for a specific stock.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
        
        Returns:
            List of HSGT history records
        """
        query = """
        SELECT 
            ts_code,
            trade_date,
            type,
            name,
            type_name
        FROM ods_stock_hsgt
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
        description="Get HSGT stock count by type and date",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_hsgt_count_by_type(
        self,
        trade_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Get HSGT stock count by type for a specific date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
        
        Returns:
            List of type counts
        """
        query = """
        SELECT 
            type,
            type_name,
            count(*) as stock_count
        FROM ods_stock_hsgt
        WHERE trade_date = %(trade_date)s
        GROUP BY type, type_name
        ORDER BY type
        """
        
        df = self.db.execute_query(query, {'trade_date': trade_date})
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
