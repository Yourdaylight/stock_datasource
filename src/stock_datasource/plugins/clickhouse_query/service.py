"""ClickHouse enhanced query service with table structure and stock filtering tools."""

from typing import Any, Dict, List, Optional, Union
import json
from stock_datasource.core.base_service import BaseService, query_method, QueryParam


def _convert_to_json_serializable(obj: Any) -> Any:
    """Convert non-JSON-serializable objects to JSON-compatible types."""
    if hasattr(obj, 'strftime'):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(obj, dict):
        return {k: _convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_json_serializable(item) for item in obj]
    elif str(obj) == 'nan' or obj is None:
        return None
    return obj


def _build_where_clause(conditions: Dict[str, Any]) -> tuple:
    """Build WHERE clause from conditions dictionary."""
    if not conditions:
        return "", []
    
    where_parts = []
    params = []
    
    for key, value in conditions.items():
        if isinstance(value, list):
            # Handle IN clause
            placeholders = ','.join(['%s'] * len(value))
            where_parts.append(f"{key} IN ({placeholders})")
            params.extend(value)
        elif isinstance(value, dict):
            # Handle range queries
            if 'min' in value:
                where_parts.append(f"{key} >= %s")
                params.append(value['min'])
            if 'max' in value:
                where_parts.append(f"{key} <= %s")
                params.append(value['max'])
            if 'eq' in value:
                where_parts.append(f"{key} = %s")
                params.append(value['eq'])
            if 'ne' in value:
                where_parts.append(f"{key} != %s")
                params.append(value['ne'])
            if 'like' in value:
                where_parts.append(f"{key} LIKE %s")
                params.append(value['like'])
        else:
            # Simple equality
            where_parts.append(f"{key} = %s")
            params.append(value)
    
    where_clause = " AND ".join(where_parts)
    return where_clause, params


class ClickHouseQueryService(BaseService):
    """Enhanced ClickHouse query service with table structure and stock filtering tools."""
    
    def __init__(self):
        super().__init__("clickhouse_query")
    
    @query_method(
        description="Get table structure and field information",
        params=[
            QueryParam(
                name="table",
                type="str",
                description="Table name to inspect",
                required=True,
            ),
        ],
    )
    def get_table_schema(self, table: str) -> Dict[str, Any]:
        """Get table structure and field information."""
        try:
            # Get table schema using DESCRIBE or similar
            schema_query = f"DESCRIBE TABLE {table}"
            schema_result = self.execute_query(schema_query)
            
            # Get table statistics
            stats_query = f"""
            SELECT 
                count() as row_count,
                name as table_name
            FROM {table}
            LIMIT 1
            """
            stats_result = self.execute_query(stats_query)
            
            # Format the schema information
            schema_info = {
                "table_name": table,
                "row_count": stats_result[0]["row_count"] if stats_result else 0,
                "columns": []
            }
            
            for row in schema_result:
                column_info = {
                    "name": row.get("name", ""),
                    "type": row.get("type", ""),
                    "default_type": row.get("default_type", ""),
                    "default_expression": row.get("default_expression", ""),
                    "comment": row.get("comment", ""),
                    "codec_expression": row.get("codec_expression", ""),
                    "ttl_expression": row.get("ttl_expression", "")
                }
                schema_info["columns"].append(column_info)
            
            return _convert_to_json_serializable(schema_info)
            
        except Exception as e:
            return {
                "error": str(e),
                "table_name": table,
                "columns": []
            }
    
    @query_method(
        description="List all available tables in the database",
        params=[],
    )
    def list_tables(self) -> List[str]:
        """List all available tables in the database."""
        try:
            query = "SHOW TABLES"
            result = self.execute_query(query)
            table_names = [row.get("name", "") for row in result]
            return _convert_to_json_serializable(table_names)
        except Exception as e:
            return [f"Error: {str(e)}"]
    
    @query_method(
        description="Filter ods_daily table with flexible conditions for stock price data",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format (e.g., '20241201')",
                required=False,
            ),
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of stock codes (e.g., ['000001.SZ', '000002.SZ'])",
                required=False,
            ),
            QueryParam(
                name="pct_chg_min",
                type="float",
                description="Minimum percentage change",
                required=False,
            ),
            QueryParam(
                name="pct_chg_max",
                type="float",
                description="Maximum percentage change",
                required=False,
            ),
            QueryParam(
                name="close_min",
                type="float",
                description="Minimum closing price",
                required=False,
            ),
            QueryParam(
                name="close_max",
                type="float",
                description="Maximum closing price",
                required=False,
            ),
            QueryParam(
                name="vol_min",
                type="float",
                description="Minimum volume",
                required=False,
            ),
            QueryParam(
                name="amount_min",
                type="float",
                description="Minimum amount",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of rows to return",
                required=False,
                default=100,
            ),
            QueryParam(
                name="order_by",
                type="str",
                description="Order by clause (e.g., 'pct_chg DESC', 'close ASC')",
                required=False,
                default="pct_chg DESC",
            ),
        ],
    )
    def filter_daily_data(self, **kwargs) -> List[Dict[str, Any]]:
        """Filter ods_daily table with flexible conditions."""
        try:
            # Build WHERE clause
            conditions = {}
            
            if kwargs.get("trade_date"):
                conditions["trade_date"] = kwargs["trade_date"]
            
            if kwargs.get("ts_codes"):
                conditions["ts_code"] = kwargs["ts_codes"]
            
            if kwargs.get("pct_chg_min") is not None:
                if "pct_chg" not in conditions:
                    conditions["pct_chg"] = {}
                conditions["pct_chg"]["min"] = kwargs["pct_chg_min"]
            
            if kwargs.get("pct_chg_max") is not None:
                if "pct_chg" not in conditions:
                    conditions["pct_chg"] = {}
                conditions["pct_chg"]["max"] = kwargs["pct_chg_max"]
            
            if kwargs.get("close_min") is not None:
                if "close" not in conditions:
                    conditions["close"] = {}
                conditions["close"]["min"] = kwargs["close_min"]
            
            if kwargs.get("close_max") is not None:
                if "close" not in conditions:
                    conditions["close"] = {}
                conditions["close"]["max"] = kwargs["close_max"]
            
            if kwargs.get("vol_min") is not None:
                if "vol" not in conditions:
                    conditions["vol"] = {}
                conditions["vol"]["min"] = kwargs["vol_min"]
            
            if kwargs.get("amount_min") is not None:
                if "amount" not in conditions:
                    conditions["amount"] = {}
                conditions["amount"]["min"] = kwargs["amount_min"]
            
            # Build query
            where_clause, params = _build_where_clause(conditions)
            
            base_query = """
            SELECT 
                ts_code, trade_date, open, high, low, close, 
                pre_close, change, pct_chg, vol, amount
            FROM ods_daily
            """
            
            if where_clause:
                base_query += f" WHERE {where_clause}"
            
            if kwargs.get("order_by"):
                base_query += f" ORDER BY {kwargs['order_by']}"
            
            limit = kwargs.get("limit", 100)
            base_query += f" LIMIT {limit}"
            
            result = self.execute_query(base_query, params)
            return _convert_to_json_serializable(result)
            
        except Exception as e:
            return [{"error": str(e)}]
    
    @query_method(
        description="Filter ods_daily_basic table with flexible conditions for stock fundamental data",
        params=[
            QueryParam(
                name="trade_date",
                type="str",
                description="Trade date in YYYYMMDD format (e.g., '20241201')",
                required=False,
            ),
            QueryParam(
                name="ts_codes",
                type="list",
                description="List of stock codes (e.g., ['000001.SZ', '000002.SZ'])",
                required=False,
            ),
            QueryParam(
                name="pe_min",
                type="float",
                description="Minimum P/E ratio",
                required=False,
            ),
            QueryParam(
                name="pe_max",
                type="float",
                description="Maximum P/E ratio",
                required=False,
            ),
            QueryParam(
                name="pb_min",
                type="float",
                description="Minimum P/B ratio",
                required=False,
            ),
            QueryParam(
                name="pb_max",
                type="float",
                description="Maximum P/B ratio",
                required=False,
            ),
            QueryParam(
                name="dv_ratio_min",
                type="float",
                description="Minimum dividend ratio (%)",
                required=False,
            ),
            QueryParam(
                name="dv_ratio_max",
                type="float",
                description="Maximum dividend ratio (%)",
                required=False,
            ),
            QueryParam(
                name="total_mv_min",
                type="float",
                description="Minimum total market value (in ten thousand)",
                required=False,
            ),
            QueryParam(
                name="total_mv_max",
                type="float",
                description="Maximum total market value (in ten thousand)",
                required=False,
            ),
            QueryParam(
                name="circ_mv_min",
                type="float",
                description="Minimum circulating market value (in ten thousand)",
                required=False,
            ),
            QueryParam(
                name="circ_mv_max",
                type="float",
                description="Maximum circulating market value (in ten thousand)",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of rows to return",
                required=False,
                default=100,
            ),
            QueryParam(
                name="order_by",
                type="str",
                description="Order by clause (e.g., 'pe ASC', 'total_mv DESC')",
                required=False,
                default="dv_ratio DESC",
            ),
        ],
    )
    def filter_daily_basic(self, **kwargs) -> List[Dict[str, Any]]:
        """Filter ods_daily_basic table with flexible conditions."""
        try:
            # Build WHERE clause
            conditions = {}
            
            if kwargs.get("trade_date"):
                conditions["trade_date"] = kwargs["trade_date"]
            
            if kwargs.get("ts_codes"):
                conditions["ts_code"] = kwargs["ts_codes"]
            
            # PE ratio filters
            if kwargs.get("pe_min") is not None:
                if "pe" not in conditions:
                    conditions["pe"] = {}
                conditions["pe"]["min"] = kwargs["pe_min"]
            
            if kwargs.get("pe_max") is not None:
                if "pe" not in conditions:
                    conditions["pe"] = {}
                conditions["pe"]["max"] = kwargs["pe_max"]
            
            # PB ratio filters
            if kwargs.get("pb_min") is not None:
                if "pb" not in conditions:
                    conditions["pb"] = {}
                conditions["pb"]["min"] = kwargs["pb_min"]
            
            if kwargs.get("pb_max") is not None:
                if "pb" not in conditions:
                    conditions["pb"] = {}
                conditions["pb"]["max"] = kwargs["pb_max"]
            
            # Dividend ratio filters
            if kwargs.get("dv_ratio_min") is not None:
                if "dv_ratio" not in conditions:
                    conditions["dv_ratio"] = {}
                conditions["dv_ratio"]["min"] = kwargs["dv_ratio_min"]
            
            if kwargs.get("dv_ratio_max") is not None:
                if "dv_ratio" not in conditions:
                    conditions["dv_ratio"] = {}
                conditions["dv_ratio"]["max"] = kwargs["dv_ratio_max"]
            
            # Total market value filters
            if kwargs.get("total_mv_min") is not None:
                if "total_mv" not in conditions:
                    conditions["total_mv"] = {}
                conditions["total_mv"]["min"] = kwargs["total_mv_min"]
            
            if kwargs.get("total_mv_max") is not None:
                if "total_mv" not in conditions:
                    conditions["total_mv"] = {}
                conditions["total_mv"]["max"] = kwargs["total_mv_max"]
            
            # Circulating market value filters
            if kwargs.get("circ_mv_min") is not None:
                if "circ_mv" not in conditions:
                    conditions["circ_mv"] = {}
                conditions["circ_mv"]["min"] = kwargs["circ_mv_min"]
            
            if kwargs.get("circ_mv_max") is not None:
                if "circ_mv" not in conditions:
                    conditions["circ_mv"] = {}
                conditions["circ_mv"]["max"] = kwargs["circ_mv_max"]
            
            # Build query
            where_clause, params = _build_where_clause(conditions)
            
            base_query = """
            SELECT 
                ts_code, trade_date, close, turnover_rate, turnover_rate_f, 
                volume_ratio, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
                total_share, float_share, free_share, total_mv, circ_mv
            FROM ods_daily_basic
            """
            
            if where_clause:
                base_query += f" WHERE {where_clause}"
            
            if kwargs.get("order_by"):
                base_query += f" ORDER BY {kwargs['order_by']}"
            
            limit = kwargs.get("limit", 100)
            base_query += f" LIMIT {limit}"
            
            result = self.execute_query(base_query, params)
            return _convert_to_json_serializable(result)
            
        except Exception as e:
            return [{"error": str(e)}]
    
    @query_method(
        description="Execute raw SQL query",
        params=[
            QueryParam(
                name="sql",
                type="str",
                description="Raw SQL query to execute",
                required=True,
            ),
        ],
    )
    def execute_raw_query(self, sql: str) -> List[Dict[str, Any]]:
        """Execute raw SQL query."""
        try:
            result = self.execute_query(sql)
            return _convert_to_json_serializable(result)
        except Exception as e:
            return [{"error": str(e), "sql": sql}]