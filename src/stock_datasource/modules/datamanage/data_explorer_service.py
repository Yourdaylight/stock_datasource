"""Data Explorer Service for browsing plugin data and executing SQL queries."""

import io
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
import pandas as pd

from stock_datasource.utils.logger import logger
from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client
from stock_datasource.core.base_plugin import PluginCategory

from .sql_validator import SqlValidator, SqlValidationError
from .schemas import (
    ExplorerTableInfo, ExplorerTableSchema, ExplorerColumnInfo,
    ExplorerTableListResponse, ExplorerSimpleQueryRequest,
    ExplorerSqlExecuteResponse, ExportFormat,
    SqlTemplate, SqlTemplateCreate
)


# Category labels mapping
CATEGORY_LABELS = {
    "cn_stock": "A股",
    "hk_stock": "港股",
    "index": "指数",
    "etf_fund": "ETF基金",
    "market": "市场数据",
    "reference": "参考数据",
    "fundamental": "基本面",
    "system": "系统"
}


class DataExplorerService:
    """Service for data exploration and SQL query execution."""
    
    def __init__(self):
        self.logger = logger.bind(component="DataExplorerService")
        self._table_cache: Dict[str, ExplorerTableInfo] = {}
        self._row_count_cache: Dict[str, Tuple[int, datetime]] = {}  # table -> (count, timestamp)
        self._validator: Optional[SqlValidator] = None
        self._cache_ttl = 300  # 5 minutes for table list
        self._row_count_cache_ttl = 3600  # 1 hour for row counts
    
    def _get_validator(self) -> SqlValidator:
        """Get SQL validator with lazy initialization."""
        if self._validator is None:
            tables = self._get_all_allowed_tables()
            self._validator = SqlValidator(tables)
        return self._validator
    
    def _refresh_validator(self):
        """Refresh the SQL validator with current tables."""
        tables = self._get_all_allowed_tables()
        if self._validator:
            self._validator.refresh_allowed_tables(tables)
        else:
            self._validator = SqlValidator(tables)
    
    def _get_all_allowed_tables(self) -> Set[str]:
        """Get all allowed table names from plugins."""
        tables = set()
        
        # Ensure plugins are discovered
        plugin_list = plugin_manager.list_plugins()
        if not plugin_list:
            plugin_manager.discover_plugins()
            plugin_list = plugin_manager.list_plugins()
        
        for plugin_name in plugin_list:
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if plugin:
                    schema = plugin.get_schema()
                    if schema and schema.get("table_name"):
                        tables.add(schema["table_name"])
            except Exception as e:
                self.logger.warning(f"Failed to get table name for plugin {plugin_name}: {e}")
        return tables
    
    def _get_plugin_category(self, plugin_name: str) -> str:
        """Get plugin category with normalization and inference."""
        try:
            plugin = plugin_manager.get_plugin(plugin_name)
            if plugin:
                config = plugin.get_config()
                cat = config.get("category", "")
                if cat:
                    # Normalize to lowercase
                    return cat.lower()
                
                # Infer category from plugin name
                name_lower = plugin_name.lower()
                if "index" in name_lower or "sw_" in name_lower or "ths_index" in name_lower:
                    return "index"
                elif "etf" in name_lower or "fund" in name_lower:
                    return "etf_fund"
                elif "hk_" in name_lower or "ggt_" in name_lower:
                    return "hk_stock"
                elif any(x in name_lower for x in ["daily", "stock", "stk_", "adj_", "top_", "limit"]):
                    return "cn_stock"
                elif any(x in name_lower for x in ["income", "balance", "cashflow", "fina_", "dividend"]):
                    return "fundamental"
                elif "calendar" in name_lower or "basic" in name_lower:
                    return "reference"
        except:
            pass
        return "other"
    
    def _get_table_row_count(self, table_name: str) -> Optional[int]:
        """Get table row count with caching."""
        # Check cache
        if table_name in self._row_count_cache:
            count, timestamp = self._row_count_cache[table_name]
            if (datetime.now() - timestamp).total_seconds() < self._row_count_cache_ttl:
                return count
        
        try:
            # Check if table exists first
            if not db_client.table_exists(table_name):
                return None
            
            # Get approximate count (faster than exact count for large tables)
            query = f"SELECT count() FROM {table_name}"
            result = db_client.execute_query(query)
            if not result.empty:
                count = int(result.iloc[0, 0])
                self._row_count_cache[table_name] = (count, datetime.now())
                return count
        except Exception as e:
            self.logger.warning(f"Failed to get row count for {table_name}: {e}")
        return None
    
    def get_available_tables(self, category: Optional[str] = None) -> ExplorerTableListResponse:
        """Get all available tables for exploration.
        
        Args:
            category: Filter by category (cn_stock, index, etf_fund, etc.)
            
        Returns:
            ExplorerTableListResponse with tables and categories
        """
        tables = []
        
        # Ensure plugins are discovered
        plugin_list = plugin_manager.list_plugins()
        if not plugin_list:
            plugin_manager.discover_plugins()
            plugin_list = plugin_manager.list_plugins()
        
        for plugin_name in plugin_list:
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    continue
                
                schema = plugin.get_schema()
                config = plugin.get_config()
                
                table_name = schema.get("table_name") if schema else None
                if not table_name:
                    continue
                
                # Get plugin category (normalized and inferred)
                plugin_category = self._get_plugin_category(plugin_name)
                
                # Apply category filter
                if category and plugin_category != category:
                    continue
                
                # Get row count (cached)
                row_count = self._get_table_row_count(table_name)
                
                # Parse columns
                columns = []
                for col in schema.get("columns", []):
                    columns.append(ExplorerColumnInfo(
                        name=col.get("name", ""),
                        data_type=col.get("data_type", "String"),
                        nullable=col.get("nullable", True),
                        comment=col.get("comment")
                    ))
                
                tables.append(ExplorerTableInfo(
                    plugin_name=plugin_name,
                    table_name=table_name,
                    category=plugin_category,
                    columns=columns,
                    row_count=row_count,
                    description=config.get("description", "")
                ))
            except Exception as e:
                self.logger.warning(f"Failed to get info for plugin {plugin_name}: {e}")
        
        # Sort tables by category and name
        tables.sort(key=lambda t: (t.category, t.table_name))
        
        # Category info
        categories = [
            {"key": "cn_stock", "label": "A股"},
            {"key": "hk_stock", "label": "港股"},
            {"key": "index", "label": "指数"},
            {"key": "etf_fund", "label": "ETF基金"},
            {"key": "fundamental", "label": "基本面"},
            {"key": "market", "label": "市场数据"},
            {"key": "reference", "label": "参考数据"},
            {"key": "system", "label": "系统"},
            {"key": "other", "label": "其他"}
        ]
        
        return ExplorerTableListResponse(tables=tables, categories=categories)
    
    def get_table_schema(self, table_name: str) -> Optional[ExplorerTableSchema]:
        """Get detailed table schema.
        
        Args:
            table_name: Table name
            
        Returns:
            ExplorerTableSchema or None if not found
        """
        # Ensure plugins are discovered
        plugin_list = plugin_manager.list_plugins()
        if not plugin_list:
            plugin_manager.discover_plugins()
            plugin_list = plugin_manager.list_plugins()
        
        # Find plugin by table name
        for plugin_name in plugin_list:
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    continue
                
                schema = plugin.get_schema()
                if schema and schema.get("table_name") == table_name:
                    columns = [
                        ExplorerColumnInfo(
                            name=col.get("name", ""),
                            data_type=col.get("data_type", "String"),
                            nullable=col.get("nullable", True),
                            comment=col.get("comment")
                        )
                        for col in schema.get("columns", [])
                    ]
                    
                    return ExplorerTableSchema(
                        table_name=table_name,
                        columns=columns,
                        partition_by=schema.get("partition_by"),
                        order_by=schema.get("order_by"),
                        engine=schema.get("engine", "ReplacingMergeTree"),
                        comment=schema.get("comment")
                    )
            except Exception as e:
                self.logger.warning(f"Failed to get schema for plugin {plugin_name}: {e}")
        
        return None
    
    def execute_simple_query(
        self, 
        table_name: str, 
        request: ExplorerSimpleQueryRequest
    ) -> ExplorerSqlExecuteResponse:
        """Execute simple filter query on a table.
        
        Args:
            table_name: Table name to query
            request: Query parameters (filters, sorting, pagination)
            
        Returns:
            ExplorerSqlExecuteResponse with query results
        """
        # Validate table schema exists
        schema = self.get_table_schema(table_name)
        if not schema:
            # Schema not found - return empty result with table_not_exists flag
            self.logger.warning(f"Schema not found for table {table_name}")
            return ExplorerSqlExecuteResponse(
                columns=[],
                data=[],
                row_count=0,
                total_count=0,
                execution_time_ms=0,
                truncated=False,
                table_not_exists=True
            )
        
        # Check if table actually exists in database
        if not db_client.table_exists(table_name):
            # Return empty result with table_not_exists flag
            return ExplorerSqlExecuteResponse(
                columns=[col.name for col in schema.columns],
                data=[],
                row_count=0,
                total_count=0,
                execution_time_ms=0,
                truncated=False,
                table_not_exists=True
            )
        
        # Build query
        where_clauses = []
        params = {}
        
        # Process filters
        for key, value in request.filters.items():
            if value is None:
                continue
            
            # Handle date range filters
            if key == "start_date" and value:
                # Find date column
                date_col = self._find_date_column(schema)
                if date_col:
                    where_clauses.append(f"{date_col} >= %(start_date)s")
                    params["start_date"] = value
            elif key == "end_date" and value:
                date_col = self._find_date_column(schema)
                if date_col:
                    where_clauses.append(f"{date_col} <= %(end_date)s")
                    params["end_date"] = value
            elif key == "codes" and value:
                # Handle code filter (list of codes)
                code_col = self._find_code_column(schema)
                if code_col and isinstance(value, list) and len(value) > 0:
                    placeholders = ", ".join([f"%(code_{i})s" for i in range(len(value))])
                    where_clauses.append(f"{code_col} IN ({placeholders})")
                    for i, code in enumerate(value):
                        params[f"code_{i}"] = code
            elif key == "code_pattern" and value:
                code_col = self._find_code_column(schema)
                if code_col:
                    where_clauses.append(f"{code_col} LIKE %(code_pattern)s")
                    params["code_pattern"] = f"%{value}%"
        
        # Build SQL
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Validate sort column exists
        sort_col = request.sort_by
        if sort_col:
            valid_cols = {col.name for col in schema.columns}
            if sort_col not in valid_cols:
                sort_col = None
        
        # Default sort by date if available
        if not sort_col:
            date_col = self._find_date_column(schema)
            sort_col = date_col if date_col else schema.columns[0].name if schema.columns else None
        
        order_sql = f"ORDER BY {sort_col} {request.sort_order}" if sort_col else ""
        
        # Calculate offset
        offset = (request.page - 1) * request.page_size
        
        # Execute count query
        count_sql = f"SELECT count() FROM {table_name} WHERE {where_sql}"
        start_time = time.time()
        
        try:
            count_result = db_client.execute_query(count_sql, params)
            total_count = int(count_result.iloc[0, 0]) if not count_result.empty else 0
        except Exception as e:
            self.logger.error(f"Count query failed: {e}")
            total_count = 0
        
        # Execute data query
        data_sql = f"""
        SELECT * FROM {table_name} 
        WHERE {where_sql}
        {order_sql}
        LIMIT {request.page_size} OFFSET {offset}
        """
        
        try:
            result = db_client.execute_query(data_sql, params)
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            columns = list(result.columns)
            data = result.to_dict(orient='records')
            
            # Convert datetime objects to strings for JSON serialization
            for row in data:
                for key, value in row.items():
                    if isinstance(value, (datetime, pd.Timestamp)):
                        row[key] = value.isoformat() if pd.notna(value) else None
                    elif pd.isna(value):
                        row[key] = None
            
            return ExplorerSqlExecuteResponse(
                columns=columns,
                data=data,
                row_count=len(data),
                total_count=total_count,
                execution_time_ms=execution_time_ms,
                truncated=False
            )
        except Exception as e:
            raise ValueError(f"查询执行失败: {str(e)}")
    
    def _find_date_column(self, schema: ExplorerTableSchema) -> Optional[str]:
        """Find the date column in a table schema."""
        date_columns = ["trade_date", "date", "cal_date", "ann_date", "end_date"]
        for col in schema.columns:
            if col.name.lower() in date_columns:
                return col.name
        return None
    
    def _find_code_column(self, schema: ExplorerTableSchema) -> Optional[str]:
        """Find the code column in a table schema."""
        code_columns = ["ts_code", "code", "stock_code", "symbol", "index_code"]
        for col in schema.columns:
            if col.name.lower() in code_columns:
                return col.name
        return None
    
    def execute_sql_query(
        self, 
        sql: str, 
        max_rows: int = 1000,
        timeout: int = 30
    ) -> ExplorerSqlExecuteResponse:
        """Execute SQL query with security validation.
        
        Args:
            sql: SQL query to execute
            max_rows: Maximum rows to return
            timeout: Query timeout in seconds
            
        Returns:
            ExplorerSqlExecuteResponse with query results
        """
        # Validate SQL
        validator = self._get_validator()
        is_valid, error = validator.validate(sql)
        if not is_valid:
            raise ValueError(error)
        
        # Add LIMIT if missing
        sql = validator.add_limit_if_missing(sql, max_rows)
        
        # Execute query
        start_time = time.time()
        try:
            result = db_client.execute_query(
                sql, 
                settings={'max_execution_time': timeout}
            )
        except Exception as e:
            raise ValueError(f"查询执行失败: {str(e)}")
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Convert result
        columns = list(result.columns)
        data = result.to_dict(orient='records')
        row_count = len(data)
        
        # Convert datetime objects to strings
        for row in data:
            for key, value in row.items():
                if isinstance(value, (datetime, pd.Timestamp)):
                    row[key] = value.isoformat() if pd.notna(value) else None
                elif pd.isna(value):
                    row[key] = None
        
        return ExplorerSqlExecuteResponse(
            columns=columns,
            data=data,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            truncated=row_count >= max_rows
        )
    
    def export_query_result(
        self,
        sql: str,
        format: ExportFormat,
        filename: Optional[str] = None,
        max_rows: int = 10000
    ) -> Tuple[bytes, str]:
        """Export query results to CSV or Excel.
        
        Args:
            sql: SQL query
            format: Export format (csv or xlsx)
            filename: Optional filename
            max_rows: Maximum rows to export
            
        Returns:
            Tuple of (file content bytes, filename)
        """
        # Execute query
        result = self.execute_sql_query(sql, max_rows=max_rows)
        df = pd.DataFrame(result.data)
        
        # Generate filename
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"query_result_{timestamp}"
        
        # Export based on format
        if format == ExportFormat.CSV:
            content = df.to_csv(index=False).encode('utf-8-sig')  # UTF-8 with BOM for Excel compatibility
            filename = f"{filename}.csv"
        else:  # Excel
            buffer = io.BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            content = buffer.getvalue()
            filename = f"{filename}.xlsx"
        
        return content, filename
    
    # ============ SQL Template Management ============
    
    def get_templates(self, user_id: str, category: Optional[str] = None) -> List[SqlTemplate]:
        """Get SQL templates for a user.
        
        Args:
            user_id: User ID
            category: Optional category filter
            
        Returns:
            List of SqlTemplate
        """
        try:
            # Check if table exists
            if not db_client.table_exists("user_sql_templates"):
                return []
            
            where_clauses = ["user_id = %(user_id)s"]
            params = {"user_id": user_id}
            
            if category:
                where_clauses.append("category = %(category)s")
                params["category"] = category
            
            where_sql = " AND ".join(where_clauses)
            query = f"""
            SELECT id, name, description, sql, category, user_id, created_at, updated_at
            FROM user_sql_templates
            WHERE {where_sql}
            ORDER BY updated_at DESC
            """
            
            result = db_client.execute_query(query, params)
            
            templates = []
            for _, row in result.iterrows():
                templates.append(SqlTemplate(
                    id=int(row["id"]),
                    name=row["name"],
                    description=row.get("description"),
                    sql=row["sql"],
                    category=row.get("category"),
                    user_id=row.get("user_id"),
                    created_at=row.get("created_at"),
                    updated_at=row.get("updated_at")
                ))
            
            return templates
        except Exception as e:
            self.logger.error(f"Failed to get templates: {e}")
            return []
    
    def create_template(self, user_id: str, template: SqlTemplateCreate) -> SqlTemplate:
        """Create a new SQL template.
        
        Args:
            user_id: User ID
            template: Template data
            
        Returns:
            Created SqlTemplate
        """
        try:
            # Generate ID
            now = datetime.now()
            template_id = int(now.timestamp() * 1000)
            
            # Ensure table exists
            self._ensure_templates_table()
            
            # Insert template
            query = """
            INSERT INTO user_sql_templates (id, user_id, name, description, sql, category, created_at, updated_at)
            VALUES (%(id)s, %(user_id)s, %(name)s, %(description)s, %(sql)s, %(category)s, %(created_at)s, %(updated_at)s)
            """
            
            params = {
                "id": template_id,
                "user_id": user_id,
                "name": template.name,
                "description": template.description or "",
                "sql": template.sql,
                "category": template.category or "",
                "created_at": now,
                "updated_at": now
            }
            
            db_client.execute_query(query, params)
            
            return SqlTemplate(
                id=template_id,
                name=template.name,
                description=template.description,
                sql=template.sql,
                category=template.category,
                user_id=user_id,
                created_at=now,
                updated_at=now
            )
        except Exception as e:
            self.logger.error(f"Failed to create template: {e}")
            raise ValueError(f"创建模板失败: {str(e)}")
    
    def delete_template(self, user_id: str, template_id: int) -> bool:
        """Delete a SQL template.
        
        Args:
            user_id: User ID (for authorization)
            template_id: Template ID to delete
            
        Returns:
            True if deleted, False if not found or not authorized
        """
        try:
            # Check if template exists and belongs to user
            check_query = """
            SELECT id FROM user_sql_templates 
            WHERE id = %(id)s AND user_id = %(user_id)s
            LIMIT 1
            """
            result = db_client.execute_query(check_query, {"id": template_id, "user_id": user_id})
            
            if result.empty:
                return False
            
            # Delete (use ALTER TABLE DELETE for ClickHouse)
            delete_query = """
            ALTER TABLE user_sql_templates DELETE WHERE id = %(id)s AND user_id = %(user_id)s
            """
            db_client.execute_query(delete_query, {"id": template_id, "user_id": user_id})
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete template: {e}")
            return False
    
    def _ensure_templates_table(self):
        """Ensure the user_sql_templates table exists."""
        try:
            if db_client.table_exists("user_sql_templates"):
                return
            
            create_sql = """
            CREATE TABLE IF NOT EXISTS user_sql_templates (
                id UInt64,
                user_id String,
                name String,
                description String DEFAULT '',
                sql String,
                category String DEFAULT '',
                created_at DateTime DEFAULT now(),
                updated_at DateTime DEFAULT now()
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY (user_id, id)
            """
            
            db_client.execute_query(create_sql)
            self.logger.info("Created user_sql_templates table")
        except Exception as e:
            self.logger.error(f"Failed to create templates table: {e}")


# Singleton instance
data_explorer_service = DataExplorerService()
