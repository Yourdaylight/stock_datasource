"""Database schema definitions for ClickHouse tables.

Note: ODS/DIM/FACT table schemas are now defined in plugins and loaded dynamically.
This file only contains metadata table schemas for system operations.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import date, datetime
from enum import Enum


class TableType(str, Enum):
    """Table types."""
    ODS = "ods"  # Operational Data Store
    DIM = "dim"  # Dimension table
    FACT = "fact"  # Fact table
    META = "meta"  # Metadata table
    VW = "vw"  # View


class ColumnDefinition(BaseModel):
    """Column definition for dynamic schema."""
    name: str
    data_type: str
    nullable: bool = True
    default_value: Optional[str] = None
    comment: Optional[str] = None


class TableSchema(BaseModel):
    """Table schema definition."""
    table_name: str
    table_type: TableType
    columns: List[ColumnDefinition]
    partition_by: Optional[str] = None
    order_by: List[str]
    engine: str = "ReplacingMergeTree"
    engine_params: Optional[List[str]] = None
    comment: Optional[str] = None


# Metadata Schemas (System tables)
META_INGESTION_LOG_SCHEMA = TableSchema(
    table_name="meta_ingestion_log",
    table_type=TableType.META,
    columns=[
        ColumnDefinition(name="id", data_type="UInt64", nullable=False),
        ColumnDefinition(name="task_id", data_type="String", nullable=False),
        ColumnDefinition(name="api_name", data_type="String", nullable=False),
        ColumnDefinition(name="table_name", data_type="String", nullable=False),
        ColumnDefinition(name="start_time", data_type="DateTime", nullable=False),
        ColumnDefinition(name="end_time", data_type="DateTime", nullable=True),
        ColumnDefinition(name="status", data_type="String", nullable=False),
        ColumnDefinition(name="records_processed", data_type="UInt64", nullable=True),
        ColumnDefinition(name="error_message", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="created_at", data_type="DateTime", nullable=False, default_value="now()"),
    ],
    partition_by="toYYYYMM(created_at)",
    order_by=["created_at", "task_id"],
    engine="MergeTree",
    engine_params=None,
    comment="Ingestion execution log"
)


META_FAILED_TASK_SCHEMA = TableSchema(
    table_name="meta_failed_task",
    table_type=TableType.META,
    columns=[
        ColumnDefinition(name="id", data_type="UInt64", nullable=False),
        ColumnDefinition(name="task_id", data_type="String", nullable=False),
        ColumnDefinition(name="api_name", data_type="String", nullable=False),
        ColumnDefinition(name="table_name", data_type="String", nullable=False),
        ColumnDefinition(name="failed_at", data_type="DateTime", nullable=False),
        ColumnDefinition(name="error_message", data_type="String", nullable=False),
        ColumnDefinition(name="retry_count", data_type="UInt8", nullable=False, default_value="0"),
        ColumnDefinition(name="max_retries", data_type="UInt8", nullable=False, default_value="3"),
        ColumnDefinition(name="created_at", data_type="DateTime", nullable=False, default_value="now()"),
    ],
    partition_by="toYYYYMM(failed_at)",
    order_by=["failed_at", "task_id"],
    engine="MergeTree",
    engine_params=None,
    comment="Failed task records for retry management"
)


META_QUALITY_CHECK_SCHEMA = TableSchema(
    table_name="meta_quality_check",
    table_type=TableType.META,
    columns=[
        ColumnDefinition(name="id", data_type="UInt64", nullable=False),
        ColumnDefinition(name="check_name", data_type="String", nullable=False),
        ColumnDefinition(name="table_name", data_type="String", nullable=False),
        ColumnDefinition(name="check_date", data_type="Date", nullable=False),
        ColumnDefinition(name="check_result", data_type="String", nullable=False),
        ColumnDefinition(name="expected_value", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="actual_value", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="status", data_type="String", nullable=False),
        ColumnDefinition(name="error_details", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="created_at", data_type="DateTime", nullable=False, default_value="now()"),
    ],
    partition_by="toYYYYMM(check_date)",
    order_by=["check_date", "check_name"],
    engine="MergeTree",
    engine_params=None,
    comment="Data quality check results"
)


META_SCHEMA_CATALOG_SCHEMA = TableSchema(
    table_name="meta_schema_catalog",
    table_type=TableType.META,
    columns=[
        ColumnDefinition(name="id", data_type="UInt64", nullable=False),
        ColumnDefinition(name="table_name", data_type="String", nullable=False),
        ColumnDefinition(name="column_name", data_type="String", nullable=False),
        ColumnDefinition(name="data_type", data_type="String", nullable=False),
        ColumnDefinition(name="nullable", data_type="Bool", nullable=False),
        ColumnDefinition(name="default_value", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="comment", data_type="Nullable(String)", nullable=True),
        ColumnDefinition(name="is_active", data_type="Bool", nullable=False, default_value="true"),
        ColumnDefinition(name="created_at", data_type="DateTime", nullable=False, default_value="now()"),
        ColumnDefinition(name="updated_at", data_type="DateTime", nullable=False, default_value="now()"),
    ],
    partition_by="toYYYYMM(created_at)",
    order_by=["table_name", "column_name"],
    engine="MergeTree",
    engine_params=None,
    comment="Schema catalog for dynamic table management"
)


# Predefined schemas created automatically on startup.
#
# NOTE:
# - Most ODS/DIM schemas are loaded from plugins (schema.json) and created dynamically.
# - A small set of core FACT tables are also defined here because business APIs depend on them.

FACT_DAILY_BAR_SCHEMA = TableSchema(
    table_name="fact_daily_bar",
    table_type=TableType.FACT,
    columns=[
        ColumnDefinition(name="ts_code", data_type="LowCardinality(String)", nullable=False),
        ColumnDefinition(name="trade_date", data_type="Date", nullable=False),

        ColumnDefinition(name="open", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="high", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="low", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="close", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="pre_close", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="change", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="pct_chg", data_type="Nullable(Float64)", nullable=True),

        ColumnDefinition(name="vol", data_type="Nullable(Float64)", nullable=True),
        ColumnDefinition(name="amount", data_type="Nullable(Float64)", nullable=True),

        ColumnDefinition(name="adj_factor", data_type="Nullable(Float64)", nullable=True),

        ColumnDefinition(name="version", data_type="UInt32", nullable=False, default_value="toUInt32(toUnixTimestamp(now()))"),
        ColumnDefinition(name="_ingested_at", data_type="DateTime", nullable=False, default_value="now()"),
        ColumnDefinition(name="created_at", data_type="DateTime", nullable=False, default_value="now()"),
        ColumnDefinition(name="updated_at", data_type="DateTime", nullable=False, default_value="now()"),
    ],
    partition_by="toYYYYMM(trade_date)",
    order_by=["ts_code", "trade_date"],
    engine="ReplacingMergeTree",
    engine_params=["updated_at"],
    comment="Daily OHLCV facts for market overview",
)

PREDEFINED_SCHEMAS = {
    "meta_ingestion_log": META_INGESTION_LOG_SCHEMA,
    "meta_failed_task": META_FAILED_TASK_SCHEMA,
    "meta_quality_check": META_QUALITY_CHECK_SCHEMA,
    "meta_schema_catalog": META_SCHEMA_CATALOG_SCHEMA,
    "fact_daily_bar": FACT_DAILY_BAR_SCHEMA,
}
