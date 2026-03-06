"""Independent worker process for executing sync tasks.

This worker runs as a separate process, consuming tasks from the Redis queue
and executing them independently of the main API server. This ensures that
heavy data sync operations don't block API requests.

Usage:
    uv run python -m stock_datasource.services.task_worker
    
Or with multiple workers:
    uv run python -m stock_datasource.services.task_worker --workers 4
"""

import argparse
import logging
import multiprocessing
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from stock_datasource.services.task_queue import task_queue, TaskPriority
from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client

# Configure logging - use /data/log in Docker, local logs/ dir otherwise
LOG_DIR = Path("/data/log") if Path("/data").exists() and os.access("/data", os.W_OK) else Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
log_file = LOG_DIR / "task_worker.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("task_worker")


def _detect_plugin_param_style(plugin) -> str:
    """Detect the parameter style a plugin expects.

    Returns one of:
        'date_range'   – needs start_date + end_date
        'period'       – needs period (YYYYMMDD)
        'entity_code'  – needs entity-specific code (index_code, ts_code, etc.),
                         plugin should handle batch iteration internally
        'no_params'    – no required params, can call with no args
        'trade_date'   – default, needs trade_date
    """
    plugin_config = plugin.get_config() if hasattr(plugin, "get_config") else {}
    params_schema = plugin_config.get("parameters_schema", {})

    if "start_date" in params_schema and "end_date" in params_schema:
        return "date_range"

    # Check for entity-code params that are *required*
    entity_keys = {"index_code", "ts_code", "code"}
    required_entity = set()
    for k in entity_keys:
        if k in params_schema:
            spec = params_schema[k]
            # Only count as entity_code if the param is actually required
            if isinstance(spec, dict) and spec.get("required", False):
                required_entity.add(k)
            elif not isinstance(spec, dict):
                # Flat schema without required flag — treat as required
                required_entity.add(k)
    if required_entity:
        if "trade_date" not in params_schema:
            return "entity_code"

    if "period" in params_schema and "trade_date" not in params_schema:
        return "period"

    # If all params in schema are optional (none required), plugin can run with no args
    if params_schema:
        has_any_required = any(
            isinstance(v, dict) and v.get("required", False)
            for v in params_schema.values()
        )
        if not has_any_required and "trade_date" not in params_schema:
            return "no_params"

    if not params_schema or all(
        k in ("trade_date",) for k in params_schema
    ):
        return "trade_date"

    return "trade_date"


def _run_plugin_in_subprocess(task_data: dict, result_queue: multiprocessing.Queue) -> None:
    """Run plugin in a subprocess and report result via queue.

    This function MUST NOT raise (best effort) so the parent can classify failures.
    """
    try:
        from stock_datasource.core.proxy import proxy_context

        plugin_name = task_data.get("plugin_name")
        task_type = task_data.get("task_type")
        trade_dates = task_data.get("trade_dates", [])
        task_id = task_data.get("task_id")

        plugin_manager.discover_plugins()
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            result_queue.put((False, 0, "plugin_not_found", f"Plugin {plugin_name} not found"))
            return

        with proxy_context():
            if task_type == "backfill" and trade_dates:
                # run per date to provide partial progress in parent process only
                total_records = 0
                for date in trade_dates:
                    date_for_api = date.replace("-", "") if "-" in date else date
                    result = plugin.run(trade_date=date_for_api)
                    if result.get("status") != "success":
                        err = result.get("error", "插件执行失败")
                        detail = result.get("error_detail", "")
                        msg = f"{err}\n{detail}" if detail else err
                        result_queue.put((False, total_records, "retryable", msg))
                        return
                    total_records += int(result.get("steps", {}).get("load", {}).get("total_records", 0))

                result_queue.put((True, total_records, "", ""))
                return

            from stock_datasource.core.trade_calendar import trade_calendar_service, MARKET_CN, MARKET_HK
            from stock_datasource.core.base_plugin import PluginCategory

            market = MARKET_HK if plugin.get_category() == PluginCategory.HK_STOCK else MARKET_CN

            # Detect what parameters this plugin expects
            param_style = _detect_plugin_param_style(plugin)

            if task_type == "full":
                # Full sync: auto-detect parameter style from plugin config's
                # parameters_schema, then run with a reasonable historical range.
                total_records = 0
                plugin_config = plugin.get_config() if hasattr(plugin, "get_config") else {}

                if param_style == "date_range":
                    # Plugins using start_date/end_date (financial statements)
                    end_dt = datetime.now().strftime("%Y%m%d")
                    start_dt = (datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d")
                    logger.info(f"[full] {plugin_name}: date_range {start_dt}~{end_dt}")
                    result = plugin.run(start_date=start_dt, end_date=end_dt)
                    if result.get("status") != "success":
                        err = result.get("error", "插件执行失败")
                        detail = result.get("error_detail", "")
                        msg = f"{err}\n{detail}" if detail else err
                        result_queue.put((False, 0, "retryable", msg))
                        return
                    total_records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                elif param_style == "entity_code":
                    # Plugins that need entity codes: call with no args (let plugin handle batch internally)
                    logger.info(f"[full] {plugin_name}: entity_code mode (no-arg call)")
                    result = plugin.run()
                    if result.get("status") != "success":
                        err = result.get("error", "插件执行失败")
                        detail = result.get("error_detail", "")
                        msg = f"{err}\n{detail}" if detail else err
                        result_queue.put((False, 0, "retryable", msg))
                        return
                    total_records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                elif param_style == "no_params":
                    logger.info(f"[full] {plugin_name}: no-params mode")
                    result = plugin.run()
                    if result.get("status") != "success":
                        err = result.get("error", "插件执行失败")
                        detail = result.get("error_detail", "")
                        msg = f"{err}\n{detail}" if detail else err
                        result_queue.put((False, 0, "retryable", msg))
                        return
                    total_records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                else:
                    # Plugins using trade_date: iterate over recent trading days
                    full_days = int(plugin_config.get("full_sync_days", 500))
                    today_str = datetime.now().strftime("%Y%m%d")
                    start_str = (datetime.now() - timedelta(days=full_days + 200)).strftime("%Y%m%d")
                    dates_raw = trade_calendar_service.get_trading_days_between(
                        start_date=start_str,
                        end_date=today_str,
                        market=market,
                    )
                    # Convert YYYY-MM-DD to YYYYMMDD
                    dates = [d.replace("-", "") for d in dates_raw] if dates_raw else []
                    if not dates:
                        dates = [(datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                                 for i in range(full_days, -1, -1)]
                    dates = dates[-full_days:]
                    logger.info(f"[full] {plugin_name}: {len(dates)} trading days")
                    for dt_str in dates:
                        try:
                            result = plugin.run(trade_date=dt_str)
                            if result.get("status") == "success":
                                total_records += int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                        except Exception as e:
                            logger.warning(f"[full] {plugin_name} date={dt_str} failed: {e}")

                result_queue.put((True, total_records, "", ""))
                return

            # incremental — determine target date
            today = datetime.now().strftime("%Y%m%d")
            if trade_calendar_service.is_trading_day(today, market=market):
                target_date = today
            else:
                prev_date = trade_calendar_service.get_prev_trading_day(today, market=market)
                target_date = prev_date or (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

            # incremental: build run_kwargs based on plugin parameter style
            if plugin_name and plugin_name.endswith("_vip"):
                year = target_date[:4]
                run_kwargs: dict[str, Any] = {"period": f"{year}1231"}
            elif param_style == "date_range":
                # Plugins requiring start_date/end_date: use target_date for both
                run_kwargs = {"start_date": target_date, "end_date": target_date}
                logger.info(f"[incremental] {plugin_name}: date_range mode ({target_date})")
            elif param_style == "period":
                year = target_date[:4]
                run_kwargs = {"period": f"{year}1231"}
                logger.info(f"[incremental] {plugin_name}: period mode ({year}1231)")
            elif param_style == "entity_code":
                # Plugins requiring entity codes: call with no args (plugin handles batch internally)
                run_kwargs = {}
                logger.info(f"[incremental] {plugin_name}: entity_code mode (no-arg call)")
            else:
                run_kwargs = {"trade_date": target_date}

            result = plugin.run(**run_kwargs)
            if result.get("status") != "success":
                err = result.get("error", "插件执行失败")
                detail = result.get("error_detail", "")
                msg = f"{err}\n{detail}" if detail else err
                result_queue.put((False, 0, "retryable", msg))
                return

            records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
            result_queue.put((True, records, "", ""))
    except Exception as e:
        result_queue.put((False, 0, "retryable", str(e)))


class TaskWorker:
    """Worker that processes tasks from the Redis queue."""
    
    def __init__(self, worker_id: int = 0):
        """Initialize worker.
        
        Args:
            worker_id: Unique identifier for this worker
        """
        self.worker_id = worker_id
        self.running = True
        self.current_task_id: Optional[str] = None
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Worker {self.worker_id}: Received signal {signum}, shutting down...")
        self.running = False
    
    def run(self):
        """Main worker loop."""
        logger.info(f"Worker {self.worker_id}: Started")
        
        # Initialize plugin manager
        plugin_manager.discover_plugins()
        logger.info(f"Worker {self.worker_id}: Discovered {len(plugin_manager.list_plugins())} plugins")
        
        # Clean up stale running tasks on startup (only worker 0 to avoid races)
        if self.worker_id == 0:
            self._cleanup_stale_running_tasks()
        
        last_cleanup = time.time()
        
        while self.running:
            try:
                # Get next task from queue (blocks for up to 5 seconds)
                task_data = task_queue.dequeue(timeout=5)
                
                if task_data:
                    self._process_task(task_data)
                
                # Periodic stale task cleanup (every 30 minutes, only worker 0)
                if self.worker_id == 0 and time.time() - last_cleanup > 1800:
                    self._cleanup_stale_running_tasks()
                    last_cleanup = time.time()
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error in main loop: {e}")
                traceback.print_exc()
                time.sleep(1)  # Prevent tight error loop
        
        logger.info(f"Worker {self.worker_id}: Stopped")
    
    def _cleanup_stale_running_tasks(self):
        """Clean up stale entries in the running_tasks set.
        
        Tasks stuck in 'running' status for longer than the max timeout
        are likely from crashed workers. Re-queue or fail them.
        """
        from stock_datasource.services.task_queue import RedisUnavailableError
        
        try:
            redis = task_queue._get_redis()
        except RedisUnavailableError:
            return
        
        try:
            running_ids = redis.smembers(task_queue.RUNNING_KEY)
            if not running_ids:
                return
            
            now = datetime.now()
            stale_count = 0
            max_stale_hours = 5  # Tasks running > 5 hours are considered stale
            
            for task_id in running_ids:
                task_data = redis.hgetall(task_queue.TASK_KEY.format(task_id=task_id))
                if not task_data:
                    # Task hash expired/deleted but still in running set
                    redis.srem(task_queue.RUNNING_KEY, task_id)
                    stale_count += 1
                    continue
                
                status = task_data.get("status", "")
                started_at = task_data.get("started_at", "")
                
                # If status is not actually 'running', remove from running set
                if status not in ("running",):
                    redis.srem(task_queue.RUNNING_KEY, task_id)
                    stale_count += 1
                    continue
                
                # Check if task has been running too long
                if started_at:
                    try:
                        started = datetime.fromisoformat(started_at)
                        age_hours = (now - started).total_seconds() / 3600
                        if age_hours > max_stale_hours:
                            plugin_name = task_data.get("plugin_name", "unknown")
                            attempt = int(task_data.get("attempt", 0))
                            max_attempts = int(task_data.get("max_attempts", 3))
                            
                            # Mark as failed
                            redis.hset(task_queue.TASK_KEY.format(task_id=task_id), mapping={
                                "status": "failed",
                                "error_message": f"Stale task cleanup: running for {age_hours:.1f}h (likely from crashed worker)",
                                "completed_at": now.isoformat(),
                                "updated_at": now.isoformat(),
                            })
                            redis.srem(task_queue.RUNNING_KEY, task_id)
                            stale_count += 1
                            
                            logger.warning(
                                f"Worker {self.worker_id}: Cleaned stale task {task_id} "
                                f"({plugin_name}, age={age_hours:.1f}h)"
                            )
                    except (ValueError, TypeError):
                        pass
            
            if stale_count > 0:
                logger.info(f"Worker {self.worker_id}: Cleaned {stale_count} stale running tasks")
        except Exception as e:
            logger.warning(f"Worker {self.worker_id}: Stale task cleanup error: {e}")
    
    def _process_task(self, task_data: dict):
        """Process a single task with timeout + automatic retries."""
        task_id = task_data.get("task_id")
        plugin_name = task_data.get("plugin_name")

        self.current_task_id = task_id
        logger.info(f"Worker {self.worker_id}: Processing task {task_id} for plugin {plugin_name}")

        try:
            attempt = int(task_data.get("attempt", 0))
            max_attempts = int(task_data.get("max_attempts", 3))

            try:
                timeout_seconds = int(task_data.get("timeout_seconds", 900))
            except Exception:
                raw_timeout = task_data.get("timeout_seconds")
                logger.warning(
                    f"Worker {self.worker_id}: Invalid timeout_seconds={raw_timeout!r} for task {task_id}, fallback to 900"
                )
                timeout_seconds = 900

            execution_id = task_data.get("execution_id")

            if attempt >= max_attempts:
                raise ValueError(f"Task attempts already exhausted: attempt={attempt}, max_attempts={max_attempts}")

            success, records, error_type, error_msg = self._run_task_with_timeout(
                task_data=task_data,
                timeout_seconds=timeout_seconds,
            )

            if success:
                task_queue.complete_task(task_id, records)
                if execution_id:
                    task_queue.update_execution_stats(execution_id)
                logger.info(f"Worker {self.worker_id}: Task {task_id} completed with {records} records")
                return

            # Failed
            next_attempt = attempt + 1
            if self._is_retryable_error(error_type) and next_attempt < max_attempts:
                delay_seconds = self._compute_backoff_seconds(next_attempt)
                logger.warning(
                    f"Worker {self.worker_id}: Task {task_id} failed (attempt {next_attempt}/{max_attempts}), "
                    f"retry in {delay_seconds}s: {error_type}: {error_msg[:200]}"
                )
                self._schedule_retry(
                    task_data=task_data,
                    next_attempt=next_attempt,
                    delay_seconds=delay_seconds,
                    last_error_type=error_type,
                    error_message=error_msg,
                )
                if execution_id:
                    task_queue.update_execution_stats(execution_id)
                return

            # Attempts exhausted or non-retryable
            final_attempt = next_attempt if next_attempt > attempt else attempt
            full_error = f"{error_type}: {error_msg}\n\n{traceback.format_exc()}"
            self._mark_failed_exhausted(
                task_id=task_id,
                attempt=final_attempt,
                max_attempts=max_attempts,
                last_error_type=error_type,
                error_message=full_error,
            )
            if execution_id:
                task_queue.update_execution_stats(execution_id)

            logger.error(
                f"Worker {self.worker_id}: Task {task_id} failed permanently: {error_type}: {error_msg[:200]}"
            )

        except Exception as e:
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            task_queue.fail_task(task_id, error_msg)
            execution_id = task_data.get("execution_id")
            if execution_id:
                task_queue.update_execution_stats(execution_id)
            logger.error(f"Worker {self.worker_id}: Task {task_id} failed: {e}")

        finally:
            self.current_task_id = None
    
    def _is_retryable_error(self, error_type: str) -> bool:
        if error_type in {"plugin_not_found", "config_error"}:
            return False
        return True

    def _compute_backoff_seconds(self, attempt: int) -> int:
        # Exponential backoff with jitter (bounded)
        base = min(2 ** attempt, 60)
        jitter = int(time.time()) % 3
        return base + jitter

    def _schedule_retry(
        self,
        task_data: dict,
        next_attempt: int,
        delay_seconds: int,
        last_error_type: str,
        error_message: str,
    ) -> None:
        from stock_datasource.services.task_queue import RedisUnavailableError

        task_id = task_data.get("task_id")
        priority = int(task_data.get("priority", TaskPriority.NORMAL.value))

        try:
            redis = task_queue._get_redis()
        except RedisUnavailableError:
            return

        now = datetime.now()
        next_run_at = (now + timedelta(seconds=delay_seconds)).isoformat()

        redis.hset(task_queue.TASK_KEY.format(task_id=task_id), mapping={
            "status": "pending",
            "attempt": next_attempt,
            "next_run_at": next_run_at,
            "last_error_type": last_error_type,
            "error_message": error_message[:2000],
            "updated_at": now.isoformat(),
            "started_at": "",
            "completed_at": "",
        })

        queue_key = task_queue.QUEUE_KEY.format(priority=priority)
        redis.lpush(queue_key, task_id)

    def _mark_failed_exhausted(
        self,
        task_id: str,
        attempt: int,
        max_attempts: int,
        last_error_type: str,
        error_message: str,
    ) -> None:
        from stock_datasource.services.task_queue import RedisUnavailableError

        try:
            redis = task_queue._get_redis()
        except RedisUnavailableError:
            return

        now = datetime.now().isoformat()
        redis.hset(task_queue.TASK_KEY.format(task_id=task_id), mapping={
            "status": "failed",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "last_error_type": last_error_type,
            "error_message": error_message[:2000],
            "completed_at": now,
            "updated_at": now,
        })
        redis.srem(task_queue.RUNNING_KEY, task_id)

    def _run_task_with_timeout(self, task_data: dict, timeout_seconds: int) -> tuple[bool, int, str, str]:
        """Run the plugin execution in a child process to enforce wall-clock timeout."""
        result_queue: multiprocessing.Queue = multiprocessing.Queue(maxsize=1)

        proc = multiprocessing.Process(
            target=_run_plugin_in_subprocess,
            args=(task_data, result_queue),
        )
        proc.start()
        proc.join(timeout=timeout_seconds)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=5)
            return False, 0, "timeout", f"Task exceeded timeout_seconds={timeout_seconds}"

        try:
            success, records, error_type, error_msg = result_queue.get_nowait()
            return bool(success), int(records), str(error_type), str(error_msg)
        except Exception:
            return False, 0, "unknown", "Subprocess finished without returning result"

    def _execute_incremental(self, task_id: str, plugin) -> int:
        """Execute incremental sync for a plugin.
        
        Args:
            task_id: Task ID
            plugin: Plugin instance
            
        Returns:
            Number of records processed
        """
        # Get latest trading date
        target_date = self._get_latest_trading_date()
        if not target_date:
            raise ValueError("无法获取有效交易日")
        
        logger.info(f"Worker {self.worker_id}: Incremental sync for date {target_date}")
        
        result = plugin.run(trade_date=target_date)
        
        if result.get("status") != "success":
            error_msg = result.get("error", "插件执行失败")
            error_detail = result.get("error_detail", "")
            raise ValueError(f"{error_msg}\n{error_detail}" if error_detail else error_msg)
        
        records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
        task_queue.update_progress(task_id, 100, records)
        
        return records
    
    def _execute_backfill(self, task_id: str, plugin, trade_dates: list) -> int:
        """Execute backfill sync for multiple dates.
        
        Args:
            task_id: Task ID
            plugin: Plugin instance
            trade_dates: List of dates to process
            
        Returns:
            Total records processed
        """
        total_records = 0
        total_dates = len(trade_dates)
        
        for i, date in enumerate(trade_dates):
            if not self.running:
                logger.warning(f"Worker {self.worker_id}: Task interrupted")
                break
            
            try:
                # Convert date format if needed (YYYY-MM-DD -> YYYYMMDD)
                date_for_api = date.replace("-", "") if "-" in date else date
                
                logger.info(f"Worker {self.worker_id}: Processing date {date} ({i+1}/{total_dates})")
                
                result = plugin.run(trade_date=date_for_api)
                
                if result.get("status") == "success":
                    records = int(result.get("steps", {}).get("load", {}).get("total_records", 0))
                    total_records += records
                else:
                    logger.warning(f"Worker {self.worker_id}: Date {date} failed: {result.get('error')}")
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Date {date} error: {e}")
            
            # Update progress
            progress = ((i + 1) / total_dates) * 100
            task_queue.update_progress(task_id, progress, total_records)
        
        return total_records
    
    def _get_latest_trading_date(self, market: str = "cn") -> Optional[str]:
        """Get the latest valid trading date.
        
        Args:
            market: Market type - 'cn' for A-share, 'hk' for HK stock
        
        Returns:
            Date string in YYYYMMDD format, or None if not available
        """
        try:
            from stock_datasource.core.trade_calendar import trade_calendar_service
            
            today = datetime.now().strftime("%Y%m%d")
            
            # Check if today is a trading day
            if trade_calendar_service.is_trading_day(today, market=market):
                return today
            
            # Get previous trading day
            prev_date = trade_calendar_service.get_prev_trading_day(today, market=market)
            if prev_date:
                return prev_date
            
            # Fallback: try last 7 days
            for i in range(1, 8):
                check_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                if trade_calendar_service.is_trading_day(check_date, market=market):
                    return check_date
            
            # Last resort fallback
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday
            
        except Exception as e:
            logger.error(f"Failed to get trading date: {e}")
            # Fallback to last Friday if weekend
            today = datetime.now()
            weekday = today.weekday()
            if weekday == 5:  # Saturday
                return (today - timedelta(days=1)).strftime("%Y%m%d")
            elif weekday == 6:  # Sunday
                return (today - timedelta(days=2)).strftime("%Y%m%d")
            return (today - timedelta(days=1)).strftime("%Y%m%d")


def run_worker(worker_id: int):
    """Run a single worker (for multiprocessing).
    
    Args:
        worker_id: Worker ID
    """
    worker = TaskWorker(worker_id)
    worker.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Task Worker")
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    args = parser.parse_args()
    
    num_workers = args.workers
    
    if num_workers == 1:
        # Single worker mode
        worker = TaskWorker(0)
        worker.run()
    else:
        # Multi-worker mode
        logger.info(f"Starting {num_workers} worker processes...")
        
        processes = []
        for i in range(num_workers):
            p = multiprocessing.Process(target=run_worker, args=(i,))
            p.start()
            processes.append(p)
        
        # Wait for all workers
        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            logger.info("Shutting down workers...")
            for p in processes:
                p.terminate()
            for p in processes:
                p.join(timeout=5)


if __name__ == "__main__":
    main()
