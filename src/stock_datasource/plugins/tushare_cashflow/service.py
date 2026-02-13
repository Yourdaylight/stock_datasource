"""Query service for TuShare cash flow statement data."""

import re
import numpy as np
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareCashflowService(BaseService):
    """Query service for TuShare cash flow statement data."""
    
    def __init__(self):
        super().__init__("tushare_cashflow")
    
    def _validate_stock_code(self, code: str) -> bool:
        if not isinstance(code, str):
            return False
        pattern = r'^[A-Za-z0-9]{4,6}\.[A-Za-z]{2,3}$'
        return bool(re.match(pattern, code))
    
    def _sanitize_limit(self, limit: Optional[int], default: int = 100, max_limit: int = 1000) -> int:
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
        description="Query cash flow statement by stock code",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False),
            QueryParam(name="report_type", type="str", description="Report type", required=False)
        ]
    )
    def get_cashflow(self, code: str, periods: Optional[int] = 8,
                     report_type: Optional[str] = "1") -> List[Dict[str, Any]]:
        """Query cash flow statement data for a stock."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=8, max_limit=40)
        
        query = """
        SELECT * FROM ods_cash_flow
        WHERE ts_code = %(code)s
        """
        params = {'code': code}
        
        if report_type:
            query += " AND report_type = %(report_type)s"
            params['report_type'] = report_type
        
        query += " ORDER BY end_date DESC LIMIT %(limit)s"
        params['limit'] = str(periods_value)
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict('records')
    
    @query_method(
        description="Get key cash flow metrics",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_cashflow_metrics(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get key cash flow metrics."""
        
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
            n_cashflow_act,
            n_cashflow_inv_act,
            n_cash_flows_fnc_act,
            c_fr_sale_sg,
            c_paid_goods_s,
            c_pay_acq_const_fiolta,
            free_cashflow,
            n_incr_cash_cash_equ,
            c_cash_equ_end_period
        FROM ods_cash_flow
        WHERE ts_code = %(code)s AND report_type = '1'
        ORDER BY end_date DESC
        LIMIT %(limit)s
        """
        params = {'code': code, 'limit': str(periods_value)}
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return {"code": code, "periods": 0, "metrics": []}
        
        metrics = []
        for _, row in df.iterrows():
            metric = {
                "end_date": str(row['end_date']) if row['end_date'] else None,
                "operating_cashflow": row['n_cashflow_act'],
                "investing_cashflow": row['n_cashflow_inv_act'],
                "financing_cashflow": row['n_cash_flows_fnc_act'],
                "sales_receipts": row['c_fr_sale_sg'],
                "purchases_payments": row['c_paid_goods_s'],
                "capex": row['c_pay_acq_const_fiolta'],
                "free_cashflow": row['free_cashflow'],
                "net_cash_change": row['n_incr_cash_cash_equ'],
                "ending_cash": row['c_cash_equ_end_period']
            }
            
            # Calculate FCF if not available
            if metric['free_cashflow'] is None and metric['operating_cashflow'] and metric['capex']:
                metric['free_cashflow_calc'] = metric['operating_cashflow'] - abs(metric['capex'])
            
            metrics.append(metric)
        
        return {
            "code": code,
            "periods": len(metrics),
            "metrics": metrics
        }
