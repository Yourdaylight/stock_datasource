"""Query service for TuShare financial indicators data."""

import re
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareFinaceIndicatorService(BaseService):
    """Query service for TuShare financial indicators data."""
    
    def __init__(self):
        super().__init__("tushare_finace_indicator")
    
    def _validate_stock_code(self, code: str) -> bool:
        """Validate stock code format to prevent SQL injection."""
        if not isinstance(code, str):
            return False
        # Allow only alphanumeric characters and dots (e.g., 000001.SZ, 600000.SH, 00700.HK)
        pattern = r'^[A-Za-z0-9]{4,6}\.[A-Za-z]{2,3}$'
        return bool(re.match(pattern, code))
    
    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format (YYYYMMDD)."""
        if not isinstance(date_str, str):
            return False
        return date_str.isdigit() and len(date_str) == 8
    
    def _sanitize_limit(self, limit: Optional[int], default: int = 1000, max_limit: int = 10000) -> int:
        """Sanitize and validate limit parameter."""
        try:
            limit_value = int(limit) if limit is not None else default
        except (TypeError, ValueError):
            limit_value = default
        
        if limit_value <= 0:
            limit_value = default
        elif limit_value > max_limit:
            limit_value = max_limit
            
        return limit_value
    
    @query_method(
        description="Query financial indicators by stock code and date range",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=False),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
            QueryParam(name="limit", type="int", description="Maximum number of records to return", required=False)
        ]
    )
    def get_financial_indicators(self, code: Optional[str] = None, start_date: Optional[str] = None, 
                                end_date: Optional[str] = None, limit: Optional[int] = 1000) -> List[Dict[str, Any]]:
        """Query financial indicators from database using parameterized queries."""
        
        # Input validation
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        if not self._validate_date_format(start_date):
            raise ValueError("start_date must be in YYYYMMDD format")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        if code and not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(limit)
        
        # Build parameterized query
        query = "SELECT * FROM ods_fina_indicator WHERE 1=1"
        params = {}
        
        if code:
            query += " AND ts_code = %(code)s"
            params['code'] = code
        
        if start_date:
            query += " AND end_date >= %(start_date)s"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND end_date <= %(end_date)s"
            params['end_date'] = end_date
        
        query += " ORDER BY ts_code, end_date DESC LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get latest financial indicators for a stock",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_latest_indicators(self, code: str, periods: Optional[int] = 4) -> List[Dict[str, Any]]:
        """Get latest financial indicators for a specific stock using parameterized queries."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=4, max_limit=100)
        
        # Parameterized query
        query = """
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC
        LIMIT %(periods)s
        """
        params = {
            'code': code,
            'periods': str(periods_value)
        }
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get financial indicators summary by date",
        params=[
            QueryParam(name="end_date", type="str", description="Report date YYYYMMDD", required=True),
            QueryParam(name="min_roe", type="float", description="Minimum ROE filter", required=False),
            QueryParam(name="max_roe", type="float", description="Maximum ROE filter", required=False),
            QueryParam(name="limit", type="int", description="Maximum number of records", required=False)
        ]
    )
    def get_indicators_by_date(self, end_date: str, min_roe: Optional[float] = None, 
                             max_roe: Optional[float] = None, limit: Optional[int] = 1000) -> List[Dict[str, Any]]:
        """Get financial indicators for all stocks on a specific report date using parameterized queries."""
        
        # Input validation
        if not end_date:
            raise ValueError("end_date is required")
        
        if not self._validate_date_format(end_date):
            raise ValueError("end_date must be in YYYYMMDD format")
        
        # Validate ROE values
        if min_roe is not None and (not isinstance(min_roe, (int, float)) or min_roe < -100 or min_roe > 1000):
            raise ValueError("min_roe must be a number between -100 and 1000")
        
        if max_roe is not None and (not isinstance(max_roe, (int, float)) or max_roe < -100 or max_roe > 1000):
            raise ValueError("max_roe must be a number between -100 and 1000")
        
        if min_roe is not None and max_roe is not None and min_roe > max_roe:
            raise ValueError("min_roe cannot be greater than max_roe")
        
        # Sanitize limit
        limit_value = self._sanitize_limit(limit)
        
        # Build parameterized query
        query = "SELECT * FROM ods_fina_indicator WHERE end_date = %(end_date)s"
        params = {'end_date': end_date}
        
        if min_roe is not None:
            query += " AND roe >= %(min_roe)s"
            params['min_roe'] = str(min_roe)
        
        if max_roe is not None:
            query += " AND roe <= %(max_roe)s"
            params['max_roe'] = str(max_roe)
        
        query += " ORDER BY roe DESC NULLS LAST LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get ROE trend for a stock",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_roe_trend(self, code: str, periods: Optional[int] = 8) -> List[Dict[str, Any]]:
        """Get ROE trend for a specific stock using parameterized queries."""
        
        # Input validation
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        # Sanitize periods
        periods_value = self._sanitize_limit(periods, default=8, max_limit=100)
        
        # Parameterized query
        query = """
        SELECT 
            end_date,
            roe,
            net_profit_margin,
            asset_turnover
        FROM ods_fina_indicator
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC
        LIMIT %(periods)s
        """
        params = {
            'code': code,
            'periods': str(periods_value)
        }
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')