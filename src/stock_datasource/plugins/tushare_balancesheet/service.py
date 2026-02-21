"""Query service for TuShare balance sheet data."""

import re
import numpy as np
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareBalancesheetService(BaseService):
    """Query service for TuShare balance sheet data."""
    
    def __init__(self):
        super().__init__("tushare_balancesheet")
    
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
        description="Query balance sheet by stock code",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False),
            QueryParam(name="report_type", type="str", description="Report type", required=False)
        ]
    )
    def get_balance_sheet(self, code: str, periods: Optional[int] = 8,
                          report_type: Optional[str] = "1") -> List[Dict[str, Any]]:
        """Query balance sheet data for a stock."""
        
        if not code:
            raise ValueError("code is required")
        
        if not self._validate_stock_code(code):
            raise ValueError(f"Invalid stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods, default=8, max_limit=40)
        
        query = """
        SELECT * FROM ods_balance_sheet
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
        description="Get key balance sheet metrics",
        params=[
            QueryParam(name="code", type="str", description="Stock code", required=True),
            QueryParam(name="periods", type="int", description="Number of periods", required=False)
        ]
    )
    def get_balance_sheet_metrics(self, code: str, periods: Optional[int] = 4) -> Dict[str, Any]:
        """Get key balance sheet metrics."""
        
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
            total_assets,
            total_liab,
            total_hldr_eqy_exc_min_int,
            total_cur_assets,
            total_cur_liab,
            total_nca,
            total_ncl,
            money_cap,
            accounts_receiv,
            inventories,
            fix_assets,
            st_borr,
            lt_borr
        FROM ods_balance_sheet
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
                "total_assets": row['total_assets'],
                "total_liab": row['total_liab'],
                "total_equity": row['total_hldr_eqy_exc_min_int'],
                "total_cur_assets": row['total_cur_assets'],
                "total_cur_liab": row['total_cur_liab'],
                "money_cap": row['money_cap'],
                "accounts_receiv": row['accounts_receiv'],
                "inventories": row['inventories'],
                "fix_assets": row['fix_assets']
            }
            
            # Calculate ratios
            if row['total_cur_liab'] and row['total_cur_liab'] != 0:
                metric['current_ratio'] = row['total_cur_assets'] / row['total_cur_liab'] if row['total_cur_assets'] else None
                quick_assets = (row['total_cur_assets'] or 0) - (row['inventories'] or 0)
                metric['quick_ratio'] = quick_assets / row['total_cur_liab']
            
            if row['total_assets'] and row['total_assets'] != 0:
                metric['debt_to_assets'] = (row['total_liab'] / row['total_assets'] * 100) if row['total_liab'] else None
            
            # Working capital
            metric['working_capital'] = (row['total_cur_assets'] or 0) - (row['total_cur_liab'] or 0)
            
            metrics.append(metric)
        
        return {
            "code": code,
            "periods": len(metrics),
            "metrics": metrics
        }
