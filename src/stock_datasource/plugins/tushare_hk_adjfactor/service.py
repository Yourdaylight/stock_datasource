"""TuShare Hong Kong Stock Adjustment Factor query service."""

from typing import Dict, Any, List, Optional
import pandas as pd

from stock_datasource.core.base_service import BaseService


class TuShareHKAdjFactorService(BaseService):
    """Service for querying HK adjustment factor data."""
    
    def __init__(self):
        super().__init__(plugin_name="tushare_hk_adjfactor")
    
    @property
    def table_name(self) -> str:
        return "ods_hk_adjfactor"
    
    @property
    def service_name(self) -> str:
        return "tushare_hk_adjfactor"
    
    def get_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        """Get all HK stocks adjustment factor for a specific date.
        
        Args:
            trade_date: Date in YYYYMMDD format
        
        Returns:
            List of adjustment factor records
        """
        formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        sql = """
            SELECT * FROM ods_hk_adjfactor
            WHERE trade_date = %(trade_date)s
            ORDER BY ts_code
        """
        df = self.db.execute_query(sql, {'trade_date': formatted_date})
        return df.to_dict('records') if not df.empty else []
    
    def get_by_ts_code(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get adjustment factor for a specific stock.
        
        Args:
            ts_code: Stock code (e.g., '00001.HK')
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            limit: Maximum number of records
        
        Returns:
            List of adjustment factor records
        """
        params = {'ts_code': ts_code, 'limit': limit}
        
        sql = "SELECT * FROM ods_hk_adjfactor WHERE ts_code = %(ts_code)s"
        
        if start_date:
            formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            sql += " AND trade_date >= %(start_date)s"
            params['start_date'] = formatted_start
        
        if end_date:
            formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            sql += " AND trade_date <= %(end_date)s"
            params['end_date'] = formatted_end
        
        sql += " ORDER BY trade_date DESC LIMIT %(limit)s"
        
        df = self.db.execute_query(sql, params)
        return df.to_dict('records') if not df.empty else []
    
    def get_latest(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get the latest adjustment factor for a stock.
        
        Args:
            ts_code: Stock code
        
        Returns:
            Latest record or None
        """
        sql = """
            SELECT * FROM ods_hk_adjfactor
            WHERE ts_code = %(ts_code)s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        df = self.db.execute_query(sql, {'ts_code': ts_code})
        return df.to_dict('records')[0] if not df.empty else None
    
    def get_adj_factor_change(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get adjustment factor changes (when factor changes from previous day).
        
        Args:
            ts_code: Stock code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of records where adj_factor changed
        """
        formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        
        sql = """
            SELECT 
                ts_code,
                trade_date,
                cum_adjfactor,
                close_price,
                lagInFrame(cum_adjfactor, 1) OVER (ORDER BY trade_date) as prev_adjfactor
            FROM ods_hk_adjfactor
            WHERE ts_code = %(ts_code)s
              AND trade_date >= %(start_date)s
              AND trade_date <= %(end_date)s
            ORDER BY trade_date
        """
        df = self.db.execute_query(sql, {
            'ts_code': ts_code,
            'start_date': formatted_start,
            'end_date': formatted_end
        })
        
        if df.empty:
            return []
        
        # Filter where factor changed
        df = df[df['cum_adjfactor'] != df['prev_adjfactor']]
        return df.to_dict('records') if not df.empty else []
    
    def calculate_adjusted_price(
        self,
        ts_code: str,
        trade_date: str,
        price: float
    ) -> Optional[float]:
        """Calculate adjusted price using the adjustment factor.
        
        Args:
            ts_code: Stock code
            trade_date: Date in YYYYMMDD format
            price: Original price
        
        Returns:
            Adjusted price or None if no factor found
        """
        formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        
        sql = """
            SELECT cum_adjfactor FROM ods_hk_adjfactor
            WHERE ts_code = %(ts_code)s AND trade_date = %(trade_date)s
            LIMIT 1
        """
        df = self.db.execute_query(sql, {'ts_code': ts_code, 'trade_date': formatted_date})
        
        if df.empty:
            return None
        
        factor = df.iloc[0]['cum_adjfactor']
        return price * factor if factor else None
    
    def get_statistics(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics of the data.
        
        Args:
            trade_date: Optional date filter
        
        Returns:
            Statistics dict
        """
        if trade_date:
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
            sql = """
                SELECT 
                    count() as total_records,
                    count(DISTINCT ts_code) as unique_stocks,
                    min(trade_date) as min_date,
                    max(trade_date) as max_date,
                    avg(cum_adjfactor) as avg_adjfactor
                FROM ods_hk_adjfactor
                WHERE trade_date = %(trade_date)s
            """
            df = self.db.execute_query(sql, {'trade_date': formatted_date})
        else:
            sql = """
                SELECT 
                    count() as total_records,
                    count(DISTINCT ts_code) as unique_stocks,
                    min(trade_date) as min_date,
                    max(trade_date) as max_date
                FROM ods_hk_adjfactor
            """
            df = self.db.execute_query(sql, {})
        
        return df.to_dict('records')[0] if not df.empty else {}
