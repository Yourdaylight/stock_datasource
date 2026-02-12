"""TuShare Hong Kong Stock Daily Adjusted data query service."""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
import pandas as pd

from stock_datasource.core.base_service import BaseService


class TuShareHKDailyAdjService(BaseService):
    """Service for querying HK daily adjusted data."""
    
    def __init__(self):
        super().__init__(plugin_name="tushare_hk_daily_adj")
    
    @property
    def table_name(self) -> str:
        return "ods_hk_daily_adj"
    
    @property
    def service_name(self) -> str:
        return "tushare_hk_daily_adj"
    
    def get_by_date(self, trade_date: str) -> List[Dict[str, Any]]:
        """Get all HK stocks for a specific date.
        
        Args:
            trade_date: Date in YYYYMMDD format
        
        Returns:
            List of stock records
        """
        formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        sql = """
            SELECT * FROM ods_hk_daily_adj
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
        """Get daily adjusted data for a specific stock.
        
        Args:
            ts_code: Stock code (e.g., '00001.HK')
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            limit: Maximum number of records
        
        Returns:
            List of daily records
        """
        params = {'ts_code': ts_code, 'limit': limit}
        
        sql = "SELECT * FROM ods_hk_daily_adj WHERE ts_code = %(ts_code)s"
        
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
        """Get the latest daily adjusted data for a stock.
        
        Args:
            ts_code: Stock code
        
        Returns:
            Latest record or None
        """
        sql = """
            SELECT * FROM ods_hk_daily_adj
            WHERE ts_code = %(ts_code)s
            ORDER BY trade_date DESC
            LIMIT 1
        """
        df = self.db.execute_query(sql, {'ts_code': ts_code})
        return df.to_dict('records')[0] if not df.empty else None
    
    def get_adj_close(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """Get adjusted close prices for a stock.
        
        Calculates: close * adj_factor = 前复权收盘价
        
        Args:
            ts_code: Stock code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of {trade_date, close, adj_factor, adj_close}
        """
        formatted_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        formatted_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
        
        sql = """
            SELECT 
                trade_date,
                close,
                adj_factor,
                close * adj_factor as adj_close
            FROM ods_hk_daily_adj
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
        return df.to_dict('records') if not df.empty else []
    
    def get_market_value(
        self,
        trade_date: str,
        top_n: int = 20
    ) -> List[Dict[str, Any]]:
        """Get top stocks by market value for a date.
        
        Args:
            trade_date: Date in YYYYMMDD format
            top_n: Number of top stocks to return
        
        Returns:
            List of stocks sorted by total_mv
        """
        formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        
        sql = """
            SELECT 
                ts_code,
                close,
                total_mv,
                free_mv,
                total_share,
                free_share,
                turnover_ratio
            FROM ods_hk_daily_adj
            WHERE trade_date = %(trade_date)s
              AND total_mv IS NOT NULL
            ORDER BY total_mv DESC
            LIMIT %(top_n)s
        """
        df = self.db.execute_query(sql, {'trade_date': formatted_date, 'top_n': top_n})
        return df.to_dict('records') if not df.empty else []
    
    def get_high_turnover(
        self,
        trade_date: str,
        min_turnover: float = 5.0,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get stocks with high turnover ratio.
        
        Args:
            trade_date: Date in YYYYMMDD format
            min_turnover: Minimum turnover ratio percentage
            limit: Maximum records
        
        Returns:
            List of high turnover stocks
        """
        formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        
        sql = """
            SELECT 
                ts_code,
                close,
                pct_change,
                vol,
                amount,
                turnover_ratio
            FROM ods_hk_daily_adj
            WHERE trade_date = %(trade_date)s
              AND turnover_ratio >= %(min_turnover)s
            ORDER BY turnover_ratio DESC
            LIMIT %(limit)s
        """
        df = self.db.execute_query(sql, {
            'trade_date': formatted_date,
            'min_turnover': min_turnover,
            'limit': limit
        })
        return df.to_dict('records') if not df.empty else []
    
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
                    avg(turnover_ratio) as avg_turnover,
                    sum(amount) as total_amount
                FROM ods_hk_daily_adj
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
                FROM ods_hk_daily_adj
            """
            df = self.db.execute_query(sql, {})
        
        return df.to_dict('records')[0] if not df.empty else {}
