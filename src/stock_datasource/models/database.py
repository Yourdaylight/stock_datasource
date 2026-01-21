"""Database connection and operations for ClickHouse."""

import logging
import threading
import io
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
from clickhouse_driver import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class ClickHouseHttpClient:
    """ClickHouse client using HTTP interface as fallback when TCP fails."""
    
    def __init__(self, host: str, port: int = 8123, user: str = "default",
                 password: str = "", database: str = "default", name: str = "http"):
        """Initialize HTTP client.
        
        Args:
            host: ClickHouse host
            port: HTTP port (default: 8123)
            user: ClickHouse user
            password: ClickHouse password
            database: ClickHouse database
            name: Client name for logging
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.name = name
        self._lock = threading.Lock()
        self._base_url = f"http://{host}:{port}/"
        self._auth = (user, password) if password else None
        logger.info(f"Initialized ClickHouse HTTP client [{name}]: {host}:{port}")
    
    def _request(self, query: str, params: Optional[Dict] = None, data: str = None) -> str:
        """Execute HTTP request to ClickHouse."""
        import requests
        
        # Handle parameterized queries by substituting params
        if params:
            for key, value in params.items():
                placeholder = f"%({key})s"
                if isinstance(value, str):
                    escaped = value.replace("'", "\\'")
                    query = query.replace(placeholder, f"'{escaped}'")
                elif isinstance(value, (int, float)):
                    query = query.replace(placeholder, str(value))
                elif isinstance(value, datetime):
                    query = query.replace(placeholder, f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'")
                else:
                    query = query.replace(placeholder, str(value))
        
        req_params = {"database": self.database}
        
        if data:
            req_params["query"] = query
            resp = requests.post(self._base_url, params=req_params, data=data, auth=self._auth, timeout=60)
        else:
            req_params["query"] = query
            resp = requests.get(self._base_url, params=req_params, auth=self._auth, timeout=60)
        
        resp.raise_for_status()
        return resp.text.strip()
    
    def execute(self, query: str, params: Optional[Dict] = None) -> List[tuple]:
        """Execute a query and return results as list of tuples."""
        with self._lock:
            try:
                # Add FORMAT for SELECT queries
                query_upper = query.strip().upper()
                if query_upper.startswith("SELECT") and "FORMAT" not in query_upper:
                    query = query.rstrip(";") + " FORMAT TabSeparatedWithNames"
                
                result = self._request(query, params)
                
                if not result:
                    return []
                
                # Parse TabSeparated result
                lines = result.split("\n")
                if len(lines) <= 1:
                    return []
                
                # Skip header line, parse data
                rows = []
                for line in lines[1:]:
                    if line.strip():
                        rows.append(tuple(line.split("\t")))
                return rows
            except Exception as e:
                logger.error(f"HTTP query execution failed [{self.name}]: {e}")
                raise
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame."""
        with self._lock:
            try:
                query_upper = query.strip().upper()
                if query_upper.startswith("SELECT") and "FORMAT" not in query_upper:
                    query = query.rstrip(";") + " FORMAT TabSeparatedWithNames"
                
                result = self._request(query, params)
                
                if not result:
                    return pd.DataFrame()
                
                return pd.read_csv(io.StringIO(result), sep="\t")
            except Exception as e:
                logger.error(f"HTTP query execution failed [{self.name}]: {e}")
                raise
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame,
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table via HTTP."""
        with self._lock:
            try:
                # Convert DataFrame to TabSeparated format
                data = df.to_csv(sep="\t", index=False, header=False)
                columns = ", ".join(df.columns)
                query = f"INSERT INTO {table_name} ({columns}) FORMAT TabSeparated"
                self._request(query, data=data)
                logger.info(f"Inserted {len(df)} rows into {table_name} [{self.name}]")
            except Exception as e:
                logger.error(f"Failed to insert data into {table_name} [{self.name}]: {e}")
                raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = f"SELECT count() FROM system.tables WHERE database = '{self.database}' AND name = '{table_name}'"
        result = self._request(query)
        return int(result.strip()) > 0 if result else False
    
    def close(self):
        """Close connection (no-op for HTTP)."""
        logger.info(f"ClickHouse HTTP connection closed [{self.name}]")


class ClickHouseClient:
    """ClickHouse database client with TCP/HTTP fallback support."""
    
    def __init__(self, host: str = None, port: int = None, user: str = None, 
                 password: str = None, database: str = None, name: str = "primary",
                 http_port: int = 8123, prefer_http: bool = False):
        """Initialize ClickHouse client.
        
        Args:
            host: ClickHouse host (default: from settings)
            port: ClickHouse TCP port (default: from settings)
            user: ClickHouse user (default: from settings)
            password: ClickHouse password (default: from settings)
            database: ClickHouse database (default: from settings)
            name: Client name for logging (default: "primary")
            http_port: HTTP port for fallback (default: 8123)
            prefer_http: If True, use HTTP directly without trying TCP first
        """
        self.host = host or settings.CLICKHOUSE_HOST
        self.port = port or settings.CLICKHOUSE_PORT
        self.user = user or settings.CLICKHOUSE_USER
        self.password = password or settings.CLICKHOUSE_PASSWORD
        self.database = database or settings.CLICKHOUSE_DATABASE
        self.name = name
        self.http_port = http_port
        self.client = None
        self._http_client = None
        self._use_http = prefer_http
        self._lock = threading.Lock()
        
        if prefer_http:
            self._init_http_client()
        else:
            self._connect()
    
    def _init_http_client(self):
        """Initialize HTTP client as fallback."""
        self._http_client = ClickHouseHttpClient(
            host=self.host,
            port=self.http_port,
            user=self.user,
            password=self.password,
            database=self.database,
            name=f"{self.name}-http"
        )
        self._use_http = True
        logger.info(f"Using HTTP fallback for ClickHouse [{self.name}]")
    
    def _connect(self):
        """Establish connection to ClickHouse via TCP, fallback to HTTP on failure."""
        try:
            # Register Asia/Beijing as alias for Asia/Shanghai to handle non-standard timezone
            self._register_timezone_alias()
            
            self.client = Client(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                connect_timeout=10,
                send_receive_timeout=60,
                sync_request_timeout=60,
                settings={
                    'use_numpy': True,
                    'enable_http_compression': 1,
                    'session_timezone': 'Asia/Shanghai',
                    'max_memory_usage': 2000000000,
                    'max_bytes_before_external_group_by': 1000000000,
                    'max_threads': 4,
                }
            )
            # Test connection
            self.client.execute("SELECT 1")
            logger.info(f"Connected to ClickHouse via TCP [{self.name}]: {self.host}:{self.port}")
            self._use_http = False
        except Exception as e:
            logger.warning(f"TCP connection failed [{self.name}]: {e}, falling back to HTTP")
            self._init_http_client()
    
    @staticmethod
    def _register_timezone_alias():
        """Register Asia/Beijing as alias for Asia/Shanghai."""
        try:
            import pytz
            if 'Asia/Beijing' not in pytz.all_timezones_set:
                pytz._tzinfo_cache['Asia/Beijing'] = pytz.timezone('Asia/Shanghai')
        except Exception:
            pass

    @staticmethod
    def _should_reconnect(exc: Exception) -> bool:
        """Check whether we should reconnect for the given exception."""
        msg = str(exc)
        return (
            isinstance(exc, EOFError)
            or isinstance(exc, OSError)
            or "Unexpected EOF while reading bytes" in msg
            or "Bad file descriptor" in msg
            or "Simultaneous queries on single connection detected" in msg
        )
    
    def _reconnect(self):
        """Force reconnect to ClickHouse."""
        try:
            if self.client:
                try:
                    self.client.disconnect()
                except Exception:
                    pass
            self._connect()
        except Exception as reconnect_err:
            logger.error(f"Reconnect to ClickHouse failed [{self.name}]: {reconnect_err}")
            raise
    
    def _ensure_connected(self):
        """Ensure we have a valid connection before executing query."""
        if self._use_http:
            if self._http_client is None:
                self._init_http_client()
        elif self.client is None:
            self._connect()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a query with retry logic and auto-reconnect on transport errors."""
        with self._lock:
            self._ensure_connected()
            
            # Use HTTP client if in HTTP mode
            if self._use_http and self._http_client:
                return self._http_client.execute(query, params)
            
            try:
                return self.client.execute(query, params)
            except Exception as e:
                if self._should_reconnect(e):
                    logger.warning(f"Reconnect ClickHouse [{self.name}] due to: {e}")
                    self._reconnect()
                    # After reconnect, check if we switched to HTTP
                    if self._use_http and self._http_client:
                        return self._http_client.execute(query, params)
                    return self.client.execute(query, params)
                logger.error(f"Query execution failed [{self.name}]: {e}")
                raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame with auto-reconnect on transport errors."""
        with self._lock:
            self._ensure_connected()
            
            # Use HTTP client if in HTTP mode
            if self._use_http and self._http_client:
                return self._http_client.execute_query(query, params)
            
            try:
                result = self.client.query_dataframe(query, params)
                return result
            except Exception as e:
                if self._should_reconnect(e):
                    logger.warning(f"Reconnect ClickHouse during query_dataframe [{self.name}] due to: {e}")
                    self._reconnect()
                    # After reconnect, check if we switched to HTTP
                    if self._use_http and self._http_client:
                        return self._http_client.execute_query(query, params)
                    return self.client.query_dataframe(query, params)
                logger.error(f"Query execution failed [{self.name}]: {e}")
                raise
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, 
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table."""
        self._ensure_connected()
        
        # Use HTTP client if in HTTP mode
        if self._use_http and self._http_client:
            self._http_client.insert_dataframe(table_name, df, settings)
            return
        
        try:
            self.client.insert_dataframe(
                f"INSERT INTO {table_name} VALUES",
                df,
                settings=settings or {}
            )
            logger.info(f"Inserted {len(df)} rows into {table_name} [{self.name}]")
        except Exception as e:
            logger.error(f"Failed to insert data into {table_name} [{self.name}]: {e}")
            raise
    
    def create_database(self, database_name: str) -> None:
        """Create database if not exists."""
        query = f"CREATE DATABASE IF NOT EXISTS {database_name}"
        self.execute(query)
        logger.info(f"Database {database_name} created or already exists [{self.name}]")
    
    def create_table(self, create_table_sql: str) -> None:
        """Create table from SQL definition."""
        self.execute(create_table_sql)
        logger.info(f"Table created successfully [{self.name}]")
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        if self._use_http and self._http_client:
            return self._http_client.table_exists(table_name)
        
        query = f"""
        SELECT count() 
        FROM system.tables 
        WHERE database = '{self.database}' 
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
        WHERE database = '{self.database}'
        AND table = '{table_name}'
        ORDER BY position
        """
        result = self.execute_query(query)
        return result.to_dict('records')
    
    def add_column(self, table_name: str, column_def: str) -> None:
        """Add column to existing table."""
        query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_def}"
        self.execute(query)
        logger.info(f"Added column to {table_name}: {column_def} [{self.name}]")
    
    def modify_column(self, table_name: str, column_name: str, new_type: str) -> None:
        """Modify column type."""
        query = f"ALTER TABLE {table_name} MODIFY COLUMN {column_name} {new_type}"
        self.execute(query)
        logger.info(f"Modified column {column_name} in {table_name} to {new_type} [{self.name}]")
    
    def get_partition_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get partition information for table."""
        query = f"""
        SELECT 
            partition,
            sum(rows) as rows,
            sum(bytes_on_disk) as bytes_on_disk
        FROM system.parts
        WHERE database = '{self.database}'
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
        logger.info(f"Optimized table {table_name} [{self.name}]")
    
    def close(self):
        """Close database connection."""
        if self._http_client:
            self._http_client.close()
        if self.client:
            self.client.disconnect()
            logger.info(f"ClickHouse connection closed [{self.name}]")
    
    def is_using_http(self) -> bool:
        """Check if currently using HTTP fallback."""
        return self._use_http


class DualWriteClient:
    """Client that writes to both primary and backup ClickHouse databases."""
    
    def __init__(self):
        """Initialize dual write client with primary and optional backup."""
        self.primary = ClickHouseClient(name="primary")
        self.backup = None
        
        # Initialize backup client if configured
        if settings.BACKUP_CLICKHOUSE_HOST:
            try:
                self.backup = ClickHouseClient(
                    host=settings.BACKUP_CLICKHOUSE_HOST,
                    port=settings.BACKUP_CLICKHOUSE_PORT,
                    user=settings.BACKUP_CLICKHOUSE_USER,
                    password=settings.BACKUP_CLICKHOUSE_PASSWORD,
                    database=settings.BACKUP_CLICKHOUSE_DATABASE,
                    name="backup"
                )
                logger.info(f"Dual write enabled: backup at {settings.BACKUP_CLICKHOUSE_HOST}")
            except Exception as e:
                logger.warning(f"Failed to connect to backup ClickHouse, dual write disabled: {e}")
                self.backup = None
    
    @property
    def client(self):
        """For backward compatibility - return primary client's underlying client."""
        return self.primary.client
    
    def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute query on primary (read operations use primary only)."""
        return self.primary.execute(query, params)
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query on primary and return DataFrame."""
        return self.primary.execute_query(query, params)
    
    def query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query on primary and return DataFrame (alias for execute_query)."""
        return self.primary.execute_query(query, params)
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, 
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into both primary and backup databases."""
        # Always write to primary
        self.primary.insert_dataframe(table_name, df, settings)
        
        # Write to backup if available
        if self.backup:
            try:
                self.backup.insert_dataframe(table_name, df, settings)
            except Exception as e:
                logger.error(f"Failed to write to backup database: {e}")
                # Don't raise - primary write succeeded
    
    def create_database(self, database_name: str) -> None:
        """Create database on both primary and backup."""
        self.primary.create_database(database_name)
        if self.backup:
            try:
                self.backup.create_database(database_name)
            except Exception as e:
                logger.warning(f"Failed to create database on backup: {e}")
    
    def create_table(self, create_table_sql: str) -> None:
        """Create table on both primary and backup."""
        self.primary.create_table(create_table_sql)
        if self.backup:
            try:
                self.backup.create_table(create_table_sql)
            except Exception as e:
                logger.warning(f"Failed to create table on backup: {e}")
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists on primary."""
        return self.primary.table_exists(table_name)
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema from primary."""
        return self.primary.get_table_schema(table_name)
    
    def add_column(self, table_name: str, column_def: str) -> None:
        """Add column on both primary and backup."""
        self.primary.add_column(table_name, column_def)
        if self.backup:
            try:
                self.backup.add_column(table_name, column_def)
            except Exception as e:
                logger.warning(f"Failed to add column on backup: {e}")
    
    def modify_column(self, table_name: str, column_name: str, new_type: str) -> None:
        """Modify column on both primary and backup."""
        self.primary.modify_column(table_name, column_name, new_type)
        if self.backup:
            try:
                self.backup.modify_column(table_name, column_name, new_type)
            except Exception as e:
                logger.warning(f"Failed to modify column on backup: {e}")
    
    def get_partition_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get partition info from primary."""
        return self.primary.get_partition_info(table_name)
    
    def optimize_table(self, table_name: str, final: bool = True) -> None:
        """Optimize table on both primary and backup."""
        self.primary.optimize_table(table_name, final)
        if self.backup:
            try:
                self.backup.optimize_table(table_name, final)
            except Exception as e:
                logger.warning(f"Failed to optimize table on backup: {e}")
    
    def close(self):
        """Close both connections."""
        self.primary.close()
        if self.backup:
            self.backup.close()
    
    def is_dual_write_enabled(self) -> bool:
        """Check if dual write is enabled."""
        return self.backup is not None


# Global database client instance (now with dual write support)
db_client = DualWriteClient()
