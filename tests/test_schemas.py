"""Tests for database schema definitions."""

import pytest
from datetime import datetime
import pandas as pd

from src.stock_datasource.models.schemas import (
    TableSchema, ColumnDefinition, TableType, MarketType,
    ODS_DAILY_SCHEMA, DIM_SECURITY_SCHEMA, FACT_DAILY_BAR_SCHEMA
)


class TestSchemas:
    """Test schema definitions."""
    
    def test_column_definition(self):
        """Test column definition creation."""
        col = ColumnDefinition(
            name="test_col",
            data_type="String",
            nullable=True,
            default_value="'default'",
            comment="Test column"
        )
        
        assert col.name == "test_col"
        assert col.data_type == "String"
        assert col.nullable is True
        assert col.default_value == "'default'"
        assert col.comment == "Test column"
    
    def test_table_schema_creation(self):
        """Test table schema creation."""
        schema = TableSchema(
            table_name="test_table",
            table_type=TableType.ODS,
            columns=[
                ColumnDefinition(name="col1", data_type="String"),
                ColumnDefinition(name="col2", data_type="Int64")
            ],
            partition_by="toYYYYMM(date)",
            order_by=["col1", "col2"],
            comment="Test table"
        )
        
        assert schema.table_name == "test_table"
        assert schema.table_type == TableType.ODS
        assert len(schema.columns) == 2
        assert schema.partition_by == "toYYYYMM(date)"
        assert schema.order_by == ["col1", "col2"]
        assert schema.comment == "Test table"
    
    def test_ods_daily_schema(self):
        """Test ODS daily schema definition."""
        schema = ODS_DAILY_SCHEMA
        
        assert schema.table_name == "ods_daily"
        assert schema.table_type == TableType.ODS
        assert len(schema.columns) >= 10  # At least the basic columns
        
        # Check required columns
        column_names = [col.name for col in schema.columns]
        assert "ts_code" in column_names
        assert "trade_date" in column_names
        assert "open" in column_names
        assert "high" in column_names
        assert "low" in column_names
        assert "close" in column_names
        
        # Check system columns
        assert "version" in column_names
        assert "_ingested_at" in column_names
    
    def test_dim_security_schema(self):
        """Test dimension security schema definition."""
        schema = DIM_SECURITY_SCHEMA
        
        assert schema.table_name == "dim_security"
        assert schema.table_type == TableType.DIM
        assert len(schema.columns) >= 7  # At least the basic columns
        
        # Check required columns
        column_names = [col.name for col in schema.columns]
        assert "ts_code" in column_names
        assert "market" in column_names
        assert "ticker" in column_names
        assert "name" in column_names
        assert "list_date" in column_names
        assert "status" in column_names
    
    def test_fact_daily_bar_schema(self):
        """Test fact daily bar schema definition."""
        schema = FACT_DAILY_BAR_SCHEMA
        
        assert schema.table_name == "fact_daily_bar"
        assert schema.table_type == TableType.FACT
        assert len(schema.columns) >= 12  # At least the basic columns
        
        # Check required columns
        column_names = [col.name for col in schema.columns]
        assert "ts_code" in column_names
        assert "trade_date" in column_names
        assert "open" in column_names
        assert "high" in column_names
        assert "low" in column_names
        assert "close" in column_names
        assert "adj_factor" in column_names  # Should have adjustment factor
    
    def test_market_type_enum(self):
        """Test market type enumeration."""
        assert MarketType.CN == "CN"
        assert MarketType.HK == "HK"
    
    def test_table_type_enum(self):
        """Test table type enumeration."""
        assert TableType.ODS == "ods"
        assert TableType.DIM == "dim"
        assert TableType.FACT == "fact"
        assert TableType.META == "meta"
        assert TableType.VW == "vw"
