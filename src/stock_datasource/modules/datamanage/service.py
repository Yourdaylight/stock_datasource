"""Data management service layer."""

import asyncio
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import threading
from collections import deque

from stock_datasource.utils.logger import logger
from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client
from stock_datasource.config.settings import settings

from .schemas import (
    SyncTask, TaskStatus, TaskType,
    PluginInfo, PluginDetail, PluginConfig, PluginSchema, PluginColumn,
    PluginStatus, PluginSchedule, ScheduleFrequency,
    PluginDataPreview, MissingDataInfo, MissingDataSummary,
    SyncHistory
)


class DataManageService:
    """Service for data management operations."""
    
    def __init__(self):
        self.logger = logger.bind(component="DataManageService")
        self._missing_data_cache: Optional[MissingDataSummary] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl = 3600  # 1 hour cache
    
    def get_trading_days(self, days: int = 30, exchange: str = "SSE") -> List[str]:
        """Get recent trading days from trade calendar.
        
        Args:
            days: Number of trading days to retrieve
            exchange: Exchange code (default: SSE for Shanghai)
        
        Returns:
            List of trading dates in YYYY-MM-DD format
        """
        try:
            query = """
            SELECT cal_date 
            FROM ods_trade_calendar 
            WHERE is_open = 1 
            AND exchange = %(exchange)s
            AND cal_date <= today() 
            ORDER BY cal_date DESC 
            LIMIT %(limit)s
            """
            result = db_client.execute_query(query, {"exchange": exchange, "limit": days})
            
            if result.empty:
                self.logger.warning("No trading days found in calendar")
                return []
            
            # Convert to string format
            dates = result['cal_date'].tolist()
            return [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d) for d in dates]
            
        except Exception as e:
            self.logger.error(f"Failed to get trading days: {e}")
            return []
    
    def check_data_exists(self, table_name: str, date_column: str, trade_date: str) -> bool:
        """Check if data exists for a specific date in a table.
        
        Args:
            table_name: Name of the ODS table
            date_column: Name of the date column
            trade_date: Date to check (YYYY-MM-DD format)
        
        Returns:
            True if data exists, False otherwise
        """
        try:
            query = f"""
            SELECT count() as cnt
            FROM {table_name}
            WHERE {date_column} = %(trade_date)s
            """
            result = db_client.execute_query(query, {"trade_date": trade_date})
            
            if result.empty:
                return False
            
            return result['cnt'].iloc[0] > 0
            
        except Exception as e:
            self.logger.warning(f"Failed to check data in {table_name} for {trade_date}: {e}")
            return False
    
    def get_table_latest_date(self, table_name: str, date_column: str) -> Optional[str]:
        """Get the latest date in a table.
        
        Args:
            table_name: Name of the ODS table
            date_column: Name of the date column
        
        Returns:
            Latest date string or None
        """
        try:
            query = f"""
            SELECT max({date_column}) as latest_date
            FROM {table_name}
            """
            result = db_client.execute_query(query)
            
            if result.empty or result['latest_date'].iloc[0] is None:
                return None
            
            latest = result['latest_date'].iloc[0]
            return latest.strftime('%Y-%m-%d') if hasattr(latest, 'strftime') else str(latest)
            
        except Exception as e:
            self.logger.warning(f"Failed to get latest date from {table_name}: {e}")
            return None
    
    def get_table_record_count(self, table_name: str) -> int:
        """Get total record count in a table.
        
        Args:
            table_name: Name of the table
        
        Returns:
            Record count
        """
        try:
            query = f"SELECT count() as cnt FROM {table_name}"
            result = db_client.execute_query(query)
            
            if result.empty:
                return 0
            
            return int(result['cnt'].iloc[0])
            
        except Exception as e:
            self.logger.warning(f"Failed to get record count from {table_name}: {e}")
            return 0
    
    def _get_plugin_date_column(self, plugin_name: str) -> str:
        """Get the date column name for a plugin's table.
        
        Args:
            plugin_name: Plugin name
        
        Returns:
            Date column name
        """
        # Most plugins use trade_date, some use cal_date
        date_column_map = {
            "tushare_trade_calendar": "cal_date",
            "tushare_stock_basic": "list_date",
            "akshare_hk_stock_list": "list_date",
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
        # Check cache
        if not force_refresh and self._missing_data_cache:
            if self._cache_time and (datetime.now() - self._cache_time).seconds < self._cache_ttl:
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
        
        summary = MissingDataSummary(
            check_time=datetime.now(),
            total_plugins=len(plugins_info),
            plugins_with_missing=plugins_with_missing,
            plugins=plugins_info
        )
        
        # Update cache
        self._missing_data_cache = summary
        self._cache_time = datetime.now()
        
        self.logger.info(f"Missing data detection complete: {plugins_with_missing}/{len(plugins_info)} plugins have missing data")
        return summary
    
    def get_plugin_list(self) -> List[PluginInfo]:
        """Get list of all plugins with status info.
        
        Returns:
            List of plugin info
        """
        plugins: List[PluginInfo] = []
        
        for plugin_name in plugin_manager.list_plugins():
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                continue
            
            # Get schedule
            schedule = plugin.get_schedule()
            frequency = schedule.get("frequency", "daily")
            time = schedule.get("time", "18:00")
            
            # Get schema for table name
            schema = plugin.get_schema()
            table_name = schema.get("table_name", f"ods_{plugin_name}")
            date_column = self._get_plugin_date_column(plugin_name)
            
            # Get status
            latest_date = self.get_table_latest_date(table_name, date_column)
            
            # Calculate missing count (simple check against today)
            missing_count = 0
            if frequency == "daily" and latest_date:
                # Check if latest date is today
                today = date.today().strftime('%Y-%m-%d')
                if latest_date < today:
                    # Count trading days between latest and today
                    trading_days = self.get_trading_days(30)
                    for td in trading_days:
                        if td > latest_date:
                            missing_count += 1
                        else:
                            break
            
            info = PluginInfo(
                name=plugin_name,
                version=plugin.version,
                description=plugin.description,
                type="data_source",
                is_enabled=plugin.is_enabled(),
                schedule_frequency=frequency,
                schedule_time=time,
                latest_date=latest_date,
                missing_count=missing_count,
                last_run_at=None,  # TODO: Get from task history
                last_run_status=None
            )
            plugins.append(info)
        
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
        
        # Get missing dates for daily plugins
        missing_dates = []
        if schedule.frequency == ScheduleFrequency.DAILY:
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
        
        if trade_date:
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
        else:
            query = f"""
            SELECT * FROM {table_name}
            ORDER BY {date_column} DESC
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
        
        # Get missing dates for daily plugins
        schedule = plugin.get_schedule()
        missing_dates = []
        
        if schedule.get("frequency") == "daily":
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
            # Use batch query for efficiency - group by date and count
            # Convert dates to proper format for ClickHouse
            dates_str = ", ".join([f"'{d}'" for d in dates])
            
            query = f"""
            SELECT toString({date_column}) as check_date, count() as cnt
            FROM {table_name}
            WHERE {date_column} IN ({dates_str})
            GROUP BY {date_column}
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
                    count = int(row['cnt'])
                    if count > 0:
                        existing_set.add(check_date)
                        record_counts[check_date] = count
            
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


class SyncTaskManager:
    """Manager for sync tasks with serial execution."""
    
    def __init__(self):
        self.logger = logger.bind(component="SyncTaskManager")
        self._tasks: Dict[str, SyncTask] = {}
        self._task_queue: deque = deque()
        self._current_task: Optional[str] = None
        self._lock = threading.Lock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the task worker thread."""
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self.logger.info("SyncTaskManager started")
    
    def stop(self):
        """Stop the task worker thread."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self.logger.info("SyncTaskManager stopped")
    
    def _worker_loop(self):
        """Worker loop for processing tasks."""
        while self._running:
            task_id = None
            
            with self._lock:
                if self._task_queue and not self._current_task:
                    task_id = self._task_queue.popleft()
                    self._current_task = task_id
            
            if task_id:
                self._execute_task(task_id)
                with self._lock:
                    self._current_task = None
            else:
                # Sleep briefly when no tasks
                import time
                time.sleep(1)
    
    def _execute_task(self, task_id: str):
        """Execute a single task."""
        task = self._tasks.get(task_id)
        if not task:
            return
        
        # Update status to running
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        self.logger.info(f"Executing task {task_id} for plugin {task.plugin_name}")
        
        try:
            plugin = plugin_manager.get_plugin(task.plugin_name)
            if not plugin:
                raise ValueError(f"Plugin {task.plugin_name} not found")
            
            # Execute based on task type
            if task.task_type == TaskType.BACKFILL.value and task.trade_dates:
                # Backfill specific dates
                total = len(task.trade_dates)
                task.total_records = total
                
                for i, trade_date in enumerate(task.trade_dates):
                    result = plugin.run(trade_date=trade_date)
                    
                    if result.get("status") == "success":
                        task.records_processed += result.get("steps", {}).get("load", {}).get("total_records", 0)
                    
                    task.progress = ((i + 1) / total) * 100
            else:
                # Incremental or full sync (use today's date)
                today = date.today().strftime('%Y%m%d')
                result = plugin.run(trade_date=today)
                
                if result.get("status") == "success":
                    task.records_processed = result.get("steps", {}).get("load", {}).get("total_records", 0)
                    task.progress = 100
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            self.logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self.logger.error(f"Task {task_id} failed: {e}")
    
    def create_task(
        self, 
        plugin_name: str, 
        task_type: TaskType = TaskType.INCREMENTAL,
        trade_dates: Optional[List[str]] = None
    ) -> SyncTask:
        """Create a new sync task.
        
        Args:
            plugin_name: Plugin name
            task_type: Task type
            trade_dates: List of dates for backfill
        
        Returns:
            Created task
        """
        task_id = str(uuid.uuid4())
        
        task = SyncTask(
            task_id=task_id,
            plugin_name=plugin_name,
            task_type=task_type.value,
            status=TaskStatus.PENDING,
            progress=0,
            records_processed=0,
            trade_dates=trade_dates or [],
            created_at=datetime.now()
        )
        
        with self._lock:
            self._tasks[task_id] = task
            self._task_queue.append(task_id)
        
        self.logger.info(f"Created task {task_id} for plugin {plugin_name}")
        return task
    
    def get_task(self, task_id: str) -> Optional[SyncTask]:
        """Get task by ID."""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SyncTask]:
        """Get all tasks."""
        return list(self._tasks.values())
    
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
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                if task_id in self._task_queue:
                    self._task_queue.remove(task_id)
                return True
        return False
    
    def cleanup_old_tasks(self, days: int = 30):
        """Clean up tasks older than specified days.
        
        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        with self._lock:
            to_remove = []
            for task_id, task in self._tasks.items():
                if task.completed_at and task.completed_at < cutoff:
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._tasks[task_id]
        
        if to_remove:
            self.logger.info(f"Cleaned up {len(to_remove)} old tasks")


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
