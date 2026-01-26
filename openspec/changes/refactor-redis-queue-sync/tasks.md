## 1. Discovery / Baseline
- [ ] 1.1 Identify all call sites of `sync_task_manager.create_task()` (scheduler + routers) and classify use-cases: incremental, backfill, group execution.
- [ ] 1.2 Identify existing status/query endpoints and UI expectations for task status fields (pending/running/completed/failed/cancelled).

## 2. Redis requirement (Mode A)
- [ ] 2.1 Introduce a single “Redis availability gate” used by task submission endpoints (e.g., `assert_redis_available()`), returning a clear HTTP error when Redis is disabled/unreachable.
- [ ] 2.2 Remove silent fallback in `SyncTaskManager.create_task(use_queue=True)`; when Redis is unavailable, raise a domain error instead of switching to legacy execution.
- [ ] 2.3 Update `/health` to explicitly report async queue availability (already exposes cache stats; extend/align semantics if needed).

## 3. Unified job model: task + execution
- [ ] 3.1 Extend `TaskQueue` task payload to include:
  - retry metadata: `attempt`, `max_attempts`, `next_run_at`, `last_error_type`
  - timeout metadata: `timeout_seconds`, `deadline_at`
  - timestamps: `updated_at`
- [ ] 3.2 Define a stable status machine for tasks: `pending -> running -> completed|failed|cancelled` (+ `retrying` optional).
- [ ] 3.3 Ensure `get_task()` and execution aggregation (`update_execution_stats`) reflect retries correctly (e.g., failures within attempts do not mark execution finished until attempts exhausted).

## 4. Worker behavior: timeout + retry
- [ ] 4.1 Add per-task timeout enforcement in `TaskWorker`:
  - enforce wall-clock timeout for plugin execution (incremental/backfill)
  - on timeout: mark failed with reason, do not hang worker
- [ ] 4.2 Add automatic retry loop:
  - configurable max attempts (default from `settings.TUSHARE_MAX_RETRIES` or plugin config)
  - exponential backoff with jitter, persisted in Redis
  - classify retryable errors vs non-retryable (e.g., config missing, plugin not found are non-retryable)
- [ ] 4.3 Ensure proxy correctness:
  - wrap actual plugin network execution in `proxy_context()` (already done in `SyncTaskManager`; ensure worker matches)
  - verify no proxy is applied globally at server startup

## 5. API: status query + cancellation + retry endpoints
- [ ] 5.1 Align `datamanage` API endpoints to read status from Redis task keys when present; avoid relying on in-memory `_tasks`.
- [ ] 5.2 Ensure task cancellation works for Redis pending tasks (queue removal + status update).
- [ ] 5.3 Ensure user-triggered retry creates a new task (new id) or re-enqueues same id (pick one and document).

## 6. Remove legacy execution path (single system)
- [ ] 6.1 Remove `SyncTaskManager` in-memory queue usage for execution (keep ClickHouse persistence for history if desired).
- [ ] 6.2 Ensure scheduler `DataSyncScheduler` always submits jobs via Redis queue.
- [ ] 6.3 Ensure local-dev worker auto-start behavior is explicit and documented (either keep auto-spawn or require running worker command).

## 7. Validation
- [ ] 7.1 Add minimal unit tests for `TaskQueue` serialization and retry metadata.
- [ ] 7.2 Add integration-style smoke test instructions (manual):
  - enqueue a task
  - observe running/completed status transitions
  - simulate Redis down and confirm API returns expected error
  - verify proxy-enabled environment still fetches TuShare data
- [ ] 7.3 Run formatting/lint checks (if configured).

## 8. OpenSpec
- [ ] 8.1 Run `openspec validate refactor-redis-queue-sync --strict` and fix all issues.
