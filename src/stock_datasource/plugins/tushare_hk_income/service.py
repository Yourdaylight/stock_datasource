"""Query service for TuShare HK income statement data (EAV model)."""

import re
import numpy as np
from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareHKIncomeService(BaseService):
    """Query service for TuShare HK income statement data."""
    
    def __init__(self):
        super().__init__("tushare_hk_income")
    
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
        description="Query HK income statement data by stock code (raw EAV format)",
        params=[
            QueryParam(name="code", type="str", description="HK stock code (e.g., 00700.HK)", required=True),
            QueryParam(name="period", type="str", description="Report period YYYYMMDD", required=False),
            QueryParam(name="indicators", type="str", description="Comma-separated indicator names to filter", required=False),
            QueryParam(name="limit", type="int", description="Max records to return", required=False)
        ]
    )
    def get_income(self, code: str, period: Optional[str] = None,
                   indicators: Optional[str] = None,
                   limit: Optional[int] = 500) -> List[Dict[str, Any]]:
        """Query HK income statement data in raw EAV format."""
        if not code:
            raise ValueError("code is required")
        if not self._validate_hk_stock_code(code):
            raise ValueError(f"Invalid HK stock code format: {code}")
        
        limit_value = self._sanitize_limit(limit, default=500, max_limit=5000)
        
        query = """
        SELECT ts_code, name, end_date, ind_name, ind_value
        FROM ods_hk_income FINAL
        WHERE ts_code = %(code)s
        """
        params: Dict[str, Any] = {'code': code}
        
        if period:
            query += " AND end_date = %(period)s"
            params['period'] = period
        
        if indicators:
            ind_list = [ind.strip() for ind in indicators.split(',') if ind.strip()]
            if ind_list:
                placeholders = ', '.join([f'%(ind_{i})s' for i in range(len(ind_list))])
                query += f" AND ind_name IN ({placeholders})"
                for i, ind in enumerate(ind_list):
                    params[f'ind_{i}'] = ind
        
        query += " ORDER BY end_date DESC, ind_name LIMIT %(limit)s"
        params['limit'] = int(limit_value)
        
        df = self.db.execute_query(query, params)
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return df.to_dict('records')
    
    @query_method(
        description="Query HK income statement data pivoted into wide format",
        params=[
            QueryParam(name="code", type="str", description="HK stock code (e.g., 00700.HK)", required=True),
            QueryParam(name="period", type="str", description="Report period YYYYMMDD", required=False),
            QueryParam(name="indicators", type="str", description="Comma-separated indicator names to pivot", required=False),
            QueryParam(name="periods_count", type="int", description="Number of latest periods to return", required=False)
        ]
    )
    def get_income_pivot(self, code: str, period: Optional[str] = None,
                         indicators: Optional[str] = None,
                         periods_count: Optional[int] = 8) -> Dict[str, Any]:
        """Query HK income statement data pivoted into wide format using conditional aggregation."""
        if not code:
            raise ValueError("code is required")
        if not self._validate_hk_stock_code(code):
            raise ValueError(f"Invalid HK stock code format: {code}")
        
        periods_value = self._sanitize_limit(periods_count, default=8, max_limit=40)
        
        # Default key indicators for HK income statement (港股利润表指标)
        default_indicators = [
            '营业额', '营运收入', '其他收入', '其他收益',
            '毛利', '经营溢利', '除税前溢利', '除税后溢利',
            '股东应占溢利', '少数股东损益',
            '销售及分销费用', '行政开支', '融资成本',
            '每股基本盈利', '每股摊薄盈利', '每股股息',
            '全面收益总额'
        ]
        
        if indicators:
            ind_list = [ind.strip() for ind in indicators.split(',') if ind.strip()]
        else:
            ind_list = default_indicators
        
        # Build conditional aggregation columns
        select_parts = ["ts_code", "end_date"]
        for ind in ind_list:
            safe_alias = ind.replace(' ', '_').replace('/', '_')
            select_parts.append(
                f"maxIf(ind_value, ind_name = %(ind_{safe_alias})s) AS `{ind}`"
            )
        
        select_clause = ",\n            ".join(select_parts)
        
        query = f"""
        SELECT 
            {select_clause}
        FROM ods_hk_income FINAL
        WHERE ts_code = %(code)s
        """
        params: Dict[str, Any] = {'code': code}
        
        for ind in ind_list:
            safe_alias = ind.replace(' ', '_').replace('/', '_')
            params[f'ind_{safe_alias}'] = ind
        
        if period:
            query += " AND end_date = %(period)s"
            params['period'] = period
        
        query += f"""
        GROUP BY ts_code, end_date
        ORDER BY end_date DESC
        LIMIT %(limit)s
        """
        params['limit'] = int(periods_value)
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return {"code": code, "periods": 0, "data": []}
        
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
            elif hasattr(df[col].dtype, 'name') and 'date' in df[col].dtype.name.lower():
                df[col] = df[col].astype(str)
        
        df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
        return {
            "code": code,
            "periods": len(df),
            "indicators": ind_list,
            "data": df.to_dict('records')
        }
    
    @query_method(
        description="List all available indicator names for HK income statement",
        params=[
            QueryParam(name="code", type="str", description="HK stock code (e.g., 00700.HK)", required=False)
        ]
    )
    def list_indicators(self, code: Optional[str] = None) -> List[str]:
        """List all distinct indicator names in the income statement table."""
        query = "SELECT DISTINCT ind_name FROM ods_hk_income FINAL"
        params: Dict[str, Any] = {}
        
        if code:
            if not self._validate_hk_stock_code(code):
                raise ValueError(f"Invalid HK stock code format: {code}")
            query += " WHERE ts_code = %(code)s"
            params['code'] = code
        
        query += " ORDER BY ind_name"
        
        df = self.db.execute_query(query, params)
        
        if df.empty:
            return []
        
        return df['ind_name'].tolist()
