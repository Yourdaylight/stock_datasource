"""Database connection and operations for ClickHouse."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from clickhouse_driver import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """ClickHouse database client."""
    
    def __init__(self):
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to ClickHouse."""
        try:
            self.client = Client(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                user=settings.CLICKHOUSE_USER,
                password=settings.CLICKHOUSE_PASSWORD,
                database=settings.CLICKHOUSE_DATABASE,
                settings={
                    'use_numpy': True,
                    'enable_http_compression': 1,
                }
            )
            logger.info(f"Connected to ClickHouse: {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a query with retry logic."""
        try:
            return self.client.execute(query, params)
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame."""
        try:
            result = self.client.query_dataframe(query, params)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, 
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table."""
        try:
            self.client.insert_dataframe(
                f"INSERT INTO {table_name} VALUES",
                df,
                settings=settings or {}
            )
            logger.info(f"Inserted {len(df)} rows into {table_name}")
        except Exception as e:
            logger.error(f"Failed to insert data into {table_name}: {e}")
            raise
    
    def create_database(self, database_name: str) -> None:
        """Create database if not exists."""
        query = f"CREATE DATABASE IF NOT EXISTS {database_name}"
        self.execute(query)
        logger.info(f"Database {database_name} created or already exists")
    
    def create_table(self, create_table_sql: str) -> None:
        """Create table from SQL definition."""
        self.execute(create_table_sql)
        logger.info("Table created successfully")
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = f"""
        SELECT count() 
        FROM system.tables 
        WHERE database = '{settings.CLICKHOUSE_DATABASE}' 
        AND name = '{table_name}'
        """
        result = self.execute(query)
        return result[0][0] > 0
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema information."""
        query = f"""
        SELECT 
            name as column_name,
            type as data_type,
            default_expression,
            comment
        FROM system.columns
        WHERE database = '{settings.CLICKHOUSE_DATABASE}'
        AND table = '{table_name}'
        ORDER BY position
        """
        result = self.execute_query(query)
        return result.to_dict('records')
    
    def add_column(self, table_name: str, column_def: str) -> None:
        """Add column to existing table."""
        query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_def}"
        self.execute(query)
        logger.info(f"Added column to {table_name}: {column_def}")
    
    def modify_column(self, table_name: str, column_name: str, new_type: str) -> None:
        """Modify column type."""
        query = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {new_type}"
        self.execute(query)
        logger.info(f"Modified column {column_name} in {table_name} to {new_type}")
    
    def get_partition_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get partition information for table."""
        query = f"""
        SELECT 
            partition,
            sum(rows) as rows,
            sum(bytes_on_disk) as bytes_on_disk
        FROM system.parts
        WHERE database = '{settings.CLICKHOUSE_DATABASE}'
        AND table = '{table_name}'
        GROUP BY partition
        ORDER BY partition
        """
        result = self.execute_query(query)
        return result.to_dict('records')
    
    def optimize_table(self, table_name: str, final: bool = True) -> None:
        """Optimize table."""
        query = f"OPTIMIZE TABLE {table_name}"
        if final:
            query += " FINAL"
        self.execute(query)
        logger.info(f"Optimized table {table_name}")
    
    def close(self):
        """Close database connection."""
        if self.client:
            self.client.disconnect()
            logger.info("ClickHouse connection closed")


# Global database client instance
db_client = ClickHouseClient()
