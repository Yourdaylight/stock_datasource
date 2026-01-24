"""Query service for TuShare financial audit opinion data."""

import re
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareFinaAuditService(BaseService):
    """Query service for TuShare financial audit opinion data."""
    
    def __init__(self):
        super().__init__("tushare_fina_audit")
    
    def _validate_stock_code(self, code: str) -> bool:
        """Validate stock code format to prevent SQL injection."""
        if not isinstance(code, str):
            return False
        pattern = r'^[A-Za-z0-9]{4,6}\.[A-Za-z]{2,3}$'
        return bool(re.match(pattern, code))
    
    def _validate_date_format(self, date_str: str) -> bool:
        """Validate date format (YYYYMMDD)."""
        if not isinstance(date_str, str):
            return False
        return date_str.isdigit() and len(date_str) == 8
    
    def _sanitize_limit(self, limit: Optional[int], default: int = 100, max_limit: int = 1000) -> int:
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
        description="Query financial audit opinion by stock code",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 600000.SH)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_audit_opinion(self, code: str, periods: Optional[int] = 5) -> List[Dict[str, Any]]:
        """Query financial audit opinion data for a stock."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=5, max_limit=20)
        
        # Build parameterized query
        query = """
        SELECT * FROM ods_fina_audit
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC LIMIT %(limit)s
        """
        params = {'code': code, 'limit': str(periods_value)}
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get non-standard audit opinions in a date range",
        params=[
            QueryParam(name="start_date", type="str", description="Start date (YYYY-MM-DD)", required=True),
            QueryParam(name="end_date", type="str", description="End date (YYYY-MM-DD)", required=True),
            QueryParam(name="limit", type="int", description="Maximum records to return", required=False)
        ]
    )
    def get_non_standard_opinions(self, start_date: str, end_date: str, 
                                   limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Get non-standard audit opinions in a date range."""
        
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        limit_value = self._sanitize_limit(limit, default=100, max_limit=500)
        
        query = """
        SELECT * FROM ods_fina_audit
        WHERE ann_date >= %(start_date)s 
          AND ann_date <= %(end_date)s
          AND audit_result != '标准无保留意见'
          AND audit_result IS NOT NULL
        ORDER BY ann_date DESC
        LIMIT %(limit)s
        """
        params = {
            'start_date': start_date,
            'end_date': end_date,
            'limit': str(limit_value)
        }
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get audit statistics by accounting firm",
        params=[
            QueryParam(name="agency", type="str", description="Accounting firm name (partial match)", required=True),
            QueryParam(name="year", type="str", description="Year (YYYY format)", required=False),
            QueryParam(name="limit", type="int", description="Maximum records to return", required=False)
        ]
    )
    def get_audit_by_agency(self, agency: str, year: Optional[str] = None,
                            limit: Optional[int] = 100) -> List[Dict[str, Any]]:
        """Get audit data by accounting firm."""
        
        if not agency:
            raise ValueError("agency is required")
        
        limit_value = self._sanitize_limit(limit, default=100, max_limit=500)
        
        query = """
        SELECT * FROM ods_fina_audit
        WHERE audit_agency LIKE %(agency)s
        """
        params = {'agency': f'%{agency}%'}
        
        if year:
            query += " AND toYear(end_date) = %(year)s"
            params['year'] = year
        
        query += " ORDER BY end_date DESC LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get audit opinion summary statistics",
        params=[
            QueryParam(name="year", type="str", description="Year (YYYY format)", required=True)
        ]
    )
    def get_audit_summary(self, year: str) -> Dict[str, Any]:
        """Get audit opinion summary statistics for a year."""
        
        if not year or not year.isdigit() or len(year) != 4:
            raise ValueError("Valid year (YYYY) is required")
        
        query = """
        SELECT 
            audit_result,
            COUNT(*) as count,
            AVG(audit_fees) as avg_fees
        FROM ods_fina_audit
        WHERE toYear(end_date) = %(year)s
          AND audit_result IS NOT NULL
        GROUP BY audit_result
        ORDER BY count DESC
        """
        params = {'year': year}
        
        df = self.db.execute_query(query, params)
        
        return {
            "year": year,
            "total_audits": int(df['count'].sum()) if not df.empty else 0,
            "by_result": df.to_dict('records') if not df.empty else []
        }
