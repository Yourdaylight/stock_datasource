"""ETF基准指数列表 service for querying data."""

import logging
from typing import Dict, Any, List, Optional
from datetime import date, datetime
import pandas as pd

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client
    return db_client


def _execute_query(query: str) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dicts."""
    db = _get_db()
    df = db.execute_query(query)
    if df is None or df.empty:
        return []
    
    # Convert datetime columns to string for JSON serialization
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]' or isinstance(df[col].iloc[0] if len(df) > 0 else None, (datetime, date, pd.Timestamp)):
            df[col] = df[col].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else None)
    
    return df.to_dict('records')


class ETFIndexService:
    """Service for querying ETF基准指数列表 data."""
    
    TABLE_NAME = "ods_etf_index"
    
    def __init__(self):
        """Initialize service."""
        self.db = _get_db()
    
    def get_all(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get all ETF基准指数列表.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of ETF基准指数 records
        """
        query = f"""
            SELECT 
                ts_code,
                indx_name,
                indx_csname,
                pub_party_name,
                pub_date,
                base_date,
                bp,
                adj_circle
            FROM {self.TABLE_NAME}
            ORDER BY ts_code
            LIMIT {int(limit)}
        """
        return _execute_query(query)
    
    def get_by_ts_code(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get ETF基准指数 by ts_code.
        
        Args:
            ts_code: 指数代码
            
        Returns:
            ETF基准指数 record or None
        """
        # Sanitize input to prevent SQL injection
        safe_ts_code = ts_code.replace("'", "''")
        
        query = f"""
            SELECT 
                ts_code,
                indx_name,
                indx_csname,
                pub_party_name,
                pub_date,
                base_date,
                bp,
                adj_circle
            FROM {self.TABLE_NAME}
            WHERE ts_code = '{safe_ts_code}'
            LIMIT 1
        """
        
        records = _execute_query(query)
        return records[0] if records else None
    
    def search_by_name(self, name: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Search ETF基准指数 by name (fuzzy match).
        
        Args:
            name: 指数名称（模糊匹配）
            limit: Maximum number of records to return
            
        Returns:
            List of matching ETF基准指数 records
        """
        # Sanitize input
        safe_name = name.replace("'", "''").replace("%", "\\%")
        
        query = f"""
            SELECT 
                ts_code,
                indx_name,
                indx_csname,
                pub_party_name,
                pub_date,
                base_date,
                bp,
                adj_circle
            FROM {self.TABLE_NAME}
            WHERE indx_name LIKE '%{safe_name}%'
               OR indx_csname LIKE '%{safe_name}%'
            ORDER BY ts_code
            LIMIT {int(limit)}
        """
        return _execute_query(query)
    
    def get_by_publisher(self, publisher: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Get ETF基准指数 by publisher.
        
        Args:
            publisher: 指数发布机构
            limit: Maximum number of records to return
            
        Returns:
            List of ETF基准指数 records from the publisher
        """
        # Sanitize input
        safe_publisher = publisher.replace("'", "''").replace("%", "\\%")
        
        query = f"""
            SELECT 
                ts_code,
                indx_name,
                indx_csname,
                pub_party_name,
                pub_date,
                base_date,
                bp,
                adj_circle
            FROM {self.TABLE_NAME}
            WHERE pub_party_name LIKE '%{safe_publisher}%'
            ORDER BY ts_code
            LIMIT {int(limit)}
        """
        return _execute_query(query)
    
    def get_publishers(self) -> List[Dict[str, Any]]:
        """Get all unique publishers with count.
        
        Returns:
            List of publishers with their index count
        """
        query = f"""
            SELECT 
                pub_party_name,
                count() as index_count
            FROM {self.TABLE_NAME}
            WHERE pub_party_name != ''
            GROUP BY pub_party_name
            ORDER BY index_count DESC
        """
        return _execute_query(query)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics of ETF基准指数列表.
        
        Returns:
            Statistics including total count, publisher count, etc.
        """
        # pub_date and base_date are stored as String (YYYY-MM-DD format)
        # Filter out empty strings for date aggregations
        query = f"""
            SELECT 
                count() as total_count,
                count(DISTINCT pub_party_name) as publisher_count,
                min(CASE WHEN pub_date != '' THEN pub_date ELSE NULL END) as earliest_pub_date,
                max(CASE WHEN pub_date != '' THEN pub_date ELSE NULL END) as latest_pub_date,
                avg(bp) as avg_base_point
            FROM {self.TABLE_NAME}
        """
        
        records = _execute_query(query)
        return records[0] if records else {}


# Create singleton instance
_service_instance = None


def get_service() -> ETFIndexService:
    """Get or create ETFIndexService singleton instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = ETFIndexService()
    return _service_instance
