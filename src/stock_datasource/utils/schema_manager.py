"""Schema management utilities for dynamic table creation and evolution."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.models.schemas import (
    TableSchema, ColumnDefinition, TableType,
    PREDEFINED_SCHEMAS, META_SCHEMA_CATALOG_SCHEMA
)
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class SchemaManager:
    """Manages dynamic schema creation and evolution."""
    
    def __init__(self):
        self.db = db_client
    
    def create_table_from_schema(self, schema: TableSchema) -> None:
        """Create table from schema definition."""
        if self.db.table_exists(schema.table_name):
            logger.info(f"Table {schema.table_name} already exists")
            return
        
        create_sql = self._build_create_table_sql(schema)
        self.db.create_table(create_sql)
        self._log_schema_change(schema.table_name, "CREATE_TABLE", create_sql)
        logger.info(f"Created table {schema.table_name}")
    
    def _build_create_table_sql(self, schema: TableSchema) -> str:
        """Build CREATE TABLE SQL from schema definition."""
        columns_sql = []
        for col in schema.columns:
            col_sql = f"{col.name} {col.data_type}"
            if col.default_value:
                col_sql += f" DEFAULT {col.default_value}"
            if col.comment:
                col_sql += f" COMMENT '{col.comment}'"
            columns_sql.append(col_sql)
        
        # Build engine SQL
        if schema.engine_params:
            engine_sql = f"{schema.engine}({', '.join(schema.engine_params)})"
        else:
            engine_sql = schema.engine
        
        sql_parts = [
            f"CREATE TABLE IF NOT EXISTS {schema.table_name} (",
            ",\n".join(columns_sql),
            f") ENGINE = {engine_sql}"
        ]
        
        if schema.partition_by:
            sql_parts.append(f"PARTITION BY {schema.partition_by}")
        
        if schema.order_by:
            sql_parts.append(f"ORDER BY ({', '.join(schema.order_by)})")
        
        if schema.comment:
            sql_parts.append(f"COMMENT '{schema.comment}'")
        
        return "\n".join(sql_parts)
    
    def sync_schema_from_api(self, table_name: str, api_data: pd.DataFrame, 
                           api_name: str) -> bool:
        """
        Sync table schema with API data (Schema-on-API).
        Returns True if schema was modified.
        """
        if not self.db.table_exists(table_name):
            # Create new table with inferred schema
            schema = self._infer_schema_from_data(table_name, api_data, api_name)
            self.create_table_from_schema(schema)
            return True
        
        # Check for schema changes
        current_schema = self.db.get_table_schema(table_name)
        api_columns = set(api_data.columns)
        table_columns = {col['column_name'] for col in current_schema}
        
        new_columns = api_columns - table_columns
        type_mismatches = self._check_type_mismatches(current_schema, api_data)
        
        schema_changed = False
        
        # Add new columns
        for col_name in new_columns:
            if col_name in ['version', '_ingested_at']:
                continue
                
            inferred_type = self._infer_clickhouse_type(api_data[col_name])
            column_def = f"{col_name} {inferred_type}"
            self.db.add_column(table_name, column_def)
            self._log_schema_change(table_name, "ADD_COLUMN", column_def)
            schema_changed = True
            logger.info(f"Added column {col_name} to {table_name}")
        
        # Handle type widening
        for col_name, (current_type, new_type) in type_mismatches.items():
            if self._is_widening_conversion(current_type, new_type):
                column_def = f"{col_name} {new_type}"
                self.db.modify_column(table_name, col_name, new_type)
                self._log_schema_change(table_name, "MODIFY_COLUMN", column_def)
                schema_changed = True
                logger.info(f"Modified column {col_name} in {table_name} from {current_type} to {new_type}")
            else:
                # Log incompatible change
                self._log_schema_change(
                    table_name, 
                    "WIDEN_TYPE_FAILED", 
                    f"Cannot convert {current_type} to {new_type} for column {col_name}"
                )
                logger.warning(f"Incompatible type change for {col_name}: {current_type} -> {new_type}")
        
        return schema_changed
    
    def _infer_schema_from_data(self, table_name: str, data: pd.DataFrame, 
                               api_name: str) -> TableSchema:
        """Infer table schema from pandas DataFrame."""
        columns = []
        
        # Add data columns
        for col_name in data.columns:
            data_type = self._infer_clickhouse_type(data[col_name])
            columns.append(ColumnDefinition(
                name=col_name,
                data_type=data_type,
                nullable=True
            ))
        
        # Add system columns
        columns.extend([
            ColumnDefinition(
                name="version",
                data_type="UInt32",
                nullable=False,
                default_value="toUInt32(toUnixTimestamp(now()))"
            ),
            ColumnDefinition(
                name="_ingested_at",
                data_type="DateTime",
                nullable=False,
                default_value="now()"
            )
        ])
        
        # Determine partition and order keys
        if 'trade_date' in data.columns:
            partition_by = "toYYYYMM(trade_date)"
            order_by = ["ts_code", "trade_date"] if 'ts_code' in data.columns else ["trade_date"]
        else:
            partition_by = "toYYYYMM(_ingested_at)"
            order_by = ["_ingested_at"]
        
        return TableSchema(
            table_name=table_name,
            table_type=TableType.ODS,
            columns=columns,
            partition_by=partition_by,
            order_by=order_by,
            comment=f"ODS table for {api_name} API data"
        )
    
    def _infer_clickhouse_type(self, series: pd.Series) -> str:
        """Infer ClickHouse data type from pandas Series."""
        if pd.api.types.is_integer_dtype(series):
            return "Nullable(Int64)"
        elif pd.api.types.is_float_dtype(series):
            return "Nullable(Float64)"
        elif pd.api.types.is_bool_dtype(series):
            return "Nullable(Bool)"
        elif pd.api.types.is_datetime64_dtype(series):
            return "Nullable(DateTime)"
        elif pd.api.types.is_string_dtype(series):
            # Check if it's a code field (usually shorter, repetitive values)
            if series.name and any(keyword in series.name.lower() for keyword in ['code', 'symbol', 'ticker']):
                return "LowCardinality(String)"
            return "Nullable(String)"
        else:
            return "Nullable(String)"
    
    def _check_type_mismatches(self, current_schema: List[Dict], 
                              api_data: pd.DataFrame) -> Dict[str, tuple]:
        """Check for type mismatches between current schema and API data."""
        mismatches = {}
        
        for col_info in current_schema:
            col_name = col_info['column_name']
            if col_name not in api_data.columns or col_name in ['version', '_ingested_at']:
                continue
            
            current_type = col_info['data_type']
            inferred_type = self._infer_clickhouse_type(api_data[col_name])
            
            if current_type != inferred_type:
                mismatches[col_name] = (current_type, inferred_type)
        
        return mismatches
    
    def _is_widening_conversion(self, current_type: str, new_type: str) -> bool:
        """Check if type conversion is a widening conversion."""
        # Simple type widening rules
        widening_rules = {
            "Int32": ["Int64", "Float64"],
            "Int64": ["Float64"],
            "Float32": ["Float64"],
            "String": ["LowCardinality(String)"],
        }
        
        # Remove Nullable wrapper for comparison
        current_base = current_type.replace("Nullable(", "").replace(")", "")
        new_base = new_type.replace("Nullable(", "").replace(")", "")
        
        if current_base in widening_rules:
            return new_base in widening_rules[current_base]
        
        # Allow nullable -> non-nullable if current is already nullable
        if current_type.startswith("Nullable(") and not new_type.startswith("Nullable("):
            current_inner = current_type.replace("Nullable(", "").replace(")", "")
            return current_inner == new_type
        
        return False
    
    def _log_schema_change(self, table_name: str, change_type: str, 
                          change_details: str) -> None:
        """Log schema change to metadata table."""
        try:
            # Ensure meta table exists
            if not self.db.table_exists("meta_schema_changelog"):
                self._create_schema_changelog_table()
            
            query = """
            INSERT INTO meta_schema_changelog 
            (table_name, change_type, change_details, created_at)
            VALUES
            """
            self.db.execute(query, {
                "table_name": table_name,
                "change_type": change_type,
                "change_details": change_details,
                "created_at": datetime.now()
            })
        except Exception as e:
            logger.error(f"Failed to log schema change: {e}")
    
    def _create_schema_changelog_table(self) -> None:
        """Create schema changelog table."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS meta_schema_changelog (
            id UInt64 DEFAULT generateUUIDv4(),
            table_name String,
            change_type String,
            change_details String,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(created_at)
        ORDER BY (created_at, table_name)
        """
        self.db.create_table(create_sql)
    
    def create_predefined_tables(self) -> None:
        """Create all predefined tables."""
        total_tables = len(PREDEFINED_SCHEMAS)
        logger.info(f"Creating {total_tables} predefined tables...")
        
        for i, (table_name, schema) in enumerate(PREDEFINED_SCHEMAS.items(), 1):
            try:
                logger.info(f"Creating table {i}/{total_tables}: {table_name}")
                self.create_table_from_schema(schema)
                logger.info(f"✓ Table {table_name} created successfully")
            except Exception as e:
                logger.error(f"✗ Failed to create table {table_name}: {e}")
                raise
        
        logger.info(f"✓ All {total_tables} predefined tables created successfully")
    
    def get_schema_summary(self, table_name: str) -> Dict[str, Any]:
        """Get schema summary for a table."""
        if not self.db.table_exists(table_name):
            return {"exists": False}
        
        schema = self.db.get_table_schema(table_name)
        partitions = self.db.get_partition_info(table_name)
        
        return {
            "exists": True,
            "columns": len(schema),
            "partitions": len(partitions),
            "total_rows": sum(p.get('rows', 0) for p in partitions),
            "total_bytes": sum(p.get('bytes_on_disk', 0) for p in partitions),
            "schema": schema
        }


# Global schema manager instance
schema_manager = SchemaManager()
