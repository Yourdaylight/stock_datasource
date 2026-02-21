"""Query service for TuShare income statement data."""

import re
import numpy as np
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareIncomeService(BaseService):
    """Query service for TuShare income statement data."""
    
    def __init__(self):
        super().__init__("tushare_income")
    
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
        description="Query income statement by stock code",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 600000.SH)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False),
            QueryParam(name="report_type", type="str", description="Report type: 1=合并报表, 2=单季合并", required=False)
        ]
    )
    def get_income_statement(self, code: str, periods: Optional[int] = 8, 
                             report_type: Optional[str] = "1") -> List[Dict[str, Any]]:
        """Query income statement data for a stock."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=8, max_limit=40)
        
        # Build parameterized query
        query = """
        SELECT * FROM ods_income_statement
        WHERE ts_code = %(code)s
        """
        params = {'code': code}
        
        if report_type:
            query += " AND report_type = %(report_type)s"
            params['report_type'] = report_type
        
        query += " ORDER BY end_date DESC LIMIT %(limit)s"
        params['limit'] = int(periods_value)
        
        df = self.db.execute_query(query, params)
        
        # Convert datetime columns to string
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict('records')
    
    @query_method(
        description="Get key profitability metrics from income statement",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_profitability_metrics(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get key profitability metrics from income statement."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=4, max_limit=20)
        
        query = """
        SELECT 
            ts_code,
            end_date,
            report_type,
            total_revenue,
            revenue,
            operate_profit,
            total_profit,
            n_income,
            n_income_attr_p,
            basic_eps,
            diluted_eps,
            ebit,
            ebitda,
            total_cogs,
            oper_cost,
            sell_exp,
            admin_exp,
            fin_exp,
            rd_exp,
            income_tax,
            biz_tax_surchg,
            minority_gain,
            invest_income,
            non_oper_income,
            non_oper_exp,
            t_compr_income,
            fin_exp_int_exp,
            fin_exp_int_inc
        FROM ods_income_statement
        WHERE ts_code = %(code)s AND report_type = '1'
        ORDER BY end_date DESC
        LIMIT %(limit)s
        """
        params = {'code': code, 'limit': int(periods_value)}
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return {"code": code, "periods": 0, "metrics": []}
        
        def _safe_float(val):
            """Safely convert to float, returning None for invalid values."""
            if val is None or val == '\\N' or val == 'None' or val == '':
                return None
            try:
                f = float(val)
                return f if f == f else None  # NaN check
            except (ValueError, TypeError):
                return None
        
        # Calculate derived metrics
        metrics = []
        for _, row in df.iterrows():
            metric = {
                "end_date": str(row['end_date']) if row['end_date'] else None,
                "total_revenue": _safe_float(row['total_revenue']),
                "revenue": _safe_float(row['revenue']),
                "operate_profit": _safe_float(row['operate_profit']),
                "total_profit": _safe_float(row['total_profit']),
                "net_income": _safe_float(row['n_income']),
                "net_income_attr_parent": _safe_float(row['n_income_attr_p']),
                "basic_eps": _safe_float(row['basic_eps']),
                "diluted_eps": _safe_float(row['diluted_eps']),
                "ebit": _safe_float(row['ebit']),
                "ebitda": _safe_float(row['ebitda']),
                # Cost & expense fields
                "oper_cost": _safe_float(row['oper_cost']),
                "sell_exp": _safe_float(row['sell_exp']),
                "admin_exp": _safe_float(row['admin_exp']),
                "fin_exp": _safe_float(row['fin_exp']),
                "rd_exp": _safe_float(row['rd_exp']),
                "total_cogs": _safe_float(row['total_cogs']),
                # Tax & other
                "income_tax": _safe_float(row['income_tax']),
                "biz_tax_surchg": _safe_float(row['biz_tax_surchg']),
                "minority_gain": _safe_float(row['minority_gain']),
                "invest_income": _safe_float(row['invest_income']),
                "non_oper_income": _safe_float(row['non_oper_income']),
                "non_oper_exp": _safe_float(row['non_oper_exp']),
                "t_compr_income": _safe_float(row['t_compr_income']),
                "fin_exp_int_exp": _safe_float(row['fin_exp_int_exp']),
                "fin_exp_int_inc": _safe_float(row['fin_exp_int_inc']),
            }
            
            # Calculate margins and ratios
            rev = metric['revenue']
            if rev and rev != 0:
                metric['gross_margin'] = ((rev - (metric['oper_cost'] or metric['total_cogs'] or 0)) / rev * 100) if (metric['oper_cost'] or metric['total_cogs']) else None
                metric['operating_margin'] = (metric['operate_profit'] / rev * 100) if metric['operate_profit'] else None
                metric['net_margin'] = (metric['net_income'] / rev * 100) if metric['net_income'] else None
                # Expense ratios (as % of revenue)
                metric['sell_exp_ratio'] = (metric['sell_exp'] / rev * 100) if metric['sell_exp'] else None
                metric['admin_exp_ratio'] = (metric['admin_exp'] / rev * 100) if metric['admin_exp'] else None
                metric['fin_exp_ratio'] = (metric['fin_exp'] / rev * 100) if metric['fin_exp'] else None
                metric['rd_exp_ratio'] = (metric['rd_exp'] / rev * 100) if metric['rd_exp'] else None
            
            metrics.append(metric)
        
        return {
            "code": code,
            "periods": len(metrics),
            "metrics": metrics
        }
    
    @query_method(
        description="Get quarterly income comparison",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="quarters", type="int", description="Number of quarters", required=False)
        ]
    )
    def get_quarterly_income(self, code: str, quarters: Optional[int] = 8) -> List[Dict[str, Any]]:
        """Get quarterly income statement data (单季合并报表)."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        quarters_value = self._sanitize_limit(quarters, default=8, max_limit=40)
        
        query = """
        SELECT * FROM ods_income_statement
        WHERE ts_code = %(code)s AND report_type = '2'
        ORDER BY end_date DESC
        LIMIT %(limit)s
        """
        params = {'code': code, 'limit': int(quarters_value)}
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')
