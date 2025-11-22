"""ClickHouse generic query service."""

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
    """Generic ClickHouse query service."""
    
    def __init__(self):
        super().__init__("clickhouse_query")
    
    @query_method(
        description="Execute custom query with conditions",
        params=[
            QueryParam(
                name="table",
                type="str",
                description="Table name to query",
                required=True,
            ),
            QueryParam(
                name="conditions",
                type="dict",
                description="Query conditions as key-value pairs",
                required=False,
            ),
            QueryParam(
                name="columns",
                type="list",
                description="Columns to select, default is all",
                required=False,
            ),
            QueryParam(
                name="limit",
                type="int",
                description="Maximum number of rows to return",
                required=False,
                default=1000,
            ),
            QueryParam(
                name="order_by",
                type="str",
                description="Order by clause",
                required=False,
            ),
        ]
    )
    def query_with_conditions(
        self,
        table: str,
        conditions: Optional[Dict[str, Any]] = None,
        columns: Optional[List[str]] = None,
        limit: int = 1000,
        order_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute query with flexible conditions.
        
        Args:
            table: Table name to query
            conditions: Query conditions as key-value pairs
            columns: Columns to select, default is all
            limit: Maximum number of rows to return
            order_by: Order by clause
        
        Returns:
            List of query results
        """
        # Build SELECT clause
        if columns:
            select_clause = ", ".join(columns)
        else:
            select_clause = "*"
        
        # Build WHERE clause
        where_clause, params = _build_where_clause(conditions or {})
        
        # Build complete query
        query = f"SELECT {select_clause} FROM {table}"
        if where_clause:
            query += f" WHERE {where_clause}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        
        # Execute query
        if params:
            df = self.db.execute_query(query, params)
        else:
            df = self.db.execute_query(query)
        
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Execute raw SQL query",
        params=[
            QueryParam(
                name="sql",
                type="str",
                description="Raw SQL query to execute",
                required=True,
            ),
            QueryParam(
                name="params",
                type="list",
                description="Query parameters for prepared statement",
                required=False,
            ),
        ]
    )
    def execute_raw_query(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute raw SQL query.
        
        Args:
            sql: Raw SQL query to execute
            params: Query parameters for prepared statement
        
        Returns:
            List of query results
        """
        if params:
            df = self.db.execute_query(sql, params)
        else:
            df = self.db.execute_query(sql)
        
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get table schema information",
        params=[
            QueryParam(
                name="table",
                type="str",
                description="Table name to get schema for",
                required=True,
            ),
        ]
    )
    def get_table_schema(
        self,
        table: str,
    ) -> List[Dict[str, Any]]:
        """
        Get table schema information.
        
        Args:
            table: Table name to get schema for
        
        Returns:
            List of column information
        """
        query = """
        SELECT 
            name,
            type,
            default_kind,
            default_expression
        FROM system.columns 
        WHERE table = %s
        ORDER BY position
        """
        
        df = self.db.execute_query(query, [table])
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="List all tables in the database",
        params=[
            QueryParam(
                name="database",
                type="str",
                description="Database name, default is current database",
                required=False,
            ),
        ]
    )
    def list_tables(
        self,
        database: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all tables in the database.
        
        Args:
            database: Database name, default is current database
        
        Returns:
            List of table information
        """
        if database:
            query = """
            SELECT 
                database,
                name,
                engine,
                total_rows,
                total_bytes
            FROM system.tables 
            WHERE database = %s
            ORDER BY name
            """
            df = self.db.execute_query(query, [database])
        else:
            query = """
            SELECT 
                database,
                name,
                engine,
                total_rows,
                total_bytes
            FROM system.tables 
            ORDER BY database, name
            """
            df = self.db.execute_query(query)
        
        records = df.to_dict('records')
        return [_convert_to_json_serializable(record) for record in records]
    
    @query_method(
        description="Get table statistics",
        params=[
            QueryParam(
                name="table",
                type="str",
                description="Table name to get statistics for",
                required=True,
            ),
        ]
    )
    def get_table_stats(
        self,
        table: str,
    ) -> Dict[str, Any]:
        """
        Get table statistics.
        
        Args:
            table: Table name to get statistics for
        
        Returns:
            Table statistics
        """
        query = f"""
        SELECT 
            count() as total_rows,
            countDistinct(*) as unique_rows,
            min(_timestamp) as min_timestamp,
            max(_timestamp) as max_timestamp
        FROM {table}
        """
        
        try:
            df = self.db.execute_query(query)
            records = df.to_dict('records')
            return _convert_to_json_serializable(records[0]) if records else {}
        except Exception:
            # Fallback for tables without _timestamp
            query = f"SELECT count() as total_rows FROM {table}"
            df = self.db.execute_query(query)
            records = df.to_dict('records')
            return _convert_to_json_serializable(records[0]) if records else {}