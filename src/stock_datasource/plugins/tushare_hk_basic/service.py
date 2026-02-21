"""TuShare Hong Kong Stock Basic Info query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareHKBasicService(BaseService):
    """Query service for TuShare Hong Kong Stock basic info."""
    
    def __init__(self):
        super().__init__("tushare_hk_basic")
    
    @query_method(
        description="Get HK stock basic info by ts_code",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="TS code (e.g., 00001.HK)",
                required=True,
            ),
        ]
    )
    def get_by_ts_code(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """
        Get HK stock basic info by ts_code.
        
        Args:
            ts_code: TS code (e.g., '00001.HK')
        
        Returns:
            Stock basic info or None
        """
        query = """
        SELECT *
        FROM ods_hk_basic
        WHERE ts_code = %(ts_code)s
        ORDER BY version DESC
        LIMIT 1
        """
        
        df = self.db.execute_query(query, {'ts_code': ts_code})
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    
    @query_method(
        description="Get all listed HK stocks",
        params=[
            QueryParam(
                name="list_status",
                type="str",
                description="Listing status: L=Listed, D=Delisted, P=Paused (default: L)",
                required=False,
            ),
        ]
    )
    def get_stock_list(
        self,
        list_status: str = 'L',
    ) -> List[Dict[str, Any]]:
        """
        Get HK stock list by listing status.
        
        Args:
            list_status: Listing status (L/D/P), default 'L'
        
        Returns:
            List of stock basic info
        """
        query = """
        SELECT *
        FROM ods_hk_basic
        WHERE list_status = %(list_status)s
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query, {'list_status': list_status})
        return df.to_dict('records')
    
    @query_method(
        description="Search HK stocks by name or code",
        params=[
            QueryParam(
                name="keyword",
                type="str",
                description="Search keyword (stock name, code, or pinyin)",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum results (default: 20)",
                required=False,
            ),
        ]
    )
    def search(
        self,
        keyword: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search HK stocks by name, code, or pinyin.
        
        Args:
            keyword: Search keyword
            limit: Maximum results
        
        Returns:
            List of matching stocks
        """
        query = """
        SELECT *
        FROM ods_hk_basic
        WHERE ts_code LIKE %(pattern)s
           OR name LIKE %(pattern)s
           OR cn_spell LIKE %(pattern)s
           OR fullname LIKE %(pattern)s
        ORDER BY ts_code ASC
        LIMIT %(limit)s
        """
        
        pattern = f"%{keyword}%"
        df = self.db.execute_query(query, {'pattern': pattern, 'limit': limit})
        return df.to_dict('records')
    
    @query_method(
        description="Get HK stocks by market",
        params=[
            QueryParam(
                name="market",
                type="str",
                description="Market category",
                required=True,
            ),
        ]
    )
    def get_by_market(self, market: str) -> List[Dict[str, Any]]:
        """
        Get HK stocks by market category.
        
        Args:
            market: Market category
        
        Returns:
            List of stocks in the market
        """
        query = """
        SELECT *
        FROM ods_hk_basic
        WHERE market = %(market)s
        AND list_status = 'L'
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query, {'market': market})
        return df.to_dict('records')
    
    @query_method(
        description="Get stock count by listing status",
        params=[]
    )
    def get_statistics(self) -> Dict[str, int]:
        """
        Get HK stock count statistics.
        
        Returns:
            Statistics by listing status
        """
        query = """
        SELECT 
            list_status,
            count() as count
        FROM ods_hk_basic
        GROUP BY list_status
        """
        
        df = self.db.execute_query(query)
        result = {}
        for _, row in df.iterrows():
            status = row['list_status']
            status_name = {'L': 'listed', 'D': 'delisted', 'P': 'paused'}.get(status, status)
            result[status_name] = int(row['count'])
        return result
    
    @query_method(
        description="Get recently listed HK stocks",
        params=[
            QueryParam(
                name="days",
                type="int",
                description="Days to look back (default: 30)",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum results (default: 50)",
                required=False,
            ),
        ]
    )
    def get_recent_ipo(
        self,
        days: int = 30,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get recently listed HK stocks.
        
        Args:
            days: Number of days to look back
            limit: Maximum results
        
        Returns:
            List of recently listed stocks
        """
        query = """
        SELECT *
        FROM ods_hk_basic
        WHERE list_status = 'L'
        AND list_date >= today() - %(days)s
        ORDER BY list_date DESC
        LIMIT %(limit)s
        """
        
        df = self.db.execute_query(query, {'days': days, 'limit': limit})
        return df.to_dict('records')
    
    @query_method(
        description="Get all ts_codes for listed stocks",
        params=[]
    )
    def get_all_ts_codes(self) -> List[str]:
        """
        Get all ts_codes for listed HK stocks.
        
        Returns:
            List of ts_codes
        """
        query = """
        SELECT ts_code
        FROM ods_hk_basic
        WHERE list_status = 'L'
        ORDER BY ts_code ASC
        """
        
        df = self.db.execute_query(query)
        return df['ts_code'].tolist()
