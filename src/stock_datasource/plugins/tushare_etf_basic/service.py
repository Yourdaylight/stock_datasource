"""TuShare ETF basic information query service."""

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


class TuShareETFBasicService(BaseService):
    """Query service for TuShare ETF basic information."""
    
    def __init__(self):
        super().__init__("tushare_etf_basic")
    
    @query_method(
        description="Query ETF basic information by code",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="ETF code, e.g., 510330.SH",
                required=True,
            ),
        ]
    )
    def get_etf_basic(self, ts_code: str) -> List[Dict[str, Any]]:
        """Query ETF basic information by code.
        
        Args:
            ts_code: ETF code (e.g., 510330.SH)
        
        Returns:
            List of ETF basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            csname,
            extname,
            cname,
            index_code,
            index_name,
            setup_date,
            list_date,
            list_status,
            exchange,
            mgr_name,
            custod_name,
            mgt_fee,
            etf_type
        FROM ods_etf_basic
        WHERE ts_code = '{ts_code}'
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query all listed ETFs",
        params=[
            QueryParam(
                name="list_status",
                type="str",
                description="List status: L(listed), D(delisted), P(pending)",
                required=False,
                default="L",
            ),
            QueryParam(
                name="exchange",
                type="str",
                description="Exchange: SH or SZ",
                required=False,
            ),
        ]
    )
    def get_all_etfs(
        self,
        list_status: str = "L",
        exchange: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query all ETFs by list status and exchange.
        
        Args:
            list_status: List status (L/D/P)
            exchange: Exchange (SH/SZ)
        
        Returns:
            List of ETF basic information records
        """
        where_clauses = [f"list_status = '{list_status}'"]
        if exchange:
            where_clauses.append(f"exchange = '{exchange}'")
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
        SELECT 
            ts_code,
            csname,
            extname,
            cname,
            index_code,
            index_name,
            setup_date,
            list_date,
            list_status,
            exchange,
            mgr_name,
            custod_name,
            mgt_fee,
            etf_type
        FROM ods_etf_basic
        WHERE {where_sql}
        ORDER BY list_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query ETFs by tracking index",
        params=[
            QueryParam(
                name="index_code",
                type="str",
                description="Index code, e.g., 000300.SH",
                required=True,
            ),
        ]
    )
    def get_etfs_by_index(self, index_code: str) -> List[Dict[str, Any]]:
        """Query ETFs by tracking index.
        
        Args:
            index_code: Index code (e.g., 000300.SH)
        
        Returns:
            List of ETF basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            csname,
            extname,
            cname,
            index_code,
            index_name,
            setup_date,
            list_date,
            list_status,
            exchange,
            mgr_name,
            custod_name,
            mgt_fee,
            etf_type
        FROM ods_etf_basic
        WHERE index_code = '{index_code}'
        AND list_status = 'L'
        ORDER BY list_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query ETFs by manager",
        params=[
            QueryParam(
                name="mgr_name",
                type="str",
                description="Manager name, e.g., 华夏基金",
                required=True,
            ),
        ]
    )
    def get_etfs_by_manager(self, mgr_name: str) -> List[Dict[str, Any]]:
        """Query ETFs by manager.
        
        Args:
            mgr_name: Manager name (e.g., 华夏基金)
        
        Returns:
            List of ETF basic information records
        """
        query = f"""
        SELECT 
            ts_code,
            csname,
            extname,
            cname,
            index_code,
            index_name,
            setup_date,
            list_date,
            list_status,
            exchange,
            mgr_name,
            custod_name,
            mgt_fee,
            etf_type
        FROM ods_etf_basic
        WHERE mgr_name LIKE '%{mgr_name}%'
        AND list_status = 'L'
        ORDER BY list_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get ETF code list",
        params=[
            QueryParam(
                name="list_status",
                type="str",
                description="List status: L(listed), D(delisted), P(pending)",
                required=False,
                default="L",
            ),
        ]
    )
    def get_etf_codes(self, list_status: str = "L") -> List[str]:
        """Get list of ETF codes.
        
        Args:
            list_status: List status (L/D/P)
        
        Returns:
            List of ETF codes
        """
        query = f"""
        SELECT ts_code
        FROM ods_etf_basic
        WHERE list_status = '{list_status}'
        ORDER BY ts_code
        """
        
        df = self.db.execute_query(query)
        return df['ts_code'].tolist() if not df.empty else []
