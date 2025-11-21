"""Database connection and operations for ClickHouse."""

import logging
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import pandas as pd
import clickhouse_connect
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class ClickHouseClient:
    """ClickHouse database client with thread-safe connection pooling using clickhouse-connect (HTTP with native types)."""
    
    def __init__(self):
        # Use thread-local storage for connections to ensure thread safety
        self._thread_local = threading.local()
        self._init_lock = threading.Lock()
        self._connection_version = 0  # Track configuration version
    
    def _ensure_connected(self):
        """Ensure thread-local connection is initialized."""
        # Check if connection exists and is still valid
        if not hasattr(self._thread_local, 'client') or \
           not hasattr(self._thread_local, 'version') or \
           self._thread_local.version != self._connection_version:
            with self._init_lock:
                # Double-check after acquiring lock
                if not hasattr(self._thread_local, 'client') or \
                   not hasattr(self._thread_local, 'version') or \
                   self._thread_local.version != self._connection_version:
                    self._connect()
    
    def _connect(self):
        """Establish connection to ClickHouse for current thread."""
        try:
            # Create fresh settings instance to get latest configuration
            from stock_datasource.config.settings import Settings
            current_settings = Settings()
            
            # Create clickhouse-connect client (uses HTTP but returns native Python types)
            self._thread_local.client = clickhouse_connect.get_client(
                host=current_settings.CLICKHOUSE_HOST,
                port=8123,  # HTTP port
                username=current_settings.CLICKHOUSE_USER,
                password=current_settings.CLICKHOUSE_PASSWORD,
                database=current_settings.CLICKHOUSE_DATABASE
            )
            self._thread_local.database = current_settings.CLICKHOUSE_DATABASE
            self._thread_local.version = self._connection_version  # Track version
            
            logger.info(f"Connected to ClickHouse: {current_settings.CLICKHOUSE_HOST}:8123 (thread: {threading.current_thread().name})")
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            raise
    
    def reconnect(self):
        """Reconnect to ClickHouse with latest settings."""
        # Close existing connection if any
        if hasattr(self._thread_local, 'client'):
            try:
                self._thread_local.client.close()
            except:
                pass
        
        # Increment version to invalidate all cached connections
        with self._init_lock:
            self._connection_version += 1
        # Force reconnection on next use
        self._connect()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a query with retry logic. Returns raw result."""
        try:
            self._ensure_connected()
            result = self._thread_local.client.command(query, parameters=params)
            return result
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame with proper native Python types."""
        try:
            self._ensure_connected()
            # query_df returns DataFrame with native Python types (int, float, etc.)
            df = self._thread_local.client.query_df(query, parameters=params)
            return df
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, 
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table using clickhouse-connect."""
        try:
            self._ensure_connected()
            
            if df.empty:
                logger.warning(f"Empty DataFrame, skipping insert into {table_name}")
                return
            
            # Prepare DataFrame - convert date objects to datetime for ClickHouse DateTime columns
            df_prepared = df.copy()
            for col in df_prepared.columns:
                if hasattr(df_prepared[col].dtype, 'name') and df_prepared[col].dtype.name == 'object':
                    if len(df_prepared[col]) > 0:
                        first_val = df_prepared[col].iloc[0]
                        # Convert date to datetime (add time component)
                        if isinstance(first_val, date) and not isinstance(first_val, datetime):
                            df_prepared[col] = pd.to_datetime(df_prepared[col])
            
            # clickhouse-connect's insert_df handles type conversion automatically
            self._thread_local.client.insert_df(
                table=table_name,
                df=df_prepared,
                database=self._thread_local.database
            )
            
            logger.info(f"Inserted {len(df)} rows into {table_name}")
        except Exception as e:
            logger.error(f"Failed to insert data into {table_name}: {e}")
            logger.error(f"DataFrame shape: {df.shape}, columns: {df.columns.tolist()}")
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
        df = self.execute_query(query)
        # clickhouse-connect returns DataFrame with native types
        return df.iloc[0, 0] > 0
    
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
        try:
            df = self.execute_query(query)
            if not df.empty:
                return df.to_dict('records')
            else:
                return []
        except Exception as e:
            logger.error(f"Failed to get table schema for {table_name}: {e}")
            return []
    
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
        if hasattr(self._thread_local, 'client'):
            try:
                self._thread_local.client.close()
                logger.info("ClickHouse connection closed")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")


# Global database client instance
db_client = ClickHouseClient()
