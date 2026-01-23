"""Schedule service for managing scheduled sync tasks.

Provides functionality to:
- Configure global schedule settings
- Configure per-plugin schedule settings
- Execute scheduled syncs based on dependency order
- Track execution history
"""

import logging
import threading
import uuid
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional

from ...config.runtime_config import (
    get_schedule_config,
    get_plugin_schedule_config,
    save_runtime_config,
    save_plugin_schedule_config,
    get_schedule_history,
    add_schedule_execution,
    update_schedule_execution,
)
from ...core.plugin_manager import plugin_manager
from ...core.trade_calendar import TradeCalendarService
from ...core.base_plugin import PluginCategory, PluginRole, CATEGORY_LABELS

logger = logging.getLogger(__name__)


class ScheduleService:
    """Service for managing scheduled sync tasks."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._executor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        logger.info("ScheduleService initialized")
        # Check for interrupted executions on startup
        self._mark_interrupted_executions()
    
    def _mark_interrupted_executions(self):
        """Mark any running executions as interrupted on service startup.
        
        This handles the case where the service was restarted while executions
        were in progress. These executions need manual intervention to retry.
        Only marks as interrupted if there are actually unfinished tasks.
        """
        from datetime import datetime
        from .service import sync_task_manager
        
        history = get_schedule_history(limit=100)
        interrupted_count = 0
        
        for record in history:
            if record.get("status") in ("running", "stopping"):
                execution_id = record.get("execution_id")
                task_ids = record.get("task_ids", [])
                
                # Check if there are actually unfinished tasks
                has_unfinished = False
                completed = 0
                failed = 0
                
                for task_id in task_ids:
                    task = sync_task_manager.get_task(task_id)
                    if task:
                        status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
                        if status_val == "completed":
                            completed += 1
                        elif status_val == "failed":
                            failed += 1
                        elif status_val in ("pending", "running"):
                            has_unfinished = True
                
                if has_unfinished:
                    # Has unfinished tasks - mark as interrupted
                    update_schedule_execution(execution_id, {
                        "status": "interrupted",
                        "skip_reason": "服务重启，任务中断",
                        "completed_at": datetime.now().isoformat(),
                        "completed_plugins": completed,
                        "failed_plugins": failed,
                    })
                    interrupted_count += 1
                    logger.warning(f"Marked execution {execution_id} as interrupted due to service restart")
                else:
                    # All tasks finished - update to final status
                    final_status = "failed" if failed > 0 else "completed"
                    update_schedule_execution(execution_id, {
                        "status": final_status,
                        "completed_at": datetime.now().isoformat(),
                        "completed_plugins": completed,
                        "failed_plugins": failed,
                    })
                    logger.info(f"Marked execution {execution_id} as {final_status} (all tasks finished)")
        
        if interrupted_count > 0:
            logger.info(f"Marked {interrupted_count} executions as interrupted")
    
    # ============ Global Schedule Config ============
    
    def get_config(self) -> Dict[str, Any]:
        """Get global schedule configuration."""
        config = get_schedule_config()
        
        # Calculate next_run_at based on current config
        if config.get("enabled"):
            config["next_run_at"] = self._calculate_next_run_time(config)
        
        return config
    
    def update_config(
        self,
        enabled: Optional[bool] = None,
        execute_time: Optional[str] = None,
        frequency: Optional[str] = None,
        include_optional_deps: Optional[bool] = None,
        skip_non_trading_days: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update global schedule configuration."""
        updates = {}
        
        if enabled is not None:
            updates["enabled"] = enabled
        if execute_time is not None:
            updates["execute_time"] = execute_time
            # Update cron expression based on time and frequency
            current_config = get_schedule_config()
            freq = frequency or current_config.get("frequency", "weekday")
            updates["cron_expression"] = self._build_cron_expression(execute_time, freq)
        if frequency is not None:
            updates["frequency"] = frequency
            # Update cron expression
            current_config = get_schedule_config()
            exec_time = execute_time or current_config.get("execute_time", "18:00")
            updates["cron_expression"] = self._build_cron_expression(exec_time, frequency)
        if include_optional_deps is not None:
            updates["include_optional_deps"] = include_optional_deps
        if skip_non_trading_days is not None:
            updates["skip_non_trading_days"] = skip_non_trading_days
        
        if updates:
            save_runtime_config(schedule=updates)
            logger.info(f"Schedule config updated: {updates}")
        
        return self.get_config()
    
    def _build_cron_expression(self, execute_time: str, frequency: str) -> str:
        """Build cron expression from time and frequency."""
        hour, minute = execute_time.split(":")
        if frequency == "daily":
            return f"{minute} {hour} * * *"
        else:  # weekday
            return f"{minute} {hour} * * 1-5"
    
    def _calculate_next_run_time(self, config: Dict[str, Any]) -> Optional[str]:
        """Calculate next scheduled run time."""
        try:
            execute_time = config.get("execute_time", "18:00")
            frequency = config.get("frequency", "weekday")
            skip_non_trading = config.get("skip_non_trading_days", True)
            
            hour, minute = map(int, execute_time.split(":"))
            target_time = time(hour, minute)
            
            now = datetime.now()
            today_run = datetime.combine(now.date(), target_time)
            
            # If today's time has passed, start from tomorrow
            if now >= today_run:
                next_date = now.date() + timedelta(days=1)
            else:
                next_date = now.date()
            
            # Find next valid run date
            for _ in range(30):  # Look ahead up to 30 days
                next_run = datetime.combine(next_date, target_time)
                
                # Check frequency
                if frequency == "weekday" and next_date.weekday() >= 5:
                    next_date += timedelta(days=1)
                    continue
                
                # Check trading day if enabled
                if skip_non_trading:
                    try:
                        calendar = TradeCalendarService()
                        if not calendar.is_trading_day(next_date):
                            next_date += timedelta(days=1)
                            continue
                    except Exception:
                        pass  # Skip trading day check if calendar unavailable
                
                return next_run.isoformat()
            
            return None
        except Exception as e:
            logger.warning(f"Failed to calculate next run time: {e}")
            return None
    
    # ============ Plugin Schedule Config ============
    
    def get_plugin_configs(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get schedule configuration for all plugins."""
        plugins = plugin_manager.list_plugins()
        result = []
        
        for plugin_name in plugins:
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                continue
            
            # Get plugin category
            try:
                plugin_category = plugin.get_category().value
            except Exception:
                plugin_category = "cn_stock"
            
            # Filter by category if specified
            if category and plugin_category != category:
                continue
            
            # Get plugin role
            try:
                plugin_role = plugin.get_role().value
            except Exception:
                plugin_role = "primary"
            
            # Get dependencies
            try:
                deps = plugin.get_dependencies()
            except Exception:
                deps = []
            
            try:
                opt_deps = plugin.get_optional_dependencies()
            except Exception:
                opt_deps = []
            
            # Get saved schedule config
            saved_config = get_plugin_schedule_config(plugin_name)
            
            result.append({
                "plugin_name": plugin_name,
                "schedule_enabled": saved_config.get("schedule_enabled", True),
                "full_scan_enabled": saved_config.get("full_scan_enabled", False),
                "category": plugin_category,
                "category_label": CATEGORY_LABELS.get(plugin_category, plugin_category),
                "role": plugin_role,
                "dependencies": deps,
                "optional_dependencies": opt_deps,
            })
        
        # Sort by role (basic first, then primary, then derived/auxiliary)
        role_order = {"basic": 0, "primary": 1, "derived": 2, "auxiliary": 3}
        result.sort(key=lambda x: (role_order.get(x["role"], 4), x["plugin_name"]))
        
        return result
    
    def update_plugin_config(
        self,
        plugin_name: str,
        schedule_enabled: Optional[bool] = None,
        full_scan_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update schedule configuration for a single plugin."""
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            raise ValueError(f"Plugin {plugin_name} not found")
        
        save_plugin_schedule_config(plugin_name, schedule_enabled, full_scan_enabled)
        
        # Return updated config
        configs = self.get_plugin_configs()
        for cfg in configs:
            if cfg["plugin_name"] == plugin_name:
                return cfg
        
        raise ValueError(f"Failed to get updated config for {plugin_name}")
    
    # ============ Schedule Execution ============
    
    def trigger_now(self, is_manual: bool = True) -> Dict[str, Any]:
        """Trigger schedule execution immediately.
        
        Returns:
            ScheduleExecutionRecord dict
        """
        from .service import sync_task_manager
        
        execution_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()
        
        record = {
            "execution_id": execution_id,
            "trigger_type": "manual" if is_manual else "scheduled",
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "status": "running",
            "skip_reason": None,
            "total_plugins": 0,
            "completed_plugins": 0,
            "failed_plugins": 0,
            "task_ids": [],
        }
        
        config = self.get_config()
        
        # Check if we should skip (non-trading day) - only for scheduled triggers
        # Manual triggers should always proceed, but use the latest trading day
        if not is_manual and config.get("skip_non_trading_days", True):
            try:
                calendar = TradeCalendarService()
                if not calendar.is_trading_day(datetime.now().date()):
                    record["status"] = "skipped"
                    record["skip_reason"] = "非交易日"
                    record["completed_at"] = datetime.now().isoformat()
                    add_schedule_execution(record)
                    logger.info(f"Schedule {execution_id} skipped: non-trading day")
                    return record
            except Exception as e:
                logger.warning(f"Failed to check trading day: {e}")
        
        # Add to history
        add_schedule_execution(record)
        
        # Get enabled plugins and sort by dependency order
        plugin_configs = self.get_plugin_configs()
        enabled_plugins = [p for p in plugin_configs if p["schedule_enabled"]]
        
        if not enabled_plugins:
            record["status"] = "completed"
            record["completed_at"] = datetime.now().isoformat()
            update_schedule_execution(execution_id, record)
            logger.info(f"Schedule {execution_id} completed: no enabled plugins")
            return record
        
        # Sort by dependency order using plugin_manager
        plugin_names = [p["plugin_name"] for p in enabled_plugins]
        include_optional = config.get("include_optional_deps", True)
        
        try:
            sorted_tasks = plugin_manager.batch_trigger_sync(
                plugin_names=plugin_names,
                task_type="incremental",
                include_optional=include_optional
            )
            execution_order = [t["plugin_name"] for t in sorted_tasks]
        except Exception as e:
            logger.error(f"Failed to sort plugins: {e}")
            execution_order = plugin_names
        
        record["total_plugins"] = len(execution_order)
        update_schedule_execution(execution_id, {"total_plugins": len(execution_order)})
        
        # Create sync tasks
        task_ids = []
        from .schemas import TaskType
        
        for plugin_name in execution_order:
            # Get plugin config for full_scan setting
            plugin_cfg = next((p for p in enabled_plugins if p["plugin_name"] == plugin_name), None)
            task_type = TaskType.FULL if plugin_cfg and plugin_cfg.get("full_scan_enabled") else TaskType.INCREMENTAL
            
            try:
                task = sync_task_manager.create_task(
                    plugin_name=plugin_name,
                    task_type=task_type,
                    trade_dates=None,
                    user_id="system",
                    username="scheduler",
                )
                task_ids.append(task.task_id)
                logger.info(f"Created task {task.task_id} for {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to create task for {plugin_name}: {e}")
                record["failed_plugins"] += 1
        
        record["task_ids"] = task_ids
        record["status"] = "running"
        
        # Update last_run_at
        save_runtime_config(schedule={"last_run_at": started_at.isoformat()})
        
        update_schedule_execution(execution_id, {
            "task_ids": task_ids,
            "total_plugins": len(execution_order),
        })
        
        logger.info(f"Schedule {execution_id} started with {len(task_ids)} tasks")
        return record
    
    def get_history(self, days: int = 7, limit: int = 50) -> List[Dict[str, Any]]:
        """Get schedule execution history."""
        history = get_schedule_history(limit=limit)
        
        # Update running executions status
        for record in history:
            if record.get("status") == "running":
                self.update_execution_status(record.get("execution_id"))
        
        # Re-fetch history after updates
        history = get_schedule_history(limit=limit)
        
        # Filter by days
        if days > 0:
            cutoff = datetime.now() - timedelta(days=days)
            filtered = []
            for record in history:
                try:
                    started = datetime.fromisoformat(record.get("started_at", ""))
                    if started >= cutoff:
                        filtered.append(record)
                except Exception:
                    filtered.append(record)
            history = filtered
        
        # Add can_retry flag for interrupted/failed executions
        for record in history:
            status = record.get("status", "")
            # Can retry if interrupted or failed
            record["can_retry"] = status in ("interrupted", "failed")
        
        return history[:limit]
    
    def retry_execution(self, execution_id: str) -> Dict[str, Any]:
        """Retry a failed or interrupted execution.
        
        Creates a new execution with the same configuration as the original.
        
        Args:
            execution_id: The ID of the execution to retry
            
        Returns:
            New ScheduleExecutionRecord dict
            
        Raises:
            ValueError: If execution not found or cannot be retried
        """
        # Find the original execution
        history = get_schedule_history(limit=100)
        original = None
        for r in history:
            if r.get("execution_id") == execution_id:
                original = r
                break
        
        if not original:
            raise ValueError(f"Execution {execution_id} not found")
        
        status = original.get("status", "")
        if status not in ("interrupted", "failed"):
            raise ValueError(f"Execution {execution_id} cannot be retried (status: {status})")
        
        # Trigger a new execution
        logger.info(f"Retrying execution {execution_id}")
        return self.trigger_now(is_manual=True)
    
    def update_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Update execution status by checking task statuses."""
        from .service import sync_task_manager
        
        history = get_schedule_history(limit=100)
        record = None
        for r in history:
            if r.get("execution_id") == execution_id:
                record = r
                break
        
        if not record or record.get("status") not in ("running", "stopping"):
            return record
        
        task_ids = record.get("task_ids", [])
        if not task_ids:
            record["status"] = "completed"
            record["completed_at"] = datetime.now().isoformat()
            update_schedule_execution(execution_id, record)
            return record
        
        # Check task statuses
        completed = 0
        failed = 0
        cancelled = 0
        running = 0
        
        for task_id in task_ids:
            task = sync_task_manager.get_task(task_id)
            if task:
                status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
                if status_val == "completed":
                    completed += 1
                elif status_val == "failed":
                    failed += 1
                elif status_val == "cancelled":
                    cancelled += 1
                elif status_val in ("pending", "running"):
                    running += 1
        
        record["completed_plugins"] = completed
        record["failed_plugins"] = failed
        
        if running == 0:
            # All tasks finished - determine final status
            if record.get("status") == "stopping":
                # Was manually stopped
                record["status"] = "stopped"
            elif failed > 0:
                record["status"] = "failed"
            else:
                record["status"] = "completed"
            record["completed_at"] = datetime.now().isoformat()
        
        update_schedule_execution(execution_id, record)
        return record
    
    def stop_execution(self, execution_id: str) -> Dict[str, Any]:
        """Stop a running execution by cancelling pending tasks.
        
        Args:
            execution_id: The execution ID to stop
            
        Returns:
            Updated execution record
            
        Raises:
            ValueError: If execution not found or not running
        """
        from .service import sync_task_manager
        
        history = get_schedule_history(limit=100)
        record = None
        for r in history:
            if r.get("execution_id") == execution_id:
                record = r
                break
        
        if not record:
            raise ValueError(f"Execution {execution_id} not found")
        
        if record.get("status") != "running":
            raise ValueError(f"Execution {execution_id} is not running (status: {record.get('status')})")
        
        # Cancel pending tasks
        task_ids = record.get("task_ids", [])
        cancelled_count = 0
        
        for task_id in task_ids:
            task = sync_task_manager.get_task(task_id)
            if task:
                status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
                if status_val == "pending":
                    if sync_task_manager.cancel_task(task_id):
                        cancelled_count += 1
        
        # Mark execution as stopping (will be updated to stopped when all tasks finish)
        record["status"] = "stopping"
        update_schedule_execution(execution_id, record)
        
        logger.info(f"Stopped execution {execution_id}, cancelled {cancelled_count} pending tasks")
        
        # Update status immediately
        return self.update_execution_status(execution_id)
    
    def get_execution_detail(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed execution info including all task details and error summary.
        
        Args:
            execution_id: The execution ID to get details for
            
        Returns:
            BatchExecutionDetail dict with all task info and error summary
        """
        from .service import sync_task_manager
        
        # Find the execution record
        history = get_schedule_history(limit=100)
        record = None
        for r in history:
            if r.get("execution_id") == execution_id:
                record = r
                break
        
        if not record:
            return None
        
        # Get all task details
        task_ids = record.get("task_ids", [])
        tasks = []
        error_parts = []
        
        for task_id in task_ids:
            task = sync_task_manager.get_task(task_id)
            if task:
                task_detail = {
                    "task_id": task.task_id,
                    "plugin_name": task.plugin_name,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "progress": task.progress,
                    "records_processed": task.records_processed,
                    "error_message": task.error_message,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                }
                tasks.append(task_detail)
                
                # Collect errors for summary
                if task.error_message:
                    error_parts.append(f"=== {task.plugin_name} ===\n{task.error_message}")
        
        # Build error summary for easy copying
        error_summary = "\n\n".join(error_parts) if error_parts else ""
        
        return {
            "execution_id": record.get("execution_id"),
            "trigger_type": record.get("trigger_type", "scheduled"),
            "started_at": record.get("started_at"),
            "completed_at": record.get("completed_at"),
            "status": record.get("status", "running"),
            "total_plugins": record.get("total_plugins", 0),
            "completed_plugins": record.get("completed_plugins", 0),
            "failed_plugins": record.get("failed_plugins", 0),
            "tasks": tasks,
            "error_summary": error_summary,
            "group_name": record.get("group_name"),
        }
    
    def create_manual_execution(
        self, 
        task_ids: List[str], 
        trigger_type: str = "manual",
        group_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an execution record for manual sync (single plugin or batch).
        
        Args:
            task_ids: List of task IDs to associate with this execution
            trigger_type: Type of trigger ("manual", "group")
            group_name: Name of the plugin group if triggered from a group
            
        Returns:
            ScheduleExecutionRecord dict
        """
        execution_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()
        
        record = {
            "execution_id": execution_id,
            "trigger_type": trigger_type,
            "started_at": started_at.isoformat(),
            "completed_at": None,
            "status": "running",
            "total_plugins": len(task_ids),
            "completed_plugins": 0,
            "failed_plugins": 0,
            "task_ids": task_ids,
            "can_retry": False,
        }
        
        if group_name:
            record["group_name"] = group_name
        
        add_schedule_execution(record)
        logger.info(f"Created manual execution {execution_id} with {len(task_ids)} tasks")
        
        return record
    
    def partial_retry_execution(
        self, 
        execution_id: str, 
        task_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Retry only failed tasks from an execution in-place.
        
        Does not create a new execution - retries failed tasks within the same execution.
        
        Args:
            execution_id: The execution ID to retry from
            task_ids: Specific task IDs to retry, or None to retry all failed
            
        Returns:
            Updated ScheduleExecutionRecord dict
            
        Raises:
            ValueError: If execution not found or no failed tasks
        """
        from .service import sync_task_manager
        
        # Find the original execution
        history = get_schedule_history(limit=100)
        original = None
        for r in history:
            if r.get("execution_id") == execution_id:
                original = r
                break
        
        if not original:
            raise ValueError(f"Execution {execution_id} not found")
        
        # Get failed tasks
        original_task_ids = original.get("task_ids", [])
        failed_tasks = []
        
        for tid in original_task_ids:
            task = sync_task_manager.get_task(tid)
            if task:
                status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
                if status_val == "failed":
                    # If specific task_ids provided, only include those
                    if task_ids is None or tid in task_ids:
                        failed_tasks.append(task)
        
        if not failed_tasks:
            raise ValueError(f"No failed tasks to retry in execution {execution_id}")
        
        # Retry failed tasks in-place (create new tasks and update execution)
        new_task_ids = list(original_task_ids)  # Copy original task ids
        retried_count = 0
        
        for old_task in failed_tasks:
            try:
                new_task = sync_task_manager.create_task(
                    plugin_name=old_task.plugin_name,
                    task_type=old_task.task_type,
                    trade_dates=old_task.trade_dates if old_task.trade_dates else None,
                    user_id="system",
                    username="retry",
                )
                # Replace old task id with new task id in the list
                old_idx = new_task_ids.index(old_task.task_id)
                new_task_ids[old_idx] = new_task.task_id
                retried_count += 1
                logger.info(f"Retried task {old_task.task_id} -> {new_task.task_id} for {old_task.plugin_name}")
            except Exception as e:
                logger.error(f"Failed to retry task for {old_task.plugin_name}: {e}")
        
        if retried_count == 0:
            raise ValueError("Failed to retry any tasks")
        
        # Update the execution record with new task ids and reset status
        original["task_ids"] = new_task_ids
        original["status"] = "running"
        original["completed_at"] = None
        original["failed_plugins"] = original.get("failed_plugins", 0) - retried_count
        if original["failed_plugins"] < 0:
            original["failed_plugins"] = 0
        
        update_schedule_execution(execution_id, original)
        logger.info(f"Retried {retried_count} failed tasks in execution {execution_id}")
        
        return original


# Global instance
schedule_service = ScheduleService()
