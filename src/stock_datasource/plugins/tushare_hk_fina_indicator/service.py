"""Query service for TuShare HK financial indicators data."""

import re
import math
import numpy as np
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _sanitize_for_json(val):
    """Replace NaN/inf float values with None for JSON compatibility."""
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


class TuShareHKFinaIndicatorService(BaseService):
    """Query service for TuShare HK financial indicators data."""
    
    def __init__(self):
        super().__init__("tushare_hk_fina_indicator")
    
    def _validate_hk_stock_code(self, code: str) -> bool:
        """Validate HK stock code format."""
        if not isinstance(code, str):
            return False
        pattern = r'^\d{5}\.(HK|hk)$'
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
        description="Query HK financial indicators by stock code",
        params=[
            QueryParam(name="code", type="str", description="HK stock code (e.g., 00700.HK)", required=True),
            QueryParam(name="periods", type="int", description="Number of latest periods to return", required=False),
            QueryParam(name="report_type", type="str", description="Report type: Q1/Q2/Q3/Q4", required=False)
        ]
    )
    def get_financial_indicators(self, code: str, periods: Optional[int] = 8,
                                  report_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Query HK financial indicators data for a stock."""
        if not code:
            raise ValueError("code is required")
        if not self._validate_hk_stock_code(code):
            raise ValueError(f"Invalid HK stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=8, max_limit=40)
        
        query = """
        SELECT * FROM ods_hk_fina_indicator FINAL
        WHERE ts_code = %(code)s
        """
        params = {'code': code}
        
        if report_type:
            query += " AND report_type = %(report_type)s"
            params['report_type'] = report_type
        
        query += " ORDER BY end_date DESC LIMIT %(limit)s"
        params['limit'] = int(periods_value)
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict('records')
    
    @query_method(
        description="Get key profitability metrics for HK stock",
        params=[
            QueryParam(name="code", type="str", description="HK stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_profitability_metrics(self, code: str, periods: Optional[int] = 8) -> Dict[str, Any]:
        """Get key profitability metrics for an HK stock."""
        if not code:
            raise ValueError("code is required")
        if not self._validate_hk_stock_code(code):
            raise ValueError(f"Invalid HK stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=8, max_limit=40)
        
        query = """
        SELECT 
            ts_code, name, end_date, report_type,
            operate_income, gross_profit, gross_profit_ratio,
            holder_profit, holder_profit_yoy, net_profit_ratio,
            roe_avg, roe_yearly, roa, roic_yearly,
            basic_eps, diluted_eps, eps_ttm, bps,
            pe_ttm, pb_ttm, total_market_cap
        FROM ods_hk_fina_indicator FINAL
        WHERE ts_code = %(code)s
        ORDER BY end_date DESC
        LIMIT %(limit)s
        """
        params = {'code': code, 'limit': int(periods_value)}
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return {"code": code, "periods": 0, "metrics": []}
        
        metrics = []
        for _, row in df.iterrows():
            metric = {
                "end_date": str(row['end_date']) if row['end_date'] else None,
                "report_type": row.get('report_type'),
                "name": row.get('name'),
                "operate_income": row.get('operate_income'),
                "gross_profit": row.get('gross_profit'),
                "gross_profit_ratio": row.get('gross_profit_ratio'),
                "holder_profit": row.get('holder_profit'),
                "holder_profit_yoy": row.get('holder_profit_yoy'),
                "net_profit_ratio": row.get('net_profit_ratio'),
                "roe_avg": row.get('roe_avg'),
                "roa": row.get('roa'),
                "basic_eps": row.get('basic_eps'),
                "pe_ttm": row.get('pe_ttm'),
                "pb_ttm": row.get('pb_ttm'),
                "total_market_cap": row.get('total_market_cap'),
            }
            metric = {k: _sanitize_for_json(v) for k, v in metric.items()}
            metrics.append(metric)
        
        return {
            "code": code,
            "periods": len(metrics),
            "metrics": metrics
        }
