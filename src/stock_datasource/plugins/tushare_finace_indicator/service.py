"""Query service for TuShare financial indicators data."""

from typing import List, Dict, Any, Optional
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


class TuShareFinaceIndicatorService(BaseService):
    """Query service for TuShare financial indicators data."""
    
    def __init__(self):
        super().__init__("tushare_finace_indicator")
    
    @query_method(
        description="Query financial indicators by stock code and date range",
        params=[
            QueryParam(name="code", type="str", description="Stock code (e.g., 002579.SZ)", required=False),
            QueryParam(name="start_date", type="str", description="Start date YYYYMMDD", required=True),
            QueryParam(name="end_date", type="str", description="End date YYYYMMDD", required=True),
            QueryParam(name="limit", type="int", description="Maximum number of records to return", required=False)
        ]
    )
    def get_financial_indicators(self, code: Optional[str] = None, start_date: str = None, 
                                end_date: str = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Query financial indicators from database."""
        query = f"""
        SELECT * FROM ods_fina_indicator
        WHERE 1=1
        """
        
        if code:
            query += f" AND ts_code = '{code}'"
        
        if start_date:
            query += f" AND end_date >= '{start_date}'"
        
        if end_date:
            query += f" AND end_date <= '{end_date}'"
        
        query += f" ORDER BY ts_code, end_date DESC"
        
        if limit:
            try:
                limit_value = int(limit)
            except (TypeError, ValueError):
                limit_value = 1000
        else:
            limit_value = 1000
        
        if limit_value <= 0:
            limit_value = 1000
        
        query += f" LIMIT {limit_value}"
        
        df = self.db.execute_query(query)
        
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
    def get_latest_indicators(self, code: str, periods: int = 4) -> List[Dict[str, Any]]:
        """Get latest financial indicators for a specific stock."""
        # Ensure periods has a sensible default if omitted or invalid
        try:
            periods_value = int(periods) if periods is not None else 4
        except (TypeError, ValueError):
            periods_value = 4
        
        if periods_value <= 0:
            periods_value = 4
        
        query = f"""
        SELECT * FROM ods_fina_indicator
        WHERE ts_code = '{code}'
        ORDER BY end_date DESC
        LIMIT {periods_value}
        """
        
        df = self.db.execute_query(query)
        
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
                             max_roe: Optional[float] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get financial indicators for all stocks on a specific report date."""
        query = f"""
        SELECT * FROM ods_fina_indicator
        WHERE end_date = '{end_date}'
        """
        
        if min_roe is not None:
            query += f" AND roe >= {min_roe}"
        
        if max_roe is not None:
            query += f" AND roe <= {max_roe}"
        
        query += f" ORDER BY roe DESC NULLS LAST"
        
        if limit:
            try:
                limit_value = int(limit)
            except (TypeError, ValueError):
                limit_value = 1000
        else:
            limit_value = 1000
        
        if limit_value <= 0:
            limit_value = 1000
        
        query += f" LIMIT {limit_value}"
        
        df = self.db.execute_query(query)
        
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
    def get_roe_trend(self, code: str, periods: int = 8) -> List[Dict[str, Any]]:
        """Get ROE trend for a specific stock."""
        try:
            periods_value = int(periods) if periods is not None else 8
        except (TypeError, ValueError):
            periods_value = 8
        
        if periods_value <= 0:
            periods_value = 8
        
        query = f"""
        SELECT 
            end_date,
            roe,
            net_profit_margin,
            asset_turnover
        FROM ods_fina_indicator
        WHERE ts_code = '{code}'
        ORDER BY end_date DESC
        LIMIT {periods_value}
        """
        
        df = self.db.execute_query(query)
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = df[col].astype(str)
        
        return df.to_dict('records')