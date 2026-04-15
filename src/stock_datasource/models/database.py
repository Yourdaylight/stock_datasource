"""Database connection and operations for ClickHouse."""

import logging
import threading
import io
import re
from typing import List, Optional, Dict, Any
from datetime import datetime, date
import pandas as pd
from clickhouse_driver import Client
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


def _to_clickhouse_literal(value: Any) -> str:
    """Serialize a Python value into a safe ClickHouse SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        return f"'{value.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(value, date):
        return f"'{value.strftime('%Y-%m-%d')}'"
    if isinstance(value, (list, tuple, set)):
        return "[" + ", ".join(_to_clickhouse_literal(item) for item in value) + "]"

    text = str(value)
    escaped = (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\0", "")
    )
    return f"'{escaped}'"


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
        # Registry of table schemas for auto-create on UNKNOWN_TABLE
        self._table_schemas: Dict[str, Dict[str, Any]] = {}
        # Use a Session with trust_env=False to completely bypass OS-level proxy
        # env vars (HTTP_PROXY/HTTPS_PROXY) that may be set by plugin discovery.
        import requests as _requests
        self._session = _requests.Session()
        self._session.trust_env = False
        if self._auth:
            self._session.auth = self._auth
        logger.info(f"Initialized ClickHouse HTTP client [{name}]: {host}:{port}")
    
    def _request(self, query: str, params: Optional[Dict] = None, data: str = None) -> str:
        """Execute HTTP request to ClickHouse."""
        # Safely render bound parameters into ClickHouse SQL literals for the
        # HTTP fallback client. The native TCP client keeps true parameterization.
        if params:
            for key, value in params.items():
                placeholder = f"%({key})s"
                query = query.replace(placeholder, _to_clickhouse_literal(value))

            unreplaced = re.findall(r"%\(([^)]+)\)s", query)
            if unreplaced:
                raise ValueError(f"Unbound ClickHouse parameters in HTTP query: {unreplaced}")
        
        req_params = {"database": self.database}
        
        if data:
            req_params["query"] = query
            resp = self._session.post(self._base_url, params=req_params, data=data, timeout=60)
        else:
            # Use POST with query in body to avoid URL length limits (e.g., long PIVOT queries with CJK)
            resp = self._session.post(self._base_url, params=req_params, data=query.encode('utf-8'), timeout=60,
                                      headers={'Content-Type': 'text/plain; charset=utf-8'})
        
        if resp.status_code != 200:
            logger.error(
                f"ClickHouse HTTP error [{self.name}]: status={resp.status_code}, "
                f"url={resp.url}, body={resp.text[:300]}"
            )
        resp.raise_for_status()
        return resp.text.strip()
    
    def execute(self, query: str, params: Optional[Dict] = None) -> List[tuple]:
        """Execute a query and return results as list of tuples.
        
        On UNKNOWN_TABLE errors, automatically creates the table from registered
        schema and retries once.
        """
        with self._lock:
            try:
                # Add FORMAT for SELECT queries (including CTE WITH ... SELECT)
                query_upper = query.strip().upper()
                if (query_upper.startswith("SELECT") or query_upper.startswith("WITH")) and "FORMAT" not in query_upper:
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
                # Auto-create table on UNKNOWN_TABLE and retry once
                table_name = self._extract_unknown_table(e)
                if table_name and self._try_auto_create_table(table_name):
                    # Retry the original query
                    try:
                        query_upper = query.strip().upper()
                        if (query_upper.startswith("SELECT") or query_upper.startswith("WITH")) and "FORMAT" not in query_upper:
                            query = query.rstrip(";") + " FORMAT TabSeparatedWithNames"
                        result = self._request(query, params)
                        if not result:
                            return []
                        lines = result.split("\n")
                        if len(lines) <= 1:
                            return []
                        rows = []
                        for line in lines[1:]:
                            if line.strip():
                                rows.append(tuple(line.split("\t")))
                        return rows
                    except Exception:
                        pass  # Retry failed, fall through to original error
                logger.error(f"HTTP query execution failed [{self.name}]: {e}")
                raise
    
    def _extract_unknown_table(exc: Exception) -> Optional[str]:
        """Extract table name from a ClickHouse UNKNOWN_TABLE error.
        
        The error body is in exc.response.text for HTTPError,
        or in str(exc) for other exceptions.
        """
        error_text = ""
        # For requests.HTTPError, the body is in response.text
        if hasattr(exc, 'response') and exc.response is not None:
            error_text = getattr(exc.response, 'text', '') or ''
        if not error_text:
            error_text = str(exc)
        
        if 'UNKNOWN_TABLE' not in error_text:
            return None
        
        # Pattern: "Unknown table expression identifier 'table_name'"
        match = re.search(r"Unknown table expression identifier\s+'(\w+)'", error_text)
        if match:
            return match.group(1)
        
        # Fallback: try to extract from FROM clause context
        match = re.search(r"from\s+`?(\w+)`?", error_text, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query and return results as DataFrame."""
        with self._lock:
            try:
                query_upper = query.strip().upper()
                if (query_upper.startswith("SELECT") or query_upper.startswith("WITH")) and "FORMAT" not in query_upper:
                    query = query.rstrip(";") + " FORMAT TabSeparatedWithNames"
                
                result = self._request(query, params)
                
                if not result:
                    return pd.DataFrame()
                
                return pd.read_csv(io.StringIO(result), sep="\t", na_values=["\\N"])
            except Exception as e:
                logger.error(f"HTTP query execution failed [{self.name}]: {e}")
                raise
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame,
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table via HTTP."""
        with self._lock:
            try:
                # Truncate datetime columns to second precision for ClickHouse DateTime compatibility
                # ClickHouse DateTime type does not accept microsecond-precision timestamps in TSV
                df = df.copy()
                for col in df.columns:
                    if pd.api.types.is_datetime64_any_dtype(df[col]):
                        df[col] = df[col].dt.floor('s')
                    elif df[col].dtype == object and len(df) > 0:
                        # Check if column contains Python datetime objects
                        sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
                        if isinstance(sample, datetime):
                            df[col] = df[col].apply(
                                lambda x: x.strftime('%Y-%m-%d %H:%M:%S') if isinstance(x, datetime) else x
                            )
                
                # Sanitize string columns: ClickHouse TabSeparated format does not
                # support embedded newlines or tabs in field values (no quoting).
                for col in df.columns:
                    if df[col].dtype == object:
                        df[col] = df[col].apply(
                            lambda v: v.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
                            if isinstance(v, str) else v
                        )

                # Convert DataFrame to TabSeparated format
                # Use na_rep='\\N' so NaN/None becomes \N (ClickHouse NULL in TSV)
                data = df.to_csv(sep="\t", index=False, header=False, na_rep='\\N')
                columns = ", ".join(df.columns)
                query = f"INSERT INTO {table_name} ({columns}) FORMAT TabSeparated"
                self._request(query, data=data)
                logger.info(f"Inserted {len(df)} rows into {table_name} [{self.name}]")
            except Exception as e:
                logger.error(f"Failed to insert data into {table_name} [{self.name}]: {e}")
                raise
    
    def register_table_schema(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Register a table schema for auto-creation on UNKNOWN_TABLE errors."""
        self._table_schemas[table_name] = schema
    
    def _try_auto_create_table(self, table_name: str) -> bool:
        """Try to auto-create a table from registered schema.
        
        Returns True if table was created, False if no schema found or creation failed.
        """
        schema = self._table_schemas.get(table_name)
        if not schema:
            return False
        
        try:
            create_sql = self._build_create_table_sql(table_name, schema)
            if create_sql:
                logger.info(f"Auto-creating table {table_name} from registered schema [{self.name}]")
                self._request(create_sql)
                logger.info(f"Table {table_name} auto-created successfully [{self.name}]")
                return True
        except Exception as e:
            logger.warning(f"Failed to auto-create table {table_name} [{self.name}]: {e}")
        return False
    
    @staticmethod
    def _build_create_table_sql(table_name: str, schema: Dict[str, Any]) -> Optional[str]:
        """Build CREATE TABLE IF NOT EXISTS SQL from schema dict."""
        columns = schema.get('columns', [])
        if not columns:
            return None
        
        engine = schema.get('engine', 'MergeTree')
        engine_params = schema.get('engine_params', [])
        partition_by = schema.get('partition_by')
        order_by = schema.get('order_by', [])
        comment = schema.get('comment', '')
        
        col_defs = []
        for col in columns:
            col_type = col.get('type') or col.get('data_type', 'String')
            col_def = f"`{col['name']}` {col_type}"
            if col.get('default'):
                col_def += f" DEFAULT {col['default']}"
            if col.get('comment'):
                col_def += f" COMMENT '{col['comment']}'"
            col_defs.append(col_def)
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        create_sql += ",\n".join(f"    {col}" for col in col_defs)
        
        if engine_params:
            engine_str = f"{engine}({', '.join(engine_params)})"
        elif '(' not in engine:
            engine_str = f"{engine}()"
        else:
            engine_str = engine
        create_sql += f"\n) ENGINE = {engine_str}"
        
        if partition_by and partition_by not in ("", "tuple()", "None"):
            create_sql += f"\nPARTITION BY {partition_by}"
        
        if order_by:
            if isinstance(order_by, list):
                create_sql += f"\nORDER BY ({', '.join(order_by)})"
            else:
                create_sql += f"\nORDER BY ({order_by})"
        
        if comment:
            create_sql += f"\nCOMMENT '{comment}'"
        
        return create_sql
    
    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        query = "SELECT count() FROM system.tables WHERE database = %(database)s AND name = %(table_name)s"
        result = self._request(query, params={"database": self.database, "table_name": table_name})
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
        self.http_port = http_port if http_port != 8123 else getattr(settings, 'CLICKHOUSE_HTTP_PORT', 8123)
        self.client = None
        self._http_client = None
        self._use_http = prefer_http
        self._lock = threading.Lock()
        # Registry of table schemas for auto-create on UNKNOWN_TABLE
        self._table_schemas: Dict[str, Dict[str, Any]] = {}
        
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
                connect_timeout=3,  # Reduced from 10s for faster HTTP fallback
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
            or "BadStatusLine" in msg
            or "InvalidChunkLength" in msg
            or "Connection broken" in msg
            or "Connection reset" in msg
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
    
    def register_table_schema(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Register a table schema for auto-creation on UNKNOWN_TABLE errors."""
        self._table_schemas[table_name] = schema
        # Also register on HTTP client if available
        if self._http_client:
            self._http_client.register_table_schema(table_name, schema)
    
    def _try_auto_create_table(self, table_name: str) -> bool:
        """Try to auto-create a table from registered schema.
        
        Returns True if table was created, False if no schema found or creation failed.
        """
        schema = self._table_schemas.get(table_name)
        if not schema:
            return False
        
        try:
            create_sql = ClickHouseHttpClient._build_create_table_sql(table_name, schema)
            if create_sql:
                logger.info(f"Auto-creating table {table_name} from registered schema [{self.name}]")
                self.execute(create_sql)
                logger.info(f"Table {table_name} auto-created successfully [{self.name}]")
                return True
        except Exception as e:
            logger.warning(f"Failed to auto-create table {table_name} [{self.name}]: {e}")
        return False

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=1, max=3))
    def execute(self, query: str, params: Optional[Dict] = None) -> Any:
        """Execute a query with retry logic and auto-reconnect on transport errors.
        
        On UNKNOWN_TABLE errors, automatically creates the table from registered
        schema and retries once.
        """
        with self._lock:
            self._ensure_connected()
            
            # Use HTTP client if in HTTP mode (already has UNKNOWN_TABLE handling)
            if self._use_http and self._http_client:
                return self._http_client.execute(query, params)
            
            try:
                return self.client.execute(query, params)
            except Exception as e:
                # Auto-create table on UNKNOWN_TABLE and retry once (TCP path)
                error_msg = str(e)
                if "UNKNOWN_TABLE" in error_msg:
                    match = re.search(r"identifier\s+'(\w+)'", error_msg)
                    if not match:
                        match = re.search(r"from\s+`?(\w+)`?", error_msg, re.IGNORECASE)
                    if match:
                        table_name = match.group(1)
                        if self._try_auto_create_table(table_name):
                            try:
                                return self.client.execute(query, params)
                            except Exception:
                                pass  # Retry failed, fall through to original error
                
                if self._should_reconnect(e):
                    logger.warning(f"Reconnect ClickHouse [{self.name}] due to: {e}")
                    self._reconnect()
                    # After reconnect, check if we switched to HTTP
                    if self._use_http and self._http_client:
                        return self._http_client.execute(query, params)
                    return self.client.execute(query, params)
                logger.error(f"Query execution failed [{self.name}]: {e}")
                raise
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=1, max=3))
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
                if "No columns to parse from file" in str(e):
                    logger.warning(
                        f"Query returned empty/columnless result [{self.name}], returning empty DataFrame"
                    )
                    return pd.DataFrame()
                if self._should_reconnect(e):
                    logger.warning(f"Reconnect ClickHouse during query_dataframe [{self.name}] due to: {e}")
                    self._reconnect()
                    # After reconnect, check if we switched to HTTP
                    if self._use_http and self._http_client:
                        return self._http_client.execute_query(query, params)
                    return self.client.query_dataframe(query, params)
                logger.error(f"Query execution failed [{self.name}]: {e}")
                raise
    
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.5, min=1, max=3))
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, 
                        settings: Optional[Dict] = None) -> None:
        """Insert DataFrame into table."""
        with self._lock:
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
                if self._should_reconnect(e):
                    logger.warning(f"Reconnect ClickHouse during insert [{self.name}] due to: {e}")
                    self._reconnect()
                    # After reconnect, check if we switched to HTTP
                    if self._use_http and self._http_client:
                        self._http_client.insert_dataframe(table_name, df, settings)
                        return
                    self.client.insert_dataframe(
                        f"INSERT INTO {table_name} VALUES",
                        df,
                        settings=settings or {}
                    )
                    logger.info(f"Inserted {len(df)} rows into {table_name} [{self.name}]")
                else:
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
        
        query = """
        SELECT count() 
        FROM system.tables 
        WHERE database = %(database)s
        AND name = %(table_name)s
        """
        result = self.execute(query, params={"database": self.database, "table_name": table_name})
        return result[0][0] > 0
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get table schema information."""
        query = """
        SELECT 
            name as column_name,
            type as data_type,
            default_expression,
            comment
        FROM system.columns
        WHERE database = %(database)s
        AND table = %(table_name)s
        ORDER BY position
        """
        result = self.execute_query(query, params={"database": self.database, "table_name": table_name})
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
        query = """
        SELECT 
            partition,
            sum(rows) as rows,
            sum(bytes_on_disk) as bytes_on_disk
        FROM system.parts
        WHERE database = %(database)s
        AND table = %(table_name)s
        GROUP BY partition
        ORDER BY partition
        """
        result = self.execute_query(query, params={"database": self.database, "table_name": table_name})
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
        self.primary = ClickHouseClient(name="primary", prefer_http=True)
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
        """Execute query on primary, fallback to backup on failure."""
        try:
            return self.primary.execute(query, params)
        except Exception as e:
            if self.backup:
                logger.warning(f"Primary execute failed, falling back to backup: {e}")
                return self.backup.execute(query, params)
            raise

    def execute_query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query on primary, fallback to backup on failure."""
        try:
            return self.primary.execute_query(query, params)
        except Exception as e:
            if self.backup:
                logger.warning(f"Primary query failed, falling back to backup: {e}")
                return self.backup.execute_query(query, params)
            raise

    def query(self, query: str, params: Optional[Dict] = None) -> pd.DataFrame:
        """Execute query on primary, fallback to backup (alias for execute_query)."""
        return self.execute_query(query, params)
    
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
    
    def register_table_schema(self, table_name: str, schema: Dict[str, Any]) -> None:
        """Register a table schema on primary (and backup if available).
        
        When a query hits UNKNOWN_TABLE for this table, the db client will
        automatically create it from the registered schema instead of raising.
        """
        self.primary.register_table_schema(table_name, schema)
        if self.backup:
            try:
                self.backup.register_table_schema(table_name, schema)
            except Exception:
                pass
    
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
