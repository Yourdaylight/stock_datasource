"""THS Index module service layer.

Provides THS sector index data services including listing, daily data, and ranking.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _get_db():
    """Get database connection."""
    from stock_datasource.models.database import db_client
    return db_client


def _execute_query(query: str, params: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Execute query and return results as list of dicts."""
    db = _get_db()
    df = db.execute_query(query, params or {})
    if df is None or df.empty:
        return []
    return df.to_dict('records')


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime("%Y%m%d")
    if hasattr(obj, "isoformat"):  # date/datetime
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    if pd.isna(obj):
        return None
    return obj


# Valid sort fields for ranking - whitelist to prevent SQL injection
VALID_SORT_FIELDS = {"pct_change", "vol", "turnover_rate", "close"}
VALID_ORDER_VALUES = {"desc", "asc"}


class THSIndexService:
    """Service for THS sector index operations."""
    
    def __init__(self):
        self.db = _get_db()
    
    def _get_latest_trade_date(self) -> Optional[str]:
        """Get latest trade date from ods_ths_daily."""
        query = """
        SELECT max(trade_date) as latest_date
        FROM ods_ths_daily
        """
        result = _execute_query(query)
        if result and result[0].get('latest_date'):
            latest = result[0]['latest_date']
            if hasattr(latest, 'strftime'):
                return latest.strftime('%Y%m%d')
            return str(latest).replace('-', '')
        return None
    
    def get_index_list(
        self,
        exchange: Optional[str] = None,
        index_type: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get THS index list with filters.
        
        Args:
            exchange: Market filter (A/HK/US)
            index_type: Type filter (N-概念/I-行业/R-地域/S-特色/ST-风格/TH-主题/BB-宽基)
            limit: Max records to return
            offset: Pagination offset
            
        Returns:
            Dict with data, total, and filter info
        """
        conditions = ["1=1"]
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        
        if exchange:
            conditions.append("exchange = %(exchange)s")
            params["exchange"] = exchange
        
        if index_type:
            conditions.append("type = %(index_type)s")
            params["index_type"] = index_type
        
        where_clause = " AND ".join(conditions)
        
        # Get total count
        count_query = f"""
        SELECT COUNT(*) as total
        FROM ods_ths_index
        WHERE {where_clause}
        """
        count_result = _execute_query(count_query, params)
        total = count_result[0].get('total', 0) if count_result else 0
        
        # Get data
        data_query = f"""
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE {where_clause}
        ORDER BY ts_code ASC
        LIMIT %(limit)s
        OFFSET %(offset)s
        """
        
        data = _execute_query(data_query, params)
        data = [_convert_to_json_serializable(item) for item in data]
        
        return {
            "data": data,
            "total": total,
            "exchange": exchange,
            "index_type": index_type,
        }
    
    def get_index_by_code(self, ts_code: str) -> Optional[Dict[str, Any]]:
        """Get THS index details by code.
        
        Args:
            ts_code: Index code (e.g., 885001.TI)
            
        Returns:
            Index details or None if not found
        """
        query = """
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE ts_code = %(ts_code)s
        LIMIT 1
        """
        
        result = _execute_query(query, {"ts_code": ts_code})
        if not result:
            return None
        return _convert_to_json_serializable(result[0])
    
    def get_daily_data(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """Get THS index daily data.
        
        Args:
            ts_code: Index code
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            limit: Max records if no date range specified
            
        Returns:
            Dict with ts_code, name, and data
        """
        # Get index info
        index_info = self.get_index_by_code(ts_code)
        name = index_info.get("name") if index_info else None
        
        params: Dict[str, Any] = {"ts_code": ts_code}
        conditions = ["ts_code = %(ts_code)s"]
        
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y%m%d").date()
            conditions.append("trade_date >= %(start_date)s")
            params["start_date"] = start_dt
        
        if end_date:
            end_dt = datetime.strptime(end_date, "%Y%m%d").date()
            conditions.append("trade_date <= %(end_date)s")
            params["end_date"] = end_dt
        
        where_clause = " AND ".join(conditions)
        
        # If no date range, use limit
        limit_clause = "" if (start_date and end_date) else f"LIMIT {limit}"
        
        query = f"""
        SELECT
            ts_code,
            trade_date,
            open,
            high,
            low,
            close,
            pre_close,
            pct_change,
            vol,
            turnover_rate,
            total_mv,
            float_mv
        FROM ods_ths_daily
        WHERE {where_clause}
        ORDER BY trade_date DESC
        {limit_clause}
        """
        
        data = _execute_query(query, params)
        data = [_convert_to_json_serializable(item) for item in data]
        
        # Sort by date ascending for charts
        data.sort(key=lambda x: x.get('trade_date', ''))
        
        return {
            "ts_code": ts_code,
            "name": name,
            "data": data,
        }
    
    def get_ranking(
        self,
        date: Optional[str] = None,
        index_type: Optional[str] = None,
        sort_by: str = "pct_change",
        order: str = "desc",
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get THS index ranking by various metrics.
        
        Args:
            date: Trade date (YYYYMMDD), defaults to latest
            index_type: Filter by type (N/I/R/S/ST/TH/BB)
            sort_by: Sort field (pct_change/vol/turnover_rate)
            order: Sort order (desc/asc)
            limit: Max records to return
            
        Returns:
            Dict with trade_date, sort_by, order, and data
        """
        # Validate sort_by to prevent SQL injection
        if sort_by not in VALID_SORT_FIELDS:
            sort_by = "pct_change"
        if order.lower() not in VALID_ORDER_VALUES:
            order = "desc"
        
        if not date:
            date = self._get_latest_trade_date()
        
        if not date:
            return {"error": "No data available"}
        
        # Convert date
        trade_date = datetime.strptime(date, "%Y%m%d").date()
        
        conditions = ["d.trade_date = %(trade_date)s"]
        params: Dict[str, Any] = {"trade_date": trade_date, "limit": limit}
        
        if index_type:
            conditions.append("i.type = %(index_type)s")
            params["index_type"] = index_type
        
        # Default to A-share market
        conditions.append("i.exchange = 'A'")
        
        where_clause = " AND ".join(conditions)
        
        # Build order clause safely using validated values
        order_clause = f"d.{sort_by} {order.upper()} NULLS LAST"
        
        query = f"""
        SELECT
            d.ts_code,
            i.name,
            i.type,
            i.count,
            d.close,
            d.pct_change,
            d.vol,
            d.turnover_rate
        FROM ods_ths_daily d
        INNER JOIN ods_ths_index i ON d.ts_code = i.ts_code
        WHERE {where_clause}
        ORDER BY {order_clause}
        LIMIT %(limit)s
        """
        
        data = _execute_query(query, params)
        data = [_convert_to_json_serializable(item) for item in data]
        
        return {
            "trade_date": date,
            "sort_by": sort_by,
            "order": order,
            "index_type": index_type,
            "data": data,
        }
    
    def search_index(
        self,
        keyword: str,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search THS index by name keyword.
        
        Args:
            keyword: Search keyword
            limit: Max records to return
            
        Returns:
            Dict with keyword and data
        """
        query = """
        SELECT
            ts_code,
            name,
            count,
            exchange,
            list_date,
            type
        FROM ods_ths_index
        WHERE name LIKE %(pattern)s
        ORDER BY count DESC NULLS LAST
        LIMIT %(limit)s
        """
        
        data = _execute_query(query, {
            "pattern": f"%{keyword}%",
            "limit": limit,
        })
        data = [_convert_to_json_serializable(item) for item in data]
        
        return {
            "keyword": keyword,
            "data": data,
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get THS index statistics by type.
        
        Returns:
            Dict with statistics grouped by type and exchange
        """
        query = """
        SELECT
            type,
            exchange,
            COUNT(*) as index_count,
            SUM(count) as total_constituents,
            AVG(count) as avg_constituents
        FROM ods_ths_index
        GROUP BY type, exchange
        ORDER BY index_count DESC
        """
        
        data = _execute_query(query)
        data = [_convert_to_json_serializable(item) for item in data]
        
        return {"data": data}


# Singleton instance
_ths_index_service: Optional[THSIndexService] = None


def get_ths_index_service() -> THSIndexService:
    """Get THS Index service singleton."""
    global _ths_index_service
    if _ths_index_service is None:
        _ths_index_service = THSIndexService()
    return _ths_index_service
