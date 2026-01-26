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
from typing import Optional

from stock_datasource.services.task_queue import task_queue, TaskPriority
from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("task_worker")


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
        
        while self.running:
            try:
                # Get next task from queue (blocks for up to 5 seconds)
                task_data = task_queue.dequeue(timeout=5)
                
                if task_data:
                    self._process_task(task_data)
                
            except Exception as e:
                logger.error(f"Worker {self.worker_id}: Error in main loop: {e}")
                traceback.print_exc()
                time.sleep(1)  # Prevent tight error loop
        
        logger.info(f"Worker {self.worker_id}: Stopped")
    
    def _process_task(self, task_data: dict):
        """Process a single task.
        
        Args:
            task_data: Task data dict from queue
        """
        task_id = task_data.get("task_id")
        plugin_name = task_data.get("plugin_name")
        task_type = task_data.get("task_type")
        trade_dates = task_data.get("trade_dates", [])
        
        self.current_task_id = task_id
        logger.info(f"Worker {self.worker_id}: Processing task {task_id} for plugin {plugin_name}")
        
        try:
            # Get plugin
            plugin = plugin_manager.get_plugin(plugin_name)
            if not plugin:
                raise ValueError(f"Plugin {plugin_name} not found")
            
            # Execute based on task type
            if task_type == "backfill" and trade_dates:
                records = self._execute_backfill(task_id, plugin, trade_dates)
            else:
                records = self._execute_incremental(task_id, plugin)
            
            # Mark as completed
            task_queue.complete_task(task_id, records)
            
            # Update execution stats
            execution_id = task_data.get("execution_id")
            if execution_id:
                task_queue.update_execution_stats(execution_id)
            
            logger.info(f"Worker {self.worker_id}: Task {task_id} completed with {records} records")
            
        except Exception as e:
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            task_queue.fail_task(task_id, error_msg)
            
            # Update execution stats
            execution_id = task_data.get("execution_id")
            if execution_id:
                task_queue.update_execution_stats(execution_id)
            
            logger.error(f"Worker {self.worker_id}: Task {task_id} failed: {e}")
        
        finally:
            self.current_task_id = None
    
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
    
    def _get_latest_trading_date(self) -> Optional[str]:
        """Get the latest valid trading date.
        
        Returns:
            Date string in YYYYMMDD format, or None if not available
        """
        try:
            from stock_datasource.core.trade_calendar import trade_calendar_service
            
            today = datetime.now().strftime("%Y%m%d")
            
            # Check if today is a trading day
            if trade_calendar_service.is_trading_day(today):
                return today
            
            # Get previous trading day
            prev_date = trade_calendar_service.get_prev_trading_day(today)
            if prev_date:
                return prev_date
            
            # Fallback: try last 7 days
            for i in range(1, 8):
                check_date = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
                if trade_calendar_service.is_trading_day(check_date):
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
