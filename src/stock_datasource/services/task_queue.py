"""Redis-based task queue for async sync task processing.

This module provides a Redis-backed task queue that decouples task submission
from task execution, allowing the API to remain responsive while workers
process tasks independently.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

from redis import Redis

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is required but unavailable."""


class TaskPriority(Enum):
    """Task priority levels."""
    HIGH = 0    # Urgent tasks (manual trigger)
    NORMAL = 1  # Regular scheduled tasks
    LOW = 2     # Background/batch tasks


class TaskQueue:
    """Redis-based task queue for sync tasks.
    
    Uses Redis lists for FIFO queue with priority support.
    Task status is stored in Redis hashes for quick lookup.
    """
    
    # Redis key prefixes
    QUEUE_KEY = "stock:task_queue:{priority}"
    TASK_KEY = "stock:task:{task_id}"
    RUNNING_KEY = "stock:running_tasks"
    EXECUTION_KEY = "stock:execution:{execution_id}"
    
    def __init__(self):
        """Initialize task queue with Redis connection."""
        self._redis: Optional[Redis] = None
        self._connected = False
    
    def _get_redis(self) -> Redis:
        """Get or create Redis connection.

        Mode A behavior: Redis is a required dependency for task queue.
        - If disabled by configuration or unreachable, raise RedisUnavailableError.
        """
        if not settings.REDIS_ENABLED:
            raise RedisUnavailableError("Redis is disabled (REDIS_ENABLED=false)")

        if self._redis is not None and self._connected:
            return self._redis

        try:
            self._redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
            )
            self._redis.ping()
            self._connected = True
            logger.info(f"Task queue connected to Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            return self._redis
        except Exception as e:
            self._connected = False
            raise RedisUnavailableError(f"Task queue Redis connection failed: {e}")
    
    def enqueue(
        self,
        plugin_name: str,
        task_type: str,
        trade_dates: List[str] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        execution_id: str = None,
        user_id: str = None,
    ) -> Optional[str]:
        """Add a task to the queue.
        
        Args:
            plugin_name: Name of the plugin to run
            task_type: Type of task (incremental, full, backfill)
            trade_dates: List of dates to process (for backfill)
            priority: Task priority level
            execution_id: Batch execution ID if part of a batch
            user_id: User who triggered the task
            
        Returns:
            Task ID if successful, None otherwise
        """
        redis = self._get_redis()
        
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        task_data = {
            "task_id": task_id,
            "plugin_name": plugin_name,
            "task_type": task_type,
            "trade_dates": json.dumps(trade_dates or []),
            "status": "pending",
            "progress": 0,
            "records_processed": 0,
            "error_message": "",
            "created_at": now,
            "updated_at": now,
            "started_at": "",
            "completed_at": "",
            "execution_id": execution_id or "",
            "user_id": user_id or "",
            "priority": priority.value,
            "attempt": 0,
            "max_attempts": 3,
            "next_run_at": "",
            "last_error_type": "",
            "timeout_seconds": 14400,
            "deadline_at": "",
        }
        
        try:
            # Store task data
            redis.hset(self.TASK_KEY.format(task_id=task_id), mapping=task_data)
            # Set expiry (7 days)
            redis.expire(self.TASK_KEY.format(task_id=task_id), 7 * 24 * 3600)
            
            # Add to queue (LPUSH for FIFO with BRPOP)
            queue_key = self.QUEUE_KEY.format(priority=priority.value)
            redis.lpush(queue_key, task_id)
            
            logger.info(f"Enqueued task {task_id} for plugin {plugin_name} with priority {priority.name}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to enqueue task: {e}")
            return None
    
    def dequeue(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """Get next task from queue (blocking).

        Args:
            timeout: Seconds to wait for a task

        Returns:
            Task data dict if available, None otherwise
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return None

        try:
            # Try queues in priority order (0=HIGH, 1=NORMAL, 2=LOW)
            queue_keys = [
                self.QUEUE_KEY.format(priority=0),
                self.QUEUE_KEY.format(priority=1),
                self.QUEUE_KEY.format(priority=2),
            ]

            # BRPOP blocks until a task is available
            result = redis.brpop(queue_keys, timeout=timeout)
            if not result:
                return None

            queue_key, task_id = result

            # Get task data
            task_data = redis.hgetall(self.TASK_KEY.format(task_id=task_id))
            if not task_data:
                logger.warning(f"Task {task_id} not found in Redis")
                return None

            # Parse JSON fields
            task_data["trade_dates"] = json.loads(task_data.get("trade_dates", "[]"))
            task_data["progress"] = float(task_data.get("progress", 0))
            task_data["records_processed"] = int(task_data.get("records_processed", 0))
            task_data["priority"] = int(task_data.get("priority", 1))
            task_data["attempt"] = int(task_data.get("attempt", 0))
            task_data["max_attempts"] = int(task_data.get("max_attempts", 3))

            try:
                task_data["timeout_seconds"] = int(task_data.get("timeout_seconds", 900))
            except Exception:
                raw_timeout = task_data.get("timeout_seconds")
                logger.warning(f"Task {task_id}: Invalid timeout_seconds={raw_timeout!r}, fallback to 900")
                task_data["timeout_seconds"] = 900

            # Mark as running
            redis.hset(self.TASK_KEY.format(task_id=task_id), "status", "running")
            redis.hset(self.TASK_KEY.format(task_id=task_id), "started_at", datetime.now().isoformat())
            redis.sadd(self.RUNNING_KEY, task_id)

            return task_data

        except Exception as e:
            # Timeout waiting for empty queue is normal, log as DEBUG
            if "Timeout" in str(e) or "timeout" in str(e):
                logger.debug(f"No task available in queue (timeout after {timeout}s)")
            else:
                logger.error(f"Failed to dequeue task: {e}")
            return None
    
    def update_progress(self, task_id: str, progress: float, records_processed: int = 0):
        """Update task progress.
        
        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            records_processed: Number of records processed
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return

        try:
            redis.hset(self.TASK_KEY.format(task_id=task_id), mapping={
                "progress": progress,
                "records_processed": records_processed,
                "updated_at": datetime.now().isoformat(),
            })
        except Exception as e:
            logger.error(f"Failed to update task progress: {e}")
    
    def complete_task(self, task_id: str, records_processed: int = 0):
        """Mark task as completed.
        
        Args:
            task_id: Task ID
            records_processed: Total records processed
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return

        try:
            now = datetime.now().isoformat()
            redis.hset(self.TASK_KEY.format(task_id=task_id), mapping={
                "status": "completed",
                "progress": 100,
                "records_processed": records_processed,
                "completed_at": now,
                "updated_at": now,
            })
            redis.srem(self.RUNNING_KEY, task_id)
            logger.info(f"Task {task_id} completed with {records_processed} records")
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
    
    def fail_task(self, task_id: str, error_message: str):
        """Mark task as failed.
        
        Args:
            task_id: Task ID
            error_message: Error message
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return

        try:
            now = datetime.now().isoformat()
            redis.hset(self.TASK_KEY.format(task_id=task_id), mapping={
                "status": "failed",
                "error_message": error_message[:2000],  # Limit error length
                "completed_at": now,
                "updated_at": now,
            })
            redis.srem(self.RUNNING_KEY, task_id)
            logger.error(f"Task {task_id} failed: {error_message[:200]}")
        except Exception as e:
            logger.error(f"Failed to mark task as failed: {e}")
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task data by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task data dict if found, None otherwise
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return None

        try:
            task_data = redis.hgetall(self.TASK_KEY.format(task_id=task_id))
            if not task_data:
                return None

            # Parse JSON fields
            task_data["trade_dates"] = json.loads(task_data.get("trade_dates", "[]"))
            task_data["progress"] = float(task_data.get("progress", 0))
            task_data["records_processed"] = int(task_data.get("records_processed", 0))
            task_data["priority"] = int(task_data.get("priority", 1))
            task_data["attempt"] = int(task_data.get("attempt", 0))
            task_data["max_attempts"] = int(task_data.get("max_attempts", 3))
            task_data["timeout_seconds"] = int(task_data.get("timeout_seconds", 900))

            return task_data
        except Exception as e:
            logger.error(f"Failed to get task: {e}")
            return None
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics.

        Returns:
            Dict with queue stats
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError as e:
            return {"available": False, "error": str(e)}

        try:
            return {
                "available": True,
                "high_priority": redis.llen(self.QUEUE_KEY.format(priority=0)),
                "normal_priority": redis.llen(self.QUEUE_KEY.format(priority=1)),
                "low_priority": redis.llen(self.QUEUE_KEY.format(priority=2)),
                "running": redis.scard(self.RUNNING_KEY),
            }
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"available": False, "error": str(e)}

    def list_tasks(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """List recent tasks from Redis.

        Notes:
            Redis hash keys are scanned. This is intended for admin UI usage.

        Args:
            limit: Max number of tasks to return

        Returns:
            List of task dicts
        """
        redis = self._get_redis()

        tasks: List[Dict[str, Any]] = []
        cursor = 0
        pattern = self.TASK_KEY.format(task_id="*")

        try:
            while True:
                cursor, keys = redis.scan(cursor=cursor, match=pattern, count=200)
                for key in keys:
                    task_data = redis.hgetall(key)
                    if not task_data:
                        continue

                    task_data["trade_dates"] = json.loads(task_data.get("trade_dates", "[]"))
                    task_data["progress"] = float(task_data.get("progress", 0))
                    task_data["records_processed"] = int(task_data.get("records_processed", 0))
                    task_data["priority"] = int(task_data.get("priority", 1))
                    task_data["attempt"] = int(task_data.get("attempt", 0))
                    task_data["max_attempts"] = int(task_data.get("max_attempts", 3))
                    task_data["timeout_seconds"] = int(task_data.get("timeout_seconds", 900))

                    tasks.append(task_data)
                    if len(tasks) >= limit:
                        return tasks

                if cursor == 0:
                    break
        except Exception as e:
            logger.error(f"Failed to list tasks: {e}")

        return tasks
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task (remove from queue).

        Args:
            task_id: Task ID

        Returns:
            True if cancelled, False otherwise
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return False

        try:
            task_data = self.get_task(task_id)
            if not task_data:
                return False

            if task_data.get("status") != "pending":
                return False

            # Remove from queue
            priority = task_data.get("priority", 1)
            queue_key = self.QUEUE_KEY.format(priority=priority)
            redis.lrem(queue_key, 1, task_id)

            # Update status
            now = datetime.now().isoformat()
            redis.hset(self.TASK_KEY.format(task_id=task_id), mapping={
                "status": "cancelled",
                "completed_at": now,
                "updated_at": now,
            })

            logger.info(f"Task {task_id} cancelled")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel task: {e}")
            return False

    def delete_task(self, task_id: str) -> bool:
        """Delete a task hash and best-effort clean queue/running references.

        Note:
            This is an admin operation. It does not guarantee removal from a
            currently-running worker process.

        Returns:
            True if deleted (or already missing), False otherwise
        """
        redis = self._get_redis()

        try:
            task_data = redis.hgetall(self.TASK_KEY.format(task_id=task_id))
            if task_data:
                # Best-effort: remove from all priority queues
                for priority in (0, 1, 2):
                    redis.lrem(self.QUEUE_KEY.format(priority=priority), 0, task_id)

                redis.srem(self.RUNNING_KEY, task_id)

            redis.delete(self.TASK_KEY.format(task_id=task_id))
            return True
        except Exception as e:
            logger.error(f"Failed to delete task: {e}")
            return False
    
    def create_execution(
        self,
        task_ids: List[str],
        trigger_type: str = "manual",
        group_name: str = None,
        date_range: str = None,
    ) -> str:
        """Create a batch execution record.
        
        Args:
            task_ids: List of task IDs in this execution
            trigger_type: Type of trigger (manual, group, scheduled)
            group_name: Name of plugin group if applicable
            date_range: Date range string
            
        Returns:
            Execution ID
        """
        redis = self._get_redis()

        execution_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        execution_data = {
            "execution_id": execution_id,
            "trigger_type": trigger_type,
            "started_at": now,
            "completed_at": "",
            "status": "running",
            "total_plugins": len(task_ids),
            "completed_plugins": 0,
            "failed_plugins": 0,
            "task_ids": json.dumps(task_ids),
            "group_name": group_name or "",
            "date_range": date_range or "",
        }
        
        try:
            redis.hset(self.EXECUTION_KEY.format(execution_id=execution_id), mapping=execution_data)
            redis.expire(self.EXECUTION_KEY.format(execution_id=execution_id), 7 * 24 * 3600)
            
            # Link tasks to execution
            for task_id in task_ids:
                redis.hset(self.TASK_KEY.format(task_id=task_id), "execution_id", execution_id)
            
            logger.info(f"Created execution {execution_id} with {len(task_ids)} tasks")
            return execution_id
        except Exception as e:
            logger.error(f"Failed to create execution: {e}")
            return execution_id
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution data by ID.
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution data dict if found, None otherwise
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return None

        try:
            execution_data = redis.hgetall(self.EXECUTION_KEY.format(execution_id=execution_id))
            if not execution_data:
                return None
            
            # Parse JSON fields
            execution_data["task_ids"] = json.loads(execution_data.get("task_ids", "[]"))
            execution_data["total_plugins"] = int(execution_data.get("total_plugins", 0))
            execution_data["completed_plugins"] = int(execution_data.get("completed_plugins", 0))
            execution_data["failed_plugins"] = int(execution_data.get("failed_plugins", 0))
            
            return execution_data
        except Exception as e:
            logger.error(f"Failed to get execution: {e}")
            return None
    
    def update_execution_stats(self, execution_id: str):
        """Update execution statistics based on task statuses.
        
        Args:
            execution_id: Execution ID
        """
        try:
            redis = self._get_redis()
        except RedisUnavailableError:
            return

        try:
            execution_data = self.get_execution(execution_id)
            if not execution_data:
                return

            task_ids = execution_data.get("task_ids", [])
            completed = 0
            failed = 0
            all_done = True

            for task_id in task_ids:
                task = self.get_task(task_id)
                if not task:
                    all_done = False
                    continue

                status = task.get("status", "pending")
                attempt = int(task.get("attempt", 0))
                max_attempts = int(task.get("max_attempts", 3))

                if status == "completed":
                    completed += 1
                    continue

                if status == "failed":
                    # Only count as failed when attempts are exhausted.
                    if attempt >= max_attempts:
                        failed += 1
                    else:
                        all_done = False
                    continue

                if status in ("pending", "running"):
                    all_done = False
                    continue

                # Unknown/nonterminal status
                all_done = False

            updates = {
                "completed_plugins": completed,
                "failed_plugins": failed,
            }

            if all_done:
                updates["status"] = "failed" if failed > 0 else "completed"
                updates["completed_at"] = datetime.now().isoformat()

            redis.hset(self.EXECUTION_KEY.format(execution_id=execution_id), mapping=updates)

        except Exception as e:
            logger.error(f"Failed to update execution stats: {e}")


# Global task queue instance
task_queue = TaskQueue()
