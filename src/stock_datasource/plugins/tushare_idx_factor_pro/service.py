"""TuShare index factor pro query service."""

from typing import Any, Dict, List, Optional
import pandas as pd
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if isinstance(obj, pd.Timestamp):
        return obj.strftime('%Y%m%d')
    elif isinstance(obj, (pd.Series, dict)):
        return {k: _convert_to_json_serializable(v) for k, v in (obj.items() if isinstance(obj, dict) else obj.items())}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif pd.isna(obj):
        return None
    return obj


class TuShareIdxFactorProService(BaseService):
    """Query service for TuShare index factor pro data."""
    
    def __init__(self):
        super().__init__("tushare_idx_factor_pro")
    
    @query_method(
        description="Query index factor data by code and date range",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Index code, e.g., 000300.SH",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="indicators",
                type="list",
                description="List of indicators to return (default: all)",
                required=False,
                default=[],
            ),
        ]
    )
    def get_index_factors(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        indicators: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query index factor data.
        
        Args:
            ts_code: Index code (e.g., 000300.SH)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            indicators: List of indicators to return (default: all)
        
        Returns:
            List of index factor data records
        """
        # Build SELECT clause based on requested indicators
        base_columns = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
        
        if indicators and len(indicators) > 0:
            columns = base_columns + [ind for ind in indicators if ind not in base_columns]
        else:
            # Select all columns except system ones
            columns = "*"
        
        columns_str = ", ".join(columns) if isinstance(columns, list) else columns
        
        query = f"""
        SELECT {columns_str}
        FROM ods_idx_factor_pro
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Query latest index factor data for multiple indices",
        params=[
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of index codes",
                required=True,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Number of latest records per index",
                required=False,
                default=1,
            ),
        ]
    )
    def get_latest_factors(
        self,
        ts_codes: List[str],
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query latest index factor data for multiple indices.
        
        Args:
            ts_codes: List of index codes
            limit: Number of latest records per index
        
        Returns:
            List of latest index factor data records
        """
        codes_str = "','".join(ts_codes)
        query = f"""
        SELECT *
        FROM (
            SELECT 
                *,
                ROW_NUMBER() OVER (PARTITION BY ts_code ORDER BY trade_date DESC) as rn
            FROM ods_idx_factor_pro
            WHERE ts_code IN ('{codes_str}')
        )
        WHERE rn <= {limit}
        ORDER BY ts_code, trade_date DESC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get specific technical indicators for an index",
        params=[
            QueryParam(
                name="ts_code",
                type="str",
                description="Index code",
                required=True,
            ),
            QueryParam(
                name="indicators",
                type="list",
                description="List of indicator names (e.g., ['macd_bfq', 'kdj_bfq'])",
                required=True,
            ),
            QueryParam(
                name="start_date",
                type="str",
                description="Start date in YYYYMMDD format",
                required=True,
            ),
            QueryParam(
                name="end_date",
                type="str",
                description="End date in YYYYMMDD format",
                required=True,
            ),
        ]
    )
    def get_technical_indicators(
        self,
        ts_code: str,
        indicators: List[str],
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        """
        Get specific technical indicators for an index.
        
        Args:
            ts_code: Index code
            indicators: List of indicator names (e.g., ['macd_bfq', 'kdj_bfq'])
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            List of records with requested indicators
        """
        base_columns = ["ts_code", "trade_date"]
        columns = base_columns + indicators
        columns_str = ", ".join(columns)
        
        query = f"""
        SELECT {columns_str}
        FROM ods_idx_factor_pro
        WHERE ts_code = '{ts_code}'
        AND trade_date >= '{start_date}'
        AND trade_date <= '{end_date}'
        ORDER BY trade_date ASC
        """
        
        df = self.db.execute_query(query)
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
