"""Data management service layer."""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import threading
from collections import deque
import pandas as pd

from stock_datasource.utils.logger import logger
from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.core.trade_calendar import trade_calendar_service
from stock_datasource.models.database import db_client
from stock_datasource.config.settings import settings
from stock_datasource.config.runtime_config import load_runtime_config, save_runtime_config

from .schemas import (
    SyncTask, TaskStatus, TaskType,
    PluginInfo, PluginDetail, PluginConfig, PluginSchema, PluginColumn,
    PluginStatus, PluginSchedule, ScheduleFrequency,
    PluginDataPreview, MissingDataInfo, MissingDataSummary,
    SyncHistory, SyncTaskListResponse
)


class DataManageService:
    """Service for data management operations."""
    
    def __init__(self):
        self.logger = logger.bind(component="DataManageService")
        self._missing_data_cache: Optional[MissingDataSummary] = None
        self._cache_time: Optional[datetime] = None
        self._cache_days: Optional[int] = None  # Track cached days range
        self._cache_ttl = 86400  # 24 hour cache (one day)
    
    def get_trading_days(self, days: int = 30, exchange: str = "SSE") -> List[str]:
        """Get recent trading days from TradeCalendarService.
        
        Args:
            days: Number of trading days to retrieve
            exchange: Exchange code (default: SSE for Shanghai, not used - kept for API compatibility)
        
        Returns:
            List of trading dates in YYYY-MM-DD format
        """
        # Use global TradeCalendarService
        return trade_calendar_service.get_trading_days(n=days)
    
    def check_data_exists(self, table_name: str, date_column: Optional[str], trade_date: str) -> bool:
        """Check if data exists for a specific date in a table.

        Uses LIMIT 1 for efficiency instead of count() to avoid memory issues on large tables.

        Args:
            table_name: Name of the ODS table
            date_column: Name of the date column (None for dimension tables)
            trade_date: Date to check (YYYY-MM-DD format)

        Returns:
            True if data exists, False otherwise (always True for dimension tables)
        """
        # Dimension tables without date column - skip date-based check
        if not date_column:
            return True

        try:
            # First check if table exists to avoid slow retry on non-existent tables
            if not db_client.table_exists(table_name):
                self.logger.debug(f"Table {table_name} does not exist, returning False")
                return False

            # Check if date_column exists in the table before querying
            # This prevents query failures on dimension tables or tables with different schemas
            # Use cache to avoid repeated schema checks
            cache_key = f"schema_check:{table_name}:{date_column}"
            if not hasattr(self, '_schema_check_cache'):
                self._schema_check_cache = {}
            
            if cache_key in self._schema_check_cache:
                if not self._schema_check_cache[cache_key]:
                    return False
            else:
                try:
                    table_schema = db_client.get_table_schema(table_name)
                    column_names = {col['column_name'] for col in table_schema}
                    if date_column not in column_names:
                        self.logger.debug(
                            f"Date column '{date_column}' does not exist in table {table_name}. "
                            f"Available columns: {list(column_names)[:10]}"
                        )
                        self._schema_check_cache[cache_key] = False
                        return False
                    self._schema_check_cache[cache_key] = True
                except Exception as schema_error:
                    # If we can't check schema, log but don't crash - try the query anyway
                    self.logger.debug(f"Could not verify schema for {table_name}: {schema_error}")

            # Use LIMIT 1 instead of count() for memory efficiency
            query = f"""
            SELECT 1
            FROM {table_name}
            WHERE {date_column} = %(trade_date)s
            LIMIT 1
            """
            result = db_client.execute_query(query, {"trade_date": trade_date})

            return not result.empty

        except Exception as e:
            # Log the error but don't crash - return False to indicate data doesn't exist
            self.logger.warning(
                f"Failed to check data in {table_name} for {trade_date}: {type(e).__name__}: {e}"
            )
            return False
    
    def get_table_latest_date(self, table_name: str, date_column: Optional[str]) -> Optional[str]:
        """Get the latest date in a table.

        Args:
            table_name: Name of the ODS table
            date_column: Name of the date column (None for dimension tables)

        Returns:
            Latest date string or None
        """
        # Return None for dimension tables without date column
        if not date_column:
            return None

        try:
            # First check if table exists to avoid slow retry on non-existent tables
            if not db_client.table_exists(table_name):
                self.logger.debug(f"Table {table_name} does not exist, returning None")
                return None

            # Check if date_column exists in the table before querying
            # Use cache to avoid repeated schema checks
            cache_key = f"schema_check:{table_name}:{date_column}"
            if not hasattr(self, '_schema_check_cache'):
                self._schema_check_cache = {}
            
            if cache_key in self._schema_check_cache:
                if not self._schema_check_cache[cache_key]:
                    return None
            else:
                try:
                    table_schema = db_client.get_table_schema(table_name)
                    column_names = {col['column_name'] for col in table_schema}
                    if date_column not in column_names:
                        self.logger.debug(
                            f"Date column '{date_column}' does not exist in table {table_name}. "
                            f"Available columns: {list(column_names)[:10]}"
                        )
                        self._schema_check_cache[cache_key] = False
                        return None
                    self._schema_check_cache[cache_key] = True
                except Exception as schema_error:
                    self.logger.debug(f"Could not verify schema for {table_name}: {schema_error}")

            # Use ORDER BY + LIMIT 1 for efficiency on large tables
            query = f"""
            SELECT {date_column} as latest_date
            FROM {table_name}
            ORDER BY {date_column} DESC
            LIMIT 1
            """
            result = db_client.execute_query(query)

            if result.empty or result['latest_date'].iloc[0] is None:
                return None

            latest = result['latest_date'].iloc[0]
            return latest.strftime('%Y-%m-%d') if hasattr(latest, 'strftime') else str(latest)

        except Exception as e:
            self.logger.warning(
                f"Failed to get latest date from {table_name}: {type(e).__name__}: {e}"
            )
            return None
    
    def get_table_record_count(self, table_name: str) -> int:
        """Get total record count in a table using system tables for efficiency.
        
        Args:
            table_name: Name of the table
        
        Returns:
            Record count (approximate for large tables)
        """
        try:
            # Use system.parts for approximate count - much faster on large tables
            query = f"""
            SELECT sum(rows) as cnt
            FROM system.parts
            WHERE table = %(table_name)s
            AND active = 1
            """
            result = db_client.execute_query(query, {"table_name": table_name})
            
            if result.empty or result['cnt'].iloc[0] is None:
                return 0
            
            return int(result['cnt'].iloc[0])
            
        except Exception as e:
            self.logger.warning(f"Failed to get record count from {table_name}: {e}")
            return 0
    
    def _get_plugin_date_column(self, plugin_name: str) -> Optional[str]:
        """Get the date column name for a plugin's table.

        Args:
            plugin_name: Plugin name

        Returns:
            Date column name, or None if table has no date column (dimension tables)
        """
        # Dimension tables without date column - return None
        dim_tables = {
            "tushare_stock_basic",      # dim table - uses list_date but not for daily data
            "tushare_index_basic",      # dim table - uses list_date
            "tushare_index_classify",   # dim table - industry classification
            "tushare_ths_index",        # dim table - uses list_date
            "tushare_etf_basic",        # dim table - uses list_date
            "akshare_hk_stock_list",    # dim table - uses list_date
            "tushare_stock_company",    # dim table - company info
            "tushare_index_member",     # dim table - index members
            "tushare_ths_member",       # dim table - THS index members
            "tushare_etf_index",        # dim table - ETF index info
            "tushare_hk_basic",         # dim table - HK stock basic info, no trade_date
        }
        if plugin_name in dim_tables:
            return None
        
        # Special date column mappings for non-standard tables
        date_column_map = {
            "tushare_trade_calendar": "cal_date",
            "tushare_finace_indicator": "end_date",  # uses report end_date
            "tushare_etf_stk_mins": "trade_time",    # minute data uses trade_time
            "tushare_stk_mins": "trade_time",         # minute data uses trade_time
            "tushare_rt_k": "trade_time",             # real-time data uses trade_time
            "tushare_express": "ann_date",  # financial reports use ann_date
            "tushare_forecast": "ann_date",  # financial forecasts use ann_date
            "tushare_income": "ann_date",  # income statement uses ann_date
            "tushare_balancesheet": "ann_date",  # balance sheet uses ann_date
            "tushare_cashflow": "ann_date",  # cash flow uses ann_date
            "tushare_stk_surv": "surv_date",  # stock survey uses surv_date
            "tushare_report_rc": "report_date",  # report recommendations use report_date
            # VIP financial statement plugins (use ann_date or end_date)
            "tushare_balancesheet_vip": "ann_date",
            "tushare_cashflow_vip": "ann_date",
            "tushare_income_vip": "ann_date",
            # Hong Kong financial statement plugins (use end_date)
            "tushare_hk_balancesheet": "end_date",
            "tushare_hk_cashflow": "end_date",
            "tushare_hk_income": "end_date",
            "tushare_hk_fina_indicator": "end_date",

        }
        return date_column_map.get(plugin_name, "trade_date")
    
    def detect_missing_data(self, days: int = 30, force_refresh: bool = False) -> MissingDataSummary:
        """Detect missing data across all daily plugins.
        
        Args:
            days: Number of trading days to check
            force_refresh: Force refresh cache
        
        Returns:
            Summary of missing data
        """
        # Check cache - invalidate if days range changed or cache expired
        if not force_refresh and self._missing_data_cache:
            cache_valid = (
                self._cache_time and 
                self._cache_days == days and
                (datetime.now() - self._cache_time).total_seconds() < self._cache_ttl
            )
            if cache_valid:
                self.logger.debug(f"Returning cached missing data (days={days})")
                return self._missing_data_cache
        
        self.logger.info(f"Detecting missing data for last {days} trading days")
        
        # Get trading days
        trading_days = self.get_trading_days(days)
        if not trading_days:
            self.logger.warning("No trading days available for detection")
            return MissingDataSummary(
                check_time=datetime.now(),
                total_plugins=0,
                plugins_with_missing=0,
                plugins=[]
            )
        
        # Get all plugins
        plugins_info: List[MissingDataInfo] = []
        plugins_with_missing = 0
        
        for plugin_name in plugin_manager.list_plugins():
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    continue
                
                # Get schedule
                schedule = plugin.get_schedule()
                frequency = schedule.get("frequency", "daily")
                
                # Only check daily plugins for missing data
                if frequency != "daily":
                    continue
                
                # Get schema
                schema = plugin.get_schema()
                table_name = schema.get("table_name", f"ods_{plugin_name}")
                date_column = self._get_plugin_date_column(plugin_name)
                
                # Skip dimension tables without date column
                if not date_column:
                    continue
                
                # Check each trading day
                missing_dates = []
                for trade_date in trading_days:
                    if not self.check_data_exists(table_name, date_column, trade_date):
                        missing_dates.append(trade_date)
                
                # Get latest date
                latest_date = self.get_table_latest_date(table_name, date_column)
                
                info = MissingDataInfo(
                    plugin_name=plugin_name,
                    table_name=table_name,
                    schedule_frequency=frequency,
                    latest_date=latest_date,
                    missing_dates=missing_dates,
                    missing_count=len(missing_dates)
                )
                plugins_info.append(info)
                
                if missing_dates:
                    plugins_with_missing += 1
            except Exception as e:
                # Log error but continue with other plugins - one plugin failure shouldn't break others
                self.logger.error(f"Failed to check missing data for plugin {plugin_name}: {e}")
                continue
        
        summary = MissingDataSummary(
            check_time=datetime.now(),
            total_plugins=len(plugins_info),
            plugins_with_missing=plugins_with_missing,
            plugins=plugins_info
        )
        
        # Update cache
        self._missing_data_cache = summary
        self._cache_time = datetime.now()
        self._cache_days = days
        
        self.logger.info(f"Missing data detection complete: {plugins_with_missing}/{len(plugins_info)} plugins have missing data")
        return summary
    
    def _batch_get_latest_dates(self, table_date_map: Dict[str, str]) -> Dict[str, Optional[str]]:
        """Batch query latest dates for multiple tables in a single SQL.

        Args:
            table_date_map: {table_name: date_column} for tables that have date columns

        Returns:
            {table_name: latest_date_str or None}
        """
        if not table_date_map:
            return {}

        results: Dict[str, Optional[str]] = {t: None for t in table_date_map}
        db_name = db_client.primary.database if hasattr(db_client, 'primary') else db_client.database

        try:
            # Step 1: Verify which (table, column) pairs actually exist via system.columns
            table_names = list(table_date_map.keys())
            placeholders = ", ".join(f"'{t}'" for t in table_names)
            col_check_query = f"""
            SELECT table, name
            FROM system.columns
            WHERE database = '{db_name}'
            AND table IN ({placeholders})
            """
            col_df = db_client.execute_query(col_check_query)

            if col_df.empty:
                return results

            # Build set of existing (table, column) pairs
            existing_cols = set()
            for _, row in col_df.iterrows():
                existing_cols.add((row['table'], row['name']))

            # Step 2: Build UNION ALL only for validated (table, date_column) pairs
            union_parts = []
            for table_name, date_col in table_date_map.items():
                if (table_name, date_col) in existing_cols:
                    union_parts.append(
                        f"SELECT '{table_name}' AS tbl, max({date_col}) AS latest_date FROM {table_name}"
                    )

            if not union_parts:
                return results

            batch_query = " UNION ALL ".join(union_parts)
            batch_df = db_client.execute_query(batch_query)

            if not batch_df.empty:
                for _, row in batch_df.iterrows():
                    tbl = row['tbl']
                    latest = row['latest_date']
                    if latest is None:
                        continue
                    latest_str = str(latest).strip()
                    if latest_str in ('', 'NaT', 'None', '\\N'):
                        continue
                    # Format as YYYY-MM-DD
                    if hasattr(latest, 'strftime'):
                        latest_str = latest.strftime('%Y-%m-%d')
                    else:
                        latest_str = latest_str[:10]  # Trim time part
                    if latest_str.startswith('1970'):
                        continue
                    results[tbl] = latest_str

        except Exception as e:
            self.logger.warning(f"Batch latest date query failed, skipping latest dates: {e}")
            # Don't fallback to per-plugin queries — that would be even slower.

        return results

    def get_plugin_list(self) -> List[PluginInfo]:
        """Get list of all plugins with status info.
        
        Returns:
            List of plugin info
        """
        plugins: List[PluginInfo] = []

        # Phase 1: Collect plugin metadata (no DB queries)
        plugin_metas = []
        table_date_map: Dict[str, str] = {}  # {table_name: date_column}
        table_to_plugin: Dict[str, str] = {}  # {table_name: plugin_name}

        for plugin_name in plugin_manager.list_plugins():
            try:
                plugin = plugin_manager.get_plugin(plugin_name)
                if not plugin:
                    continue

                schedule = plugin.get_schedule()
                frequency = schedule.get("frequency", "daily")
                time = schedule.get("time", "18:00")

                schema = plugin.get_schema()
                table_name = schema.get("table_name", f"ods_{plugin_name}")
                date_column = self._get_plugin_date_column(plugin_name)

                category = plugin.get_category().value
                role = plugin.get_role().value
                dependencies = plugin.get_dependencies()
                optional_dependencies = plugin.get_optional_dependencies()

                plugin_metas.append({
                    "plugin_name": plugin_name,
                    "plugin": plugin,
                    "frequency": frequency,
                    "time": time,
                    "table_name": table_name,
                    "date_column": date_column,
                    "category": category,
                    "role": role,
                    "dependencies": dependencies,
                    "optional_dependencies": optional_dependencies,
                })

                if date_column:
                    table_date_map[table_name] = date_column
                    table_to_plugin[table_name] = plugin_name

            except Exception as e:
                self.logger.error(f"Failed to get plugin info for {plugin_name}: {e}")
                continue

        # Phase 2: Batch query latest dates (1~2 DB queries instead of 63*3)
        latest_dates = self._batch_get_latest_dates(table_date_map)

        # Pre-fetch trading days once (not per-plugin)
        trading_days = None
        today_str = date.today().strftime('%Y-%m-%d')
        try:
            trading_days = self.get_trading_days(30)
        except Exception:
            pass

        # Phase 3: Assemble results
        for meta in plugin_metas:
            try:
                table_name = meta["table_name"]
                date_column = meta["date_column"]
                frequency = meta["frequency"]

                latest_date = latest_dates.get(table_name) if date_column else None

                missing_count = 0
                if date_column and frequency == "daily" and latest_date and trading_days:
                    if latest_date < today_str:
                        for td in trading_days:
                            if td > latest_date:
                                missing_count += 1
                            else:
                                break

                info = PluginInfo(
                    name=meta["plugin_name"],
                    version=meta["plugin"].version,
                    description=meta["plugin"].description,
                    type="data_source",
                    category=meta["category"],
                    role=meta["role"],
                    is_enabled=meta["plugin"].is_enabled(),
                    schedule_frequency=frequency,
                    schedule_time=meta["time"],
                    latest_date=latest_date,
                    missing_count=missing_count,
                    last_run_at=None,
                    last_run_status=None,
                    dependencies=meta["dependencies"],
                    optional_dependencies=meta["optional_dependencies"],
                )
                plugins.append(info)
            except Exception as e:
                self.logger.error(f"Failed to assemble plugin info for {meta.get('plugin_name', '?')}: {e}")
                continue
        
        return plugins
    
    def get_plugin_detail(self, plugin_name: str) -> Optional[PluginDetail]:
        """Get detailed plugin information.
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            Plugin detail or None if not found
        """
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return None
        
        # Get config
        config_data = plugin.get_config()
        schedule_data = config_data.get("schedule", {})
        
        schedule = PluginSchedule(
            frequency=ScheduleFrequency(schedule_data.get("frequency", "daily")),
            time=schedule_data.get("time", "18:00"),
            day_of_week=schedule_data.get("day_of_week")
        )
        
        config = PluginConfig(
            enabled=config_data.get("enabled", True),
            rate_limit=config_data.get("rate_limit", 120),
            timeout=config_data.get("timeout", 30),
            retry_attempts=config_data.get("retry_attempts", 3),
            description=config_data.get("description", plugin.description),
            schedule=schedule,
            parameters_schema=config_data.get("parameters_schema", {})
        )
        
        # Get schema
        schema_data = plugin.get_schema()
        columns = [
            PluginColumn(
                name=col.get("name", ""),
                data_type=col.get("data_type", "String"),
                nullable=col.get("nullable", True),
                comment=col.get("comment"),
                default=col.get("default")
            )
            for col in schema_data.get("columns", [])
        ]
        
        schema = PluginSchema(
            table_name=schema_data.get("table_name", f"ods_{plugin_name}"),
            table_type=schema_data.get("table_type", "ods"),
            columns=columns,
            partition_by=schema_data.get("partition_by"),
            order_by=schema_data.get("order_by", []),
            engine=schema_data.get("engine", "ReplacingMergeTree"),
            engine_params=schema_data.get("engine_params", []),
            comment=schema_data.get("comment")
        )
        
        # Get status
        table_name = schema_data.get("table_name", f"ods_{plugin_name}")
        date_column = self._get_plugin_date_column(plugin_name)
        
        latest_date = self.get_table_latest_date(table_name, date_column)
        total_records = self.get_table_record_count(table_name)
        
        # Get missing dates for daily plugins (skip dimension tables without date column)
        missing_dates = []
        if date_column and schedule.frequency == ScheduleFrequency.DAILY:
            trading_days = self.get_trading_days(30)
            for trade_date in trading_days:
                if not self.check_data_exists(table_name, date_column, trade_date):
                    missing_dates.append(trade_date)
        
        status = PluginStatus(
            latest_date=latest_date,
            missing_count=len(missing_dates),
            missing_dates=missing_dates[:10],  # Limit to 10 for response
            total_records=total_records
        )
        
        return PluginDetail(
            plugin_name=plugin_name,
            version=plugin.version,
            description=plugin.description,
            config=config,
            table_schema=schema,
            status=status
        )
    
    def get_plugin_data_preview(
        self, 
        plugin_name: str, 
        trade_date: Optional[str] = None,
        page: int = 1,
        page_size: int = 100
    ) -> Optional[PluginDataPreview]:
        """Get data preview for a plugin.
        
        Args:
            plugin_name: Plugin name
            trade_date: Optional date filter
            page: Page number
            page_size: Page size
        
        Returns:
            Data preview or None if not found
        """
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return None
        
        schema = plugin.get_schema()
        table_name = schema.get("table_name", f"ods_{plugin_name}")
        date_column = self._get_plugin_date_column(plugin_name)
        
        # Build query
        offset = (page - 1) * page_size
        
        if trade_date and date_column:
            query = f"""
            SELECT * FROM {table_name}
            WHERE {date_column} = %(trade_date)s
            ORDER BY {date_column} DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """
            params = {"trade_date": trade_date, "limit": page_size, "offset": offset}
            
            count_query = f"""
            SELECT count() as cnt FROM {table_name}
            WHERE {date_column} = %(trade_date)s
            """
            count_params = {"trade_date": trade_date}
        elif date_column:
            query = f"""
            SELECT * FROM {table_name}
            ORDER BY {date_column} DESC
            LIMIT %(limit)s OFFSET %(offset)s
            """
            params = {"limit": page_size, "offset": offset}
            
            count_query = f"SELECT count() as cnt FROM {table_name}"
            count_params = {}
        else:
            # Dimension tables without date column
            query = f"""
            SELECT * FROM {table_name}
            LIMIT %(limit)s OFFSET %(offset)s
            """
            params = {"limit": page_size, "offset": offset}
            
            count_query = f"SELECT count() as cnt FROM {table_name}"
            count_params = {}
        
        try:
            result = db_client.execute_query(query, params)
            count_result = db_client.execute_query(count_query, count_params)
            
            total_count = int(count_result['cnt'].iloc[0]) if not count_result.empty else 0
            
            # Convert DataFrame to list of dicts
            columns = result.columns.tolist()
            data = result.to_dict('records')
            
            # Convert datetime objects to strings
            for row in data:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif hasattr(value, 'strftime'):
                        row[key] = value.strftime('%Y-%m-%d')
            
            return PluginDataPreview(
                plugin_name=plugin_name,
                table_name=table_name,
                columns=columns,
                data=data,
                total_count=total_count,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            self.logger.error(f"Failed to get data preview for {plugin_name}: {e}")
            return None
    
    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """Get plugin data status.
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            Plugin status or None if not found
        """
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return None
        
        schema = plugin.get_schema()
        table_name = schema.get("table_name", f"ods_{plugin_name}")
        date_column = self._get_plugin_date_column(plugin_name)
        
        latest_date = self.get_table_latest_date(table_name, date_column)
        total_records = self.get_table_record_count(table_name)
        
        # Get missing dates for daily plugins (skip dimension tables without date column)
        schedule = plugin.get_schedule()
        missing_dates = []
        
        if date_column and schedule.get("frequency") == "daily":
            trading_days = self.get_trading_days(30)
            for trade_date in trading_days:
                if not self.check_data_exists(table_name, date_column, trade_date):
                    missing_dates.append(trade_date)
        
        return PluginStatus(
            latest_date=latest_date,
            missing_count=len(missing_dates),
            missing_dates=missing_dates,
            total_records=total_records
        )
    
    def check_dates_data_exists(self, plugin_name: str, dates: List[str]) -> Dict[str, Any]:
        """Check if data exists for specific dates in a plugin's table.
        
        Uses batch query for efficiency when checking many dates.
        
        Args:
            plugin_name: Plugin name
            dates: List of dates to check (YYYY-MM-DD format)
        
        Returns:
            Dict with existing_dates, non_existing_dates, and record_counts
        """
        from .schemas import DataExistsCheckResult
        
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            return DataExistsCheckResult(
                plugin_name=plugin_name,
                dates_checked=dates,
                existing_dates=[],
                non_existing_dates=dates,
                record_counts={}
            )
        
        schema = plugin.get_schema()
        table_name = schema.get("table_name", f"ods_{plugin_name}")
        date_column = self._get_plugin_date_column(plugin_name)
        
        existing_dates = []
        non_existing_dates = []
        record_counts = {}
        
        if not dates:
            return DataExistsCheckResult(
                plugin_name=plugin_name,
                dates_checked=dates,
                existing_dates=[],
                non_existing_dates=[],
                record_counts={}
            )
        
        try:
            # Use DISTINCT with LIMIT for memory efficiency instead of GROUP BY count
            # This avoids aggregation which can cause memory issues on large tables
            dates_str = ", ".join([f"'{d}'" for d in dates])
            
            query = f"""
            SELECT DISTINCT toString({date_column}) as check_date
            FROM {table_name}
            WHERE {date_column} IN ({dates_str})
            """
            
            result = db_client.execute_query(query)
            
            # Build set of existing dates from query result
            existing_set = set()
            if not result.empty:
                for _, row in result.iterrows():
                    check_date = str(row['check_date'])
                    # Handle both YYYY-MM-DD and YYYYMMDD formats
                    if len(check_date) == 8 and '-' not in check_date:
                        check_date = f"{check_date[:4]}-{check_date[4:6]}-{check_date[6:]}"
                    existing_set.add(check_date)
            
            # Categorize dates
            for d in dates:
                if d in existing_set:
                    existing_dates.append(d)
                else:
                    non_existing_dates.append(d)
                    
        except Exception as e:
            self.logger.error(f"Failed to batch check data for {plugin_name}: {e}")
            # Fall back to marking all as non-existing on error
            non_existing_dates = dates
        
        return DataExistsCheckResult(
            plugin_name=plugin_name,
            dates_checked=dates,
            existing_dates=existing_dates,
            non_existing_dates=non_existing_dates,
            record_counts=record_counts
        )
    
    def check_group_data_exists(self, group_id: str, dates: List[str]) -> Dict[str, Any]:
        """Check if data exists for specific dates across all plugins in a group.
        
        Args:
            group_id: Plugin group ID
            dates: List of dates to check (YYYY-MM-DD format)
        
        Returns:
            GroupDataExistsCheckResult with per-plugin data existence info
        """
        from .schemas import (
            GroupDataExistsCheckResult, 
            PluginDataExistsInfo
        )
        from .plugin_groups import get_plugin_group
        
        group = get_plugin_group(group_id)
        if not group:
            raise ValueError(f"Group {group_id} not found")
        
        plugin_names = group.get("plugin_names", [])
        group_name = group.get("name", group_id)
        
        plugins_info = []
        plugins_with_existing_data = []
        plugins_missing_data = []
        
        for plugin_name in plugin_names:
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                continue
            
            # Get date column to check if this is a dimension table
            date_column = self._get_plugin_date_column(plugin_name)
            
            if not date_column:
                # Dimension table - check if it has any data
                schema = plugin.get_schema()
                table_name = schema.get("table_name", f"ods_{plugin_name}")
                has_data = False
                try:
                    query = f"SELECT 1 FROM {table_name} LIMIT 1"
                    result = db_client.execute_query(query)
                    has_data = not result.empty
                except Exception:
                    pass
                
                plugins_info.append(PluginDataExistsInfo(
                    plugin_name=plugin_name,
                    existing_dates=dates if has_data else [],
                    non_existing_dates=[] if has_data else dates,
                    has_date_column=False
                ))
                
                if has_data:
                    plugins_with_existing_data.append(plugin_name)
                else:
                    plugins_missing_data.append(plugin_name)
            else:
                # Daily data table - check each date
                check_result = self.check_dates_data_exists(plugin_name, dates)
                
                plugins_info.append(PluginDataExistsInfo(
                    plugin_name=plugin_name,
                    existing_dates=check_result.existing_dates,
                    non_existing_dates=check_result.non_existing_dates,
                    has_date_column=True
                ))
                
                if check_result.existing_dates:
                    plugins_with_existing_data.append(plugin_name)
                if check_result.non_existing_dates:
                    plugins_missing_data.append(plugin_name)
        
        # Determine if all plugins have data for all dates
        all_have_data = all(
            len(p.non_existing_dates) == 0 for p in plugins_info
        )
        
        return GroupDataExistsCheckResult(
            group_id=group_id,
            group_name=group_name,
            dates_checked=dates,
            plugins=plugins_info,
            all_plugins_have_data=all_have_data,
            plugins_with_existing_data=plugins_with_existing_data,
            plugins_missing_data=plugins_missing_data
        )


class SyncTaskManager:
    """Manager for sync tasks with parallel execution and database persistence.
    
    Supports:
    - At least 3 tasks running in parallel (configurable via max_concurrent_tasks)
    - Multi-date parallel processing within a single task (based on rate_limit)
    - Task persistence to ClickHouse database
    - Recovery of pending/running tasks on restart
    - Configurable parallelism (concurrent tasks and date threads)
    """
    
    # Default configuration
    DEFAULT_MAX_CONCURRENT_TASKS = 1  # Default to 1 for TuShare IP limit
    DEFAULT_MAX_DATE_CONCURRENCY = 1  # Default to 1 for TuShare IP limit
    DEFAULT_REQUESTS_PER_DATE = 10  # Estimated API requests per date
    
    # Table name for task history
    TASK_TABLE = "sync_task_history"
    
    def __init__(self, max_concurrent_tasks: int = DEFAULT_MAX_CONCURRENT_TASKS, 
                 max_date_threads: int = DEFAULT_MAX_DATE_CONCURRENCY):
        self.logger = logger.bind(component="SyncTaskManager")
        self._tasks: Dict[str, SyncTask] = {}
        self._task_queue: deque = deque()
        self._running_tasks: Dict[str, str] = {}  # task_id -> plugin_name

        # Load persisted concurrency config (fallback to provided defaults)
        base_max_tasks = max(max_concurrent_tasks, 1)
        base_max_threads = max(max_date_threads, 1)
        try:
            from stock_datasource.config.runtime_config import load_runtime_config
            persisted = load_runtime_config().get("sync", {})
            base_max_tasks = max(1, min(10, int(persisted.get("max_concurrent_tasks", base_max_tasks))))
            base_max_threads = max(1, min(20, int(persisted.get("max_date_threads", base_max_threads))))
        except Exception:
            # Ignore persistence errors and keep defaults
            pass

        self._max_concurrent_tasks = base_max_tasks
        self._max_date_threads = base_max_threads
        self._task_semaphore = threading.Semaphore(self._max_concurrent_tasks)
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._executor: Optional[Any] = None
        self._db_initialized = False
    
    def update_config(self, max_concurrent_tasks: Optional[int] = None, 
                      max_date_threads: Optional[int] = None) -> Dict[str, Any]:
        """Update parallelism configuration.
        
        Args:
            max_concurrent_tasks: Max parallel tasks (1-10)
            max_date_threads: Max threads per task for multi-date (1-20)
        
        Returns:
            Updated configuration
        """
        with self._lock:
            if max_concurrent_tasks is not None:
                old_value = self._max_concurrent_tasks
                self._max_concurrent_tasks = max(1, min(10, max_concurrent_tasks))
                # Update semaphore if changed
                if self._max_concurrent_tasks != old_value:
                    self._task_semaphore = threading.Semaphore(self._max_concurrent_tasks)
                    self.logger.info(f"Updated max_concurrent_tasks: {old_value} -> {self._max_concurrent_tasks}")
            
            if max_date_threads is not None:
                old_value = self._max_date_threads
                self._max_date_threads = max(1, min(20, max_date_threads))
                self.logger.info(f"Updated max_date_threads: {old_value} -> {self._max_date_threads}")
        
        updated = self.get_config()
        try:
            save_runtime_config(sync={
                "max_concurrent_tasks": self._max_concurrent_tasks,
                "max_date_threads": self._max_date_threads
            })
        except Exception as e:
            self.logger.warning(f"Failed to persist sync config: {e}")
        
        return updated
    
    def _ensure_table_exists(self):
        """Ensure the sync_task_history table exists in ClickHouse."""
        if self._db_initialized:
            return
        
        try:
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS sync_task_history (
                task_id String,
                plugin_name String,
                task_type String,
                status String,
                progress Float64 DEFAULT 0,
                records_processed Int64 DEFAULT 0,
                total_records Int64 DEFAULT 0,
                error_message Nullable(String),
                trade_dates Array(String) DEFAULT [],
                created_at DateTime DEFAULT now(),
                started_at Nullable(DateTime),
                completed_at Nullable(DateTime),
                updated_at DateTime DEFAULT now(),
                user_id Nullable(String),
                username Nullable(String)
            ) ENGINE = ReplacingMergeTree(updated_at)
            ORDER BY (task_id)
            """
            db_client.execute_query(create_table_sql)
            
            # Ensure user_id and username columns exist (for migration from older schema)
            try:
                db_client.execute_query(
                    "ALTER TABLE sync_task_history ADD COLUMN IF NOT EXISTS user_id Nullable(String)"
                )
                db_client.execute_query(
                    "ALTER TABLE sync_task_history ADD COLUMN IF NOT EXISTS username Nullable(String)"
                )
            except Exception as alter_err:
                self.logger.debug(f"Column migration (may already exist): {alter_err}")
            
            self._db_initialized = True
            self.logger.info("sync_task_history table ensured")
        except Exception as e:
            self.logger.error(f"Failed to create sync_task_history table: {e}")
    
    def _save_task_to_db(self, task: SyncTask):
        """Save or update a task in the database.
        
        Args:
            task: The task to save
        """
        try:
            # Convert trade_dates list to ClickHouse array format
            trade_dates_str = "[" + ",".join([f"'{d}'" for d in task.trade_dates]) + "]"
            
            # Format datetime values
            created_at = task.created_at.strftime('%Y-%m-%d %H:%M:%S') if task.created_at else 'now()'
            started_at = f"'{task.started_at.strftime('%Y-%m-%d %H:%M:%S')}'" if task.started_at else 'NULL'
            completed_at = f"'{task.completed_at.strftime('%Y-%m-%d %H:%M:%S')}'" if task.completed_at else 'NULL'
            error_msg = f"'{task.error_message}'" if task.error_message else 'NULL'
            user_id = f"'{task.user_id}'" if task.user_id else 'NULL'
            username = f"'{task.username}'" if task.username else 'NULL'
            
            insert_sql = f"""
            INSERT INTO {self.TASK_TABLE} (
                task_id, plugin_name, task_type, status, progress,
                records_processed, total_records, error_message,
                trade_dates, created_at, started_at, completed_at, updated_at,
                user_id, username
            ) VALUES (
                '{task.task_id}', '{task.plugin_name}', '{task.task_type}', 
                '{task.status.value if isinstance(task.status, TaskStatus) else task.status}',
                {task.progress}, {task.records_processed}, {task.total_records},
                {error_msg}, {trade_dates_str},
                '{created_at}', {started_at}, {completed_at}, now(),
                {user_id}, {username}
            )
            """
            db_client.execute_query(insert_sql)
            self.logger.debug(f"Task {task.task_id} saved to database")
        except Exception as e:
            self.logger.error(f"Failed to save task {task.task_id} to database: {e}")
    
    def _load_tasks_from_db(self):
        """Load recent tasks from database on startup (for display only, not auto-resume)."""
        try:
            # Load tasks from last 7 days
            # Use subquery with FINAL to get deduplicated data, then filter
            cutoff_time = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            query = f"""
            SELECT 
                task_id, plugin_name, task_type, status, progress,
                records_processed, total_records, error_message,
                trade_dates, 
                formatDateTime(created_at, '%Y-%m-%d %H:%i:%S') as created_at_str,
                formatDateTime(started_at, '%Y-%m-%d %H:%i:%S') as started_at_str,
                formatDateTime(completed_at, '%Y-%m-%d %H:%i:%S') as completed_at_str,
                user_id, username
            FROM (
                SELECT * FROM {self.TASK_TABLE} FINAL
                WHERE created_at >= toDateTime('{cutoff_time}')
                ORDER BY created_at DESC
                LIMIT 500
                SETTINGS max_threads = 2, max_memory_usage = 1000000000, max_bytes_before_external_group_by = 500000000
            )
            ORDER BY created_at DESC
            """
            result = db_client.execute_query(query)
            
            if result.empty:
                self.logger.info("No recent tasks found in database")
                return
            
            loaded_count = 0
            pending_count = 0
            
            for _, row in result.iterrows():
                task_id = row['task_id']
                status = row['status']
                
                # Parse datetime strings
                def parse_dt(val):
                    if val and val != '' and val != 'None' and val != '1970-01-01 00:00:00':
                        try:
                            return datetime.strptime(str(val)[:19], '%Y-%m-%d %H:%M:%S')
                        except:
                            return None
                    return None
                
                # Convert to SyncTask
                task = SyncTask(
                    task_id=task_id,
                    plugin_name=row['plugin_name'],
                    task_type=row['task_type'],
                    status=TaskStatus(status) if status in [s.value for s in TaskStatus] else TaskStatus.FAILED,
                    progress=float(row['progress']),
                    records_processed=int(row['records_processed']),
                    total_records=int(row['total_records']),
                    error_message=row['error_message'] if row['error_message'] else None,
                    trade_dates=list(row['trade_dates']) if row['trade_dates'] else [],
                    created_at=parse_dt(row['created_at_str']),
                    started_at=parse_dt(row['started_at_str']),
                    completed_at=parse_dt(row['completed_at_str']),
                    user_id=row.get('user_id') if row.get('user_id') else None,
                    username=row.get('username') if row.get('username') else None
                )
                
                # Add to memory for display
                self._tasks[task_id] = task
                loaded_count += 1
                
                # Count pending tasks but DO NOT auto-resume
                # User must manually trigger resume if needed
                if status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
                    pending_count += 1
            
            if pending_count > 0:
                self.logger.info(f"Loaded {loaded_count} tasks from database, {pending_count} pending/interrupted (manual resume required)")
            else:
                self.logger.info(f"Loaded {loaded_count} tasks from database")
            
        except Exception as e:
            self.logger.error(f"Failed to load tasks from database: {e}")
    
    def start(self):
        """Start the task worker thread."""
        if self._running:
            return
        
        from concurrent.futures import ThreadPoolExecutor
        
        # Ensure table exists and load existing tasks
        self._ensure_table_exists()
        self._load_tasks_from_db()
        
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self._max_concurrent_tasks + 2)
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self.logger.info(f"SyncTaskManager started with max {self._max_concurrent_tasks} concurrent tasks")
    
    def stop(self):
        """Stop the task worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        if self._executor:
            self._executor.shutdown(wait=False)
        self.logger.info("SyncTaskManager stopped")
    
    def _worker_loop(self):
        """Worker loop for processing tasks in parallel."""
        import time
        
        while self._running:
            task_id = None
            
            with self._lock:
                # Check if we can start a new task
                if self._task_queue and len(self._running_tasks) < self._max_concurrent_tasks:
                    # Find a task that doesn't conflict with running tasks
                    # (same plugin tasks should run serially to avoid data conflicts)
                    for i, queued_task_id in enumerate(self._task_queue):
                        queued_task = self._tasks.get(queued_task_id)
                        if queued_task:
                            running_plugins = set(self._running_tasks.values())
                            if queued_task.plugin_name not in running_plugins:
                                task_id = queued_task_id
                                self._task_queue.remove(queued_task_id)
                                self._running_tasks[task_id] = queued_task.plugin_name
                                break
            
            if task_id:
                # Submit task to executor for parallel execution
                self._executor.submit(self._execute_task_wrapper, task_id)
            else:
                # Sleep briefly when no tasks available
                time.sleep(0.5)
    
    def _execute_task_wrapper(self, task_id: str):
        """Wrapper for task execution with cleanup and scoped proxy."""
        from stock_datasource.core.proxy import proxy_context
        
        try:
            # Use proxy_context to apply proxy only during data extraction
            # This ensures proxy is isolated to this task and doesn't affect global settings
            with proxy_context():
                self._execute_task(task_id)
        finally:
            with self._lock:
                self._running_tasks.pop(task_id, None)
    
    def _calculate_date_concurrency(self, plugin_name: str, num_dates: int) -> int:
        """Calculate optimal date concurrency based on configured max_date_threads.
        
        Args:
            plugin_name: Plugin name
            num_dates: Number of dates to process
        
        Returns:
            Optimal number of dates to process in parallel
        """
        # Use configured max_date_threads, capped by actual number of dates
        concurrency = min(self._max_date_threads, num_dates)
        
        self.logger.debug(
            f"Date concurrency for {plugin_name}: {concurrency} "
            f"(max_date_threads={self._max_date_threads}, dates={num_dates})"
        )
        
        return concurrency
    
    def _execute_task(self, task_id: str):
        """Execute a single task with optional multi-date parallelism."""
        import traceback
        
        task = self._tasks.get(task_id)
        if not task:
            return
        
        # Update status to running and save to DB
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self._save_task_to_db(task)
        
        self.logger.info(f"Executing task {task_id} for plugin {task.plugin_name}")
        
        try:
            plugin = plugin_manager.get_plugin(task.plugin_name)
            if not plugin:
                raise ValueError(f"Plugin {task.plugin_name} not found")
            
            # Execute based on task type
            if task.task_type == TaskType.BACKFILL.value and task.trade_dates:
                # Backfill specific dates with parallel processing
                self._execute_backfill_parallel(task, plugin)
            else:
                # Determine market from plugin category
                from stock_datasource.core.base_plugin import PluginCategory
                from stock_datasource.core.trade_calendar import MARKET_CN, MARKET_HK
                market = MARKET_HK if plugin.get_category() == PluginCategory.HK_STOCK else MARKET_CN
                
                # Incremental or full sync - use latest valid trading day from calendar
                target_date = self._get_latest_trading_date(market=market)
                if not target_date:
                    raise ValueError("无法获取有效交易日，请检查交易日历数据")
                
                self.logger.info(f"Incremental sync using trading date: {target_date}")
                result = plugin.run(trade_date=target_date)
                
                if result.get("status") == "success":
                    # Convert to int to avoid numpy.uint64 serialization issues
                    task.records_processed = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                    task.progress = 100
                else:
                    # Pipeline failed - get detailed error info
                    error_msg = result.get("error", "插件执行失败")
                    error_detail = result.get("error_detail", "")
                    full_error = f"{error_msg}"
                    if error_detail:
                        full_error += f"\n\n详细信息:\n{error_detail}"
                    raise ValueError(full_error)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            self._save_task_to_db(task)
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            # Capture full traceback for debugging
            error_tb = traceback.format_exc()
            error_msg = str(e)
            
            # Limit error message length but keep useful info
            if len(error_msg) > 2000:
                error_msg = error_msg[:2000] + "... (truncated)"
            
            # Store both short message and full traceback
            task.status = TaskStatus.FAILED
            task.error_message = f"{error_msg}\n\n--- 堆栈跟踪 ---\n{error_tb}"
            task.completed_at = datetime.now()
            self._save_task_to_db(task)
            self.logger.error(f"Task {task_id} failed: {error_msg}\n{error_tb}")
    
    def _get_latest_trading_date(self, market: str = "cn") -> Optional[str]:
        """Get the latest valid trading date from calendar.
        
        Returns the most recent trading day that has data available.
        Since today's data may not be published yet (especially before market close),
        we return the previous trading day to ensure data availability.
        
        Args:
            market: Market type - 'cn' for A-share, 'hk' for HK stock
        
        Returns:
            Trading date in YYYYMMDD format, or None if calendar is unavailable
        """
        try:
            # Get recent trading days (get a few to ensure we have valid ones)
            trading_days = trade_calendar_service.get_trading_days(n=10, market=market)
            if not trading_days:
                self.logger.error("交易日历为空，无法获取有效交易日")
                return None
            
            today = date.today()
            
            # Find trading days that are strictly before today (data should be available)
            # Today's data may not be published yet, so we use previous trading day
            valid_dates = []
            for day_str in trading_days:
                try:
                    trading_date = datetime.strptime(day_str, '%Y-%m-%d').date()
                    if trading_date < today:
                        valid_dates.append(trading_date)
                except ValueError:
                    continue
            
            if valid_dates:
                # Return the most recent past trading day
                latest = max(valid_dates)
                self.logger.info(f"使用最近的有效交易日: {latest} (今天: {today}, 市场: {market})")
                return latest.strftime('%Y%m%d')
            
            # If no past trading days found, this is unusual
            # Maybe it's the first trading day of the year or calendar issue
            self.logger.warning(f"没有找到过去的交易日，交易日列表: {trading_days}")
            return None
            
        except Exception as e:
            self.logger.error(f"获取最新交易日失败: {e}")
            return None

    def _execute_backfill_parallel(self, task: SyncTask, plugin):
        """Execute backfill task with multi-date parallelism.
        
        Args:
            task: The sync task
            plugin: The plugin instance
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import time
        
        trade_dates = task.trade_dates
        total = len(trade_dates)
        task.total_records = total
        
        # Calculate date concurrency
        date_concurrency = self._calculate_date_concurrency(task.plugin_name, total)
        
        self.logger.info(
            f"Backfill task {task.task_id}: {total} dates with concurrency {date_concurrency}"
        )
        
        # Get rate limit for throttling
        config = plugin.get_config()
        rate_limit = config.get("rate_limit", 120)
        min_interval = 60.0 / rate_limit if rate_limit > 0 else 0.5
        
        completed_count = 0
        records_lock = threading.Lock()
        last_request_time = time.time()
        request_lock = threading.Lock()
        
        def process_date(trade_date: str) -> Dict[str, Any]:
            """Process a single date with rate limiting."""
            nonlocal last_request_time
            
            # Rate limiting
            with request_lock:
                elapsed = time.time() - last_request_time
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last_request_time = time.time()
            
            try:
                # Convert YYYY-MM-DD to YYYYMMDD format for tushare API
                date_for_api = trade_date.replace("-", "") if "-" in trade_date else trade_date
                result = plugin.run(trade_date=date_for_api)
                return {"date": trade_date, "result": result, "error": None}
            except Exception as e:
                return {"date": trade_date, "result": None, "error": str(e)}
        
        # Process dates in parallel with controlled concurrency
        with ThreadPoolExecutor(max_workers=date_concurrency) as executor:
            futures = {executor.submit(process_date, d): d for d in trade_dates}
            
            for future in as_completed(futures):
                result_data = future.result()
                
                with records_lock:
                    completed_count += 1
                    
                    if result_data["result"] and result_data["result"].get("status") == "success":
                        # Convert to int to avoid numpy.uint64 serialization issues
                        records = int(result_data["result"].get("steps", {}).get("load", {}).get("total_records", 0))
                        task.records_processed += records
                    elif result_data["error"]:
                        self.logger.warning(
                            f"Date {result_data['date']} failed: {result_data['error']}"
                        )
                    
                    task.progress = (completed_count / total) * 100
        
        self.logger.info(
            f"Backfill completed: {completed_count}/{total} dates, "
            f"{task.records_processed} records"
        )
    
    def create_task(
        self, 
        plugin_name: str, 
        task_type: TaskType = TaskType.INCREMENTAL,
        trade_dates: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        use_queue: bool = True,
        execution_id: Optional[str] = None
    ) -> SyncTask:
        """Create a new sync task.
        
        Args:
            plugin_name: Plugin name
            task_type: Task type
            trade_dates: List of dates for backfill
            user_id: ID of the user who triggered the task
            username: Username of the user who triggered the task
            use_queue: If True, use Redis queue (worker processes); 
                       If False, use legacy ThreadPoolExecutor
            execution_id: Batch execution ID if part of a group trigger
        
        Returns:
            Created task
        """
        if not use_queue:
            raise ValueError("Legacy in-memory execution is no longer supported; use Redis queue")

        # Redis queue is the single execution path (Mode A).
        from stock_datasource.services.task_queue import task_queue, TaskPriority, RedisUnavailableError

        # Determine priority
        priority = TaskPriority.HIGH if task_type == TaskType.INCREMENTAL else TaskPriority.NORMAL

        try:
            task_id = task_queue.enqueue(
                plugin_name=plugin_name,
                task_type=task_type.value,
                trade_dates=trade_dates,
                priority=priority,
                execution_id=execution_id,
                user_id=user_id,
            )
        except RedisUnavailableError as e:
            raise ValueError(f"Redis unavailable: {e}")

        if not task_id:
            raise ValueError("Failed to enqueue task")

        # Create SyncTask object for API response
        task = SyncTask(
            task_id=task_id,
            plugin_name=plugin_name,
            task_type=task_type.value,
            status=TaskStatus.PENDING,
            progress=0,
            records_processed=0,
            trade_dates=trade_dates or [],
            created_at=datetime.now(),
            user_id=user_id,
            username=username
        )

        # Also save to ClickHouse for history
        self._save_task_to_db(task)

        self.logger.info(f"Created task {task_id} in Redis queue for plugin {plugin_name}")
        return task
    
    def get_task(self, task_id: str) -> Optional[SyncTask]:
        """Get task by ID (Redis is the single source of truth).

        Mode A:
            If Redis is unavailable, raise to let API fail fast.
        """
        from stock_datasource.services.task_queue import task_queue

        task_data = task_queue.get_task(task_id)
        if not task_data:
            return None

        return self._task_data_to_sync_task(task_data)
    
    def get_all_tasks(self) -> List[SyncTask]:
        """Get all tasks."""
        return list(self._tasks.values())
    
    def get_tasks_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        plugin_name: Optional[str] = None,
        user_id: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> SyncTaskListResponse:
        """Get paginated tasks with filtering and sorting.
        
        Args:
            page: Page number (1-based)
            page_size: Items per page
            status: Filter by status
            plugin_name: Filter by plugin name (partial match)
            user_id: Filter by user ID (exact match)
            sort_by: Sort field (created_at, started_at, completed_at)
            sort_order: Sort order (asc, desc)
        
        Returns:
            Paginated task list response
        """
        tasks: List[SyncTask] = []

        # Prefer Redis-backed task list (single source of truth).
        try:
            from stock_datasource.services.task_queue import task_queue

            queue_tasks = task_queue.list_tasks(limit=5000)
            tasks = [self._task_data_to_sync_task(t) for t in queue_tasks]
        except Exception:
            # Fallback to in-memory list for backward compatibility (should be empty in new mode)
            tasks = list(self._tasks.values())
        
        # Filter by status
        if status:
            try:
                status_enum = TaskStatus(status)
                tasks = [t for t in tasks if t.status == status_enum]
            except ValueError:
                pass
        
        # Filter by plugin name (partial match)
        if plugin_name:
            plugin_name_lower = plugin_name.lower()
            tasks = [t for t in tasks if plugin_name_lower in t.plugin_name.lower()]
        
        # Filter by user_id (exact match)
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]
        
        # Sort
        reverse = sort_order.lower() == "desc"
        if sort_by == "started_at":
            tasks.sort(key=lambda t: t.started_at or datetime.min, reverse=reverse)
        elif sort_by == "completed_at":
            tasks.sort(key=lambda t: t.completed_at or datetime.min, reverse=reverse)
        else:  # created_at
            tasks.sort(key=lambda t: t.created_at or datetime.min, reverse=reverse)
        
        # Paginate
        total = len(tasks)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size
        items = tasks[start:end]
        
        return SyncTaskListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    def _task_data_to_sync_task(self, task_data: Dict[str, Any]) -> SyncTask:
        """Convert Redis task hash to SyncTask schema."""
        def _parse_dt(value: str) -> Optional[datetime]:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return None

        status_str = str(task_data.get("status", "pending"))
        try:
            status_enum = TaskStatus(status_str)
        except Exception:
            status_enum = TaskStatus.PENDING

        return SyncTask(
            task_id=str(task_data.get("task_id", "")),
            plugin_name=str(task_data.get("plugin_name", "")),
            task_type=str(task_data.get("task_type", "")),
            status=status_enum,
            progress=float(task_data.get("progress", 0)),
            records_processed=int(task_data.get("records_processed", 0)),
            trade_dates=task_data.get("trade_dates", []) or [],
            created_at=_parse_dt(str(task_data.get("created_at", ""))) or datetime.now(),
            started_at=_parse_dt(str(task_data.get("started_at", ""))),
            completed_at=_parse_dt(str(task_data.get("completed_at", ""))),
            error_message=str(task_data.get("error_message", "")),
            user_id=str(task_data.get("user_id", "")) or None,
            username=None,
        )
    
    def get_running_tasks(self) -> List[SyncTask]:
        """Get running tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.RUNNING]
    
    def get_pending_tasks(self) -> List[SyncTask]:
        """Get pending tasks."""
        return [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task.
        
        Args:
            task_id: Task ID
        
        Returns:
            True if cancelled, False otherwise
        """
        try:
            from stock_datasource.services.task_queue import task_queue, RedisUnavailableError

            success = task_queue.cancel_task(task_id)
            if not success:
                return False

            # Persist cancellation to ClickHouse (best-effort)
            try:
                task_data = task_queue.get_task(task_id)
                if task_data:
                    self._save_task_to_db(self._task_data_to_sync_task(task_data))
            except Exception:
                pass

            return True
        except RedisUnavailableError:
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task (any status except running).

        Redis is the single source of truth for real-time status.

        Mode A:
            If Redis is unavailable, raise to let API fail fast.
        """
        from stock_datasource.services.task_queue import task_queue

        task_data = task_queue.get_task(task_id)
        if not task_data:
            return False

        if str(task_data.get("status", "")) == TaskStatus.RUNNING.value:
            return False

        deleted = task_queue.delete_task(task_id)
        if not deleted:
            return False

        # Delete from ClickHouse history (best-effort)
        try:
            delete_sql = f"""
            ALTER TABLE {self.TASK_TABLE} DELETE 
            WHERE task_id = %(task_id)s
            """
            db_client.execute_query(delete_sql, {"task_id": task_id})
            self.logger.info(f"Deleted task {task_id} from database")
        except Exception as e:
            self.logger.error(f"Failed to delete task {task_id} from database: {e}")

        return True
    
    def retry_task(self, task_id: str) -> Optional[SyncTask]:
        """Retry a failed or cancelled task by creating a new task with same parameters.
        
        Args:
            task_id: Task ID of the failed/cancelled task
        
        Returns:
            New SyncTask if retry created, None if task not found or not retryable
        """
        try:
            from stock_datasource.services.task_queue import task_queue, RedisUnavailableError

            task_data = task_queue.get_task(task_id)
            if not task_data:
                self.logger.warning(f"Task {task_id} not found for retry")
                return None

            status = str(task_data.get("status", "pending"))
            if status not in {"failed", "cancelled"}:
                self.logger.warning(f"Task {task_id} is not retryable (status: {status})")
                return None

            plugin_name = str(task_data.get("plugin_name", ""))
            task_type = TaskType(str(task_data.get("task_type", "incremental")))
            trade_dates = task_data.get("trade_dates", [])

            # Manual retry => create NEW task_id (audit-friendly)
            self.logger.info(f"Retrying task {task_id} for plugin {plugin_name} (new task_id)")
            return self.create_task(
                plugin_name=plugin_name,
                task_type=task_type,
                trade_dates=trade_dates if trade_dates else None,
            )
        except RedisUnavailableError:
            return None
    
    def cleanup_old_tasks(self, days: int = 30):
        """Clean up tasks older than specified days.
        
        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        # Clean up from database
        try:
            delete_sql = f"""
            ALTER TABLE {self.TASK_TABLE} DELETE 
            WHERE completed_at < %(cutoff)s
            """
            db_client.execute_query(delete_sql, {"cutoff": cutoff.strftime('%Y-%m-%d %H:%M:%S')})
            self.logger.info(f"Cleaned up tasks older than {days} days from database")
        except Exception as e:
            self.logger.error(f"Failed to cleanup old tasks from database: {e}")
        
        # Clean up from memory
        with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.completed_at and task.completed_at < cutoff:
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._tasks[task_id]
        
        if to_remove:
            self.logger.info(f"Cleaned up {len(to_remove)} old tasks from memory")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current sync configuration.
        
        Returns:
            Dict with current configuration
        """
        with self._lock:
            return {
                "max_concurrent_tasks": self._max_concurrent_tasks,
                "max_date_threads": self._max_date_threads,
                "running_tasks_count": len(self._running_tasks),
                "pending_tasks_count": len(self._task_queue),
                "running_plugins": list(self._running_tasks.values())
            }
    
    def get_concurrency_info(self) -> Dict[str, Any]:
        """Get current concurrency configuration and status.
        
        Returns:
            Dict with concurrency info
        """
        return self.get_config()
    
    def get_task_history(self, days: int = 7, limit: int = 100) -> List[SyncHistory]:
        """Get task history from database.
        
        Args:
            days: Number of days to look back
            limit: Maximum number of records to return
        
        Returns:
            List of SyncHistory records
        """
        try:
            # Use subquery with FINAL to get deduplicated data
            cutoff_time = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
            query = f"""
            SELECT 
                task_id, plugin_name, task_type, status,
                records_processed, error_message,
                formatDateTime(started_at, '%Y-%m-%d %H:%i:%S') as started_at_str,
                formatDateTime(completed_at, '%Y-%m-%d %H:%i:%S') as completed_at_str,
                user_id, username
            FROM (
                SELECT * FROM {self.TASK_TABLE} FINAL
                WHERE created_at >= toDateTime('{cutoff_time}')
            )
            ORDER BY created_at DESC
            LIMIT {limit}
            """
            result = db_client.execute_query(query)
            
            if result.empty:
                return []
            
            def parse_dt(val):
                if val and val != '' and val != 'None' and str(val) != '1970-01-01 00:00:00':
                    try:
                        return datetime.strptime(str(val)[:19], '%Y-%m-%d %H:%M:%S')
                    except:
                        return None
                return None
            
            history = []
            for _, row in result.iterrows():
                started_at = parse_dt(row['started_at_str'])
                completed_at = parse_dt(row['completed_at_str'])
                
                # Calculate duration
                duration = None
                if started_at and completed_at:
                    duration = (completed_at - started_at).total_seconds()
                
                history.append(SyncHistory(
                    task_id=row['task_id'],
                    plugin_name=row['plugin_name'],
                    task_type=row['task_type'],
                    status=row['status'],
                    records_processed=int(row['records_processed']),
                    error_message=row['error_message'] if row['error_message'] else None,
                    started_at=started_at if started_at else datetime.now(),
                    completed_at=completed_at,
                    duration_seconds=duration,
                    user_id=row.get('user_id') if row.get('user_id') else None,
                    username=row.get('username') if row.get('username') else None
                ))
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get task history: {e}")
            return []


class DiagnosisService:
    """Service for AI-powered log diagnosis and suggestions."""
    
    # Known error patterns and their solutions
    ERROR_PATTERNS = {
        "TUSHARE_TOKEN environment variable not set": {
            "severity": "critical",
            "category": "config",
            "title": "TuShare Token未配置",
            "description": "系统无法加载TuShare相关插件，因为未设置TUSHARE_TOKEN环境变量",
            "suggestion": "请在.env文件中添加 TUSHARE_TOKEN=your_token，或设置环境变量 export TUSHARE_TOKEN=your_token"
        },
        "No trading days found in calendar": {
            "severity": "critical",
            "category": "data",
            "title": "交易日历数据为空",
            "description": "ods_trade_calendar表中没有数据，导致无法进行数据缺失检测",
            "suggestion": "请先运行交易日历插件同步数据：执行 tushare_trade_calendar 插件的同步任务"
        },
        "No trading days available for detection": {
            "severity": "warning",
            "category": "data",
            "title": "无法获取交易日数据",
            "description": "数据缺失检测无法执行，因为没有可用的交易日数据",
            "suggestion": "请确保交易日历表(ods_trade_calendar)中有数据，并检查exchange参数是否正确"
        },
        "symbol is required": {
            "severity": "warning",
            "category": "plugin",
            "title": "插件参数缺失",
            "description": "akshare_hk_daily插件需要symbol参数才能执行",
            "suggestion": "该插件需要指定股票代码(symbol)参数，请在同步时提供具体的股票代码"
        },
        "Database initialization timed out": {
            "severity": "critical",
            "category": "connection",
            "title": "数据库初始化超时",
            "description": "ClickHouse数据库连接超时，可能是服务未启动或网络问题",
            "suggestion": "请检查ClickHouse服务状态：systemctl status clickhouse-server，并确认连接配置正确"
        },
        "Query execution failed: timed out": {
            "severity": "warning",
            "category": "connection",
            "title": "查询执行超时",
            "description": "数据库查询超时，可能是查询过于复杂或数据库负载过高",
            "suggestion": "请检查数据库性能，考虑优化查询或增加超时时间"
        },
        "Unknown table expression identifier": {
            "severity": "critical",
            "category": "data",
            "title": "数据表不存在",
            "description": "查询的数据表不存在，可能是表未创建或表名错误",
            "suggestion": "请检查表是否已创建，可以运行数据库初始化脚本创建所需的表"
        },
        "Connection refused": {
            "severity": "critical",
            "category": "connection",
            "title": "连接被拒绝",
            "description": "无法连接到数据库或外部API服务",
            "suggestion": "请检查服务是否启动，网络是否可达，防火墙是否允许连接"
        },
        "Rate limit exceeded": {
            "severity": "warning",
            "category": "plugin",
            "title": "API请求频率超限",
            "description": "数据源API请求频率超过限制",
            "suggestion": "请降低请求频率，或等待一段时间后重试。可以在插件config.json中调整rate_limit参数"
        },
        "NumPy support is not implemented for Decimal": {
            "severity": "info",
            "category": "system",
            "title": "数据类型兼容性警告",
            "description": "ClickHouse的Decimal类型与NumPy不完全兼容",
            "suggestion": "这是一个已知的兼容性问题，不影响功能，可以忽略"
        }
    }
    
    def __init__(self):
        self.logger = logger.bind(component="DiagnosisService")
    
    def read_logs(self, lines: int = 100, errors_only: bool = False) -> List[str]:
        """Read recent log lines.
        
        Args:
            lines: Number of lines to read
            errors_only: Only return error/warning lines
        
        Returns:
            List of log lines
        """
        log_file = settings.LOGS_DIR / "stock_datasource.log"
        
        if not log_file.exists():
            self.logger.warning(f"Log file not found: {log_file}")
            return []
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            # Get last N lines
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            
            if errors_only:
                # Filter for ERROR and WARNING lines
                recent_lines = [
                    line for line in recent_lines 
                    if 'ERROR' in line or 'WARNING' in line
                ]
            
            return [line.strip() for line in recent_lines if line.strip()]
            
        except Exception as e:
            self.logger.error(f"Failed to read logs: {e}")
            return []
    
    def analyze_logs(self, log_lines: List[str]) -> Dict[str, Any]:
        """Analyze log lines for errors and patterns.
        
        Args:
            log_lines: List of log lines to analyze
        
        Returns:
            Analysis results
        """
        errors = []
        warnings = []
        matched_patterns = []
        
        for line in log_lines:
            if 'ERROR' in line:
                errors.append(line)
            elif 'WARNING' in line:
                warnings.append(line)
            
            # Check against known patterns
            for pattern, info in self.ERROR_PATTERNS.items():
                if pattern in line:
                    if pattern not in [m['pattern'] for m in matched_patterns]:
                        matched_patterns.append({
                            'pattern': pattern,
                            'info': info,
                            'example_log': line
                        })
        
        return {
            'errors': errors,
            'warnings': warnings,
            'matched_patterns': matched_patterns,
            'error_count': len(errors),
            'warning_count': len(warnings)
        }
    
    def generate_suggestions(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate suggestions based on log analysis.
        
        Args:
            analysis: Log analysis results
        
        Returns:
            List of suggestions
        """
        suggestions = []
        
        # Add suggestions from matched patterns
        for match in analysis['matched_patterns']:
            info = match['info']
            suggestions.append({
                'severity': info['severity'],
                'category': info['category'],
                'title': info['title'],
                'description': info['description'],
                'suggestion': info['suggestion'],
                'related_logs': [match['example_log']]
            })
        
        # Add generic suggestions for unmatched errors
        unmatched_errors = []
        for error in analysis['errors']:
            is_matched = any(
                pattern in error 
                for pattern in self.ERROR_PATTERNS.keys()
            )
            if not is_matched:
                unmatched_errors.append(error)
        
        if unmatched_errors:
            suggestions.append({
                'severity': 'warning',
                'category': 'system',
                'title': '其他错误',
                'description': f'发现 {len(unmatched_errors)} 个未分类的错误',
                'suggestion': '请检查以下错误日志，确定具体问题原因',
                'related_logs': unmatched_errors[:5]  # Limit to 5
            })
        
        # Sort by severity
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        suggestions.sort(key=lambda x: severity_order.get(x['severity'], 3))
        
        return suggestions
    
    def generate_summary(self, analysis: Dict[str, Any], suggestions: List[Dict[str, Any]]) -> str:
        """Generate a summary of the diagnosis.
        
        Args:
            analysis: Log analysis results
            suggestions: List of suggestions
        
        Returns:
            Summary string
        """
        critical_count = sum(1 for s in suggestions if s['severity'] == 'critical')
        warning_count = sum(1 for s in suggestions if s['severity'] == 'warning')
        
        if critical_count > 0:
            return f"发现 {critical_count} 个严重问题需要立即处理，{warning_count} 个警告需要关注"
        elif warning_count > 0:
            return f"系统运行基本正常，但有 {warning_count} 个警告需要关注"
        elif analysis['error_count'] > 0:
            return f"发现 {analysis['error_count']} 个错误，但未匹配到已知问题模式，请检查详细日志"
        else:
            return "系统运行正常，未发现明显问题"
    
    def diagnose(self, lines: int = 100, errors_only: bool = False, context: Optional[str] = None) -> Dict[str, Any]:
        """Perform full diagnosis.
        
        Args:
            lines: Number of log lines to analyze
            errors_only: Only analyze error/warning logs
            context: Additional context for diagnosis
        
        Returns:
            Diagnosis result
        """
        from .schemas import DiagnosisResult, DiagnosisSuggestion
        
        # Read logs
        log_lines = self.read_logs(lines, errors_only)
        
        # Analyze
        analysis = self.analyze_logs(log_lines)
        
        # Generate suggestions
        suggestions = self.generate_suggestions(analysis)
        
        # Generate summary
        summary = self.generate_summary(analysis, suggestions)
        
        # Build result
        suggestion_models = [
            DiagnosisSuggestion(
                severity=s['severity'],
                category=s['category'],
                title=s['title'],
                description=s['description'],
                suggestion=s['suggestion'],
                related_logs=s.get('related_logs', [])
            )
            for s in suggestions
        ]
        
        return DiagnosisResult(
            diagnosis_time=datetime.now(),
            log_lines_analyzed=len(log_lines),
            error_count=analysis['error_count'],
            warning_count=analysis['warning_count'],
            summary=summary,
            suggestions=suggestion_models,
            raw_errors=analysis['errors'][:20]  # Limit raw errors
        )


# Global service instances
data_manage_service = DataManageService()
sync_task_manager = SyncTaskManager()
diagnosis_service = DiagnosisService()
