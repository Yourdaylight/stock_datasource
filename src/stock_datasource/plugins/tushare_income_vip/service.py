"""Query service for TuShare income statement VIP data."""

import re
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareIncomeVipService(BaseService):
    """Query service for TuShare income statement VIP data.
    
    Note: VIP data is stored in the same table as base income (ods_income_statement).
    This service provides the same query methods as the base income service.
    """
    
    def __init__(self):
        super().__init__("tushare_income_vip")
    
    def _validate_stock_code(self, code: str) -> bool:
        """Validate stock code format to prevent SQL injection."""
        if not isinstance(code, str):
            return False
        pattern = r'^[A-Za-z0-9]{4,6}\.[A-Za-z]{2,3}$'
        return bool(re.match(pattern, code))
    
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
        description="Query income statement by period (batch)",
        params=[
            QueryParam(name="period", type="str", description="Report period (e.g., 20231231)", required=True),
            QueryParam(name="report_type", type="str", description="Report type: 1=合并报表", required=False),
            QueryParam(name="limit", type="int", description="Maximum records to return", required=False)
        ]
    )
    def get_income_by_period(self, period: str, report_type: Optional[str] = "1",
                             limit: Optional[int] = 1000) -> List[Dict[str, Any]]:
        """Query income statement data for a period (all stocks)."""
        
        if not period:
            raise ValueError("period is required")
        
        limit_value = self._sanitize_limit(limit, default=1000, max_limit=5000)
        
        # Build parameterized query
        query = """
        SELECT * FROM ods_income_statement
        WHERE end_date = toDate(%(period)s)
        """
        # Format period from YYYYMMDD to YYYY-MM-DD
        period_formatted = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
        params = {'period': period_formatted}
        
        if report_type:
            query += " AND report_type = %(report_type)s"
            params['report_type'] = report_type
        
        query += " ORDER BY ts_code LIMIT %(limit)s"
        params['limit'] = str(limit_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
    
    @query_method(
        description="Get income statement summary by period",
        params=[
            QueryParam(name="period", type="str", description="Report period (e.g., 20231231)", required=True)
        ]
    )
    def get_income_summary(self, period: str) -> Dict[str, Any]:
        """Get income statement summary statistics for a period."""
        
        if not period:
            raise ValueError("period is required")
        
        # Format period from YYYYMMDD to YYYY-MM-DD
        period_formatted = f"{period[:4]}-{period[4:6]}-{period[6:8]}"
        
        query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT ts_code) as unique_stocks,
            AVG(total_revenue) as avg_revenue,
            AVG(n_income) as avg_net_income,
            AVG(basic_eps) as avg_eps
        FROM ods_income_statement
        WHERE end_date = toDate(%(period)s) AND report_type = '1'
        """
        params = {'period': period_formatted}
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return {"period": period, "total_records": 0}
        
        row = df.iloc[0]
        return {
            "period": period,
            "total_records": int(row['total_records']) if row['total_records'] else 0,
            "unique_stocks": int(row['unique_stocks']) if row['unique_stocks'] else 0,
            "avg_revenue": float(row['avg_revenue']) if row['avg_revenue'] else None,
            "avg_net_income": float(row['avg_net_income']) if row['avg_net_income'] else None,
            "avg_eps": float(row['avg_eps']) if row['avg_eps'] else None
        }
