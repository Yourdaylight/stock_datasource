## Why
当前数据拉取/同步存在“双任务系统”：`SyncTaskManager`（线程池+内存队列）与 `TaskQueue/TaskWorker`（Redis list + 独立进程）并存，并且在 `SyncTaskManager.create_task()` 中出现“Redis 不可用则静默回退 legacy 模式”的行为。这导致：
- 运行时语义不一致（同一个 API 调用，可能变成不同执行路径）
- 状态来源分裂（Redis 与内存/ClickHouse）
- 可靠性不可控（无 Redis 配置时任务仍可被创建，但执行能力与并发/超时/重试策略不透明）

本变更提出：以 Redis queue 作为**唯一**异步执行通道，强制启用（模式 A）：未配置/不可用即明确失败；同时补齐“重试/超时/状态查询”的一致 API，并确保 TuShare HTTP 代理能力在 worker 执行环境下稳定可用。

## What Changes
- 将数据同步任务的后台执行统一为“Redis queue + 独立 worker”的单通道架构，移除 `SyncTaskManager` 的 legacy 内存队列执行路径。
- 任务具备：
  - **异步执行**：Web/API 只负责入队与查询
  - **超时控制**：单任务执行超时后标记失败并释放 worker
  - **自动重试**：按策略重试（次数、退避），可区分可重试与不可重试错误
  - **状态查询**：通过统一的 Task/Execution 状态模型查询进度、错误、执行统计
- 强制 Redis 可用：
  - 当 `REDIS_ENABLED=false` 或连接失败时，创建任务与相关 API 返回明确错误（例如 503/409），不再 silent fallback。
- TuShare HTTP 代理不受影响：
  - worker 执行插件时继续使用 `proxy_context()`（进程/任务级隔离），确保 proxy 仅对数据拉取生效。

## Impact
- Affected code (for apply stage):
  - `stock_datasource/modules/datamanage/service.py` (`SyncTaskManager.create_task()` fallback removal, status path consolidation)
  - `stock_datasource/services/task_queue.py` (retry/timeout/status model extensions)
  - `stock_datasource/services/task_worker.py` (timeout watchdog, retry loop, proxy isolation, graceful shutdown)
  - `stock_datasource/modules/datamanage/router.py` (API error semantics when Redis unavailable)
  - `stock_datasource/services/http_server.py` (local-dev auto worker start policy may be simplified)

- Behavior changes:
  - **BREAKING**：未配置 Redis 时，数据同步任务不再可用（明确失败），不会回退到线程池执行。
  - 状态查询将以 Redis 为主、ClickHouse 为历史审计（或仅用于历史列表），避免多源分裂。
