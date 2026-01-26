## Context
当前项目同时存在两套“后台任务”执行机制：
- `stock_datasource/modules/datamanage/service.py::SyncTaskManager`：线程池 + 内存队列 + ClickHouse 记录（历史/展示）
- `stock_datasource/services/task_queue.py` + `task_worker.py`：Redis list + 独立 worker 进程

此外，项目对 TuShare 数据拉取存在 HTTP 代理需求，代理通过 `stock_datasource/core/proxy.py` 的 `proxy_context()` 在“数据拉取上下文”内设置进程环境变量，从而影响 requests/tushare。

## Goals / Non-Goals
- **Goals**
  - Web 后台与数据拉取任务解耦：API 只负责“提交 + 查询”，worker 负责“执行”。
  - 单通道任务系统：所有数据同步任务统一走 Redis queue。
  - 支持：后台异步执行 + **超时** + **重试** + **状态查询**。
  - 强制依赖 Redis（模式 A）：未配置/不可用 => 明确失败，不 silent fallback。
  - 保持 TuShare HTTP 代理能力稳定：proxy 仅在任务执行时启用，不污染全局。

- **Non-Goals**
  - 不引入 Celery/Dramatiq/RQ 等第三方大框架（本变更聚焦于“把现有 Redis 队列做完整并单一化”）。
  - 不重写所有插件逻辑；仅约束执行入口（worker）与任务元数据。
  - 不在 proposal 阶段改动代码（实现发生在 apply stage）。

## Target Architecture
### Components
- **API Server (FastAPI)**
  - 接收同步请求（单插件/插件组/补数）
  - 校验 Redis 可用性（fail fast）
  - 入队任务、返回 `task_id` / `execution_id`
  - 提供查询接口（task/execution status）

- **Redis Queue**
  - 队列：按优先级的 list（现有：`stock:task_queue:{priority}`）
  - 状态存储：task hash（现有：`stock:task:{task_id}`）
  - 执行聚合：execution hash（现有：`stock:execution:{execution_id}`）

- **Worker Process(es)**
  - `BRPOP` 拉取任务
  - 执行插件（带 `proxy_context()`）
  - 维护：超时、重试、进度更新、最终状态

- **ClickHouse（可选/延续）**
  - 用于历史审计与 UI 列表（长期保留）
  - 不作为“实时状态唯一来源”（避免 Redis/DB 双写时序问题）

### Sequence (happy path)
1. 用户触发同步（HTTP API）
2. API 校验 Redis 可用 → 写入 task hash（pending）→ 推入 queue
3. worker `BRPOP` 得到 task_id → task hash 标记 running
4. worker 执行插件：
   - `with proxy_context(): plugin.run(...)`
   - 周期性 `update_progress()`
5. 成功：`complete_task()`；失败：`fail_task()` 或 `requeue`（重试）
6. API 通过 `get_task(task_id)` 返回最新状态

## Key Decisions
### Decision 1: Redis is required (Mode A)
- **Decision**：当 `REDIS_ENABLED=false` 或 Redis 连接失败时，任务“创建/取消/重试”等 API 返回明确错误；不再走 `SyncTaskManager` 线程池回退。
- **Rationale**：
  - 解决双系统分裂
  - 避免“看起来创建成功但其实跑在另一套系统”的隐患
  - 让运维与用户对系统能力预期一致

### Decision 2: Retry semantics live in Redis task metadata
- **Decision**：重试次数、下次可运行时间（backoff）、最后错误类型等元数据写入 task hash。
- **Rationale**：
  - worker 可水平扩展，重试状态不依赖单进程内存
  - API 查询可以直接展示 attempt/backoff 等信息

### Decision 3: Timeout enforcement at worker level
- **Decision**：worker 对每个 task 应用 wall-clock 超时。
- **Rationale**：
  - 插件可能内部网络阻塞或卡死
  - 需要保证 worker 不被单个任务永久占用

### Decision 4: Proxy is scoped to execution
- **Decision**：proxy 只在任务执行上下文启用（`proxy_context()`），不在 HTTP server startup 全局启用。
- **Rationale**：
  - 代理配置可能是“仅对 TuShare”有效，不应影响其他网络请求
  - 进程级环境变量容易在并发场景产生意外影响，因此必须强调“作用域”

## Alternatives Considered
- **Celery / Dramatiq / RQ**
  - 优点：成熟的 retry/timeout/monitoring
  - 缺点：引入新框架与运行时组件（broker/result backend），迁移成本与学习成本更高
  - 结论：后续可作为进一步演进，但当前先把现有 Redis 队列做“单一化 + 可靠化”。

- **仅用 ClickHouse 作为队列/状态**
  - 优点：减少 Redis 依赖
  - 缺点：ClickHouse 不适合作为低延迟队列，且写入/一致性复杂
  - 结论：不采用

## Risks / Trade-offs
- **Redis 成为硬依赖**：
  - 风险：未部署 Redis 时功能不可用
  - 缓解：
    - `/health` 明确展示队列不可用
    - 文档/部署脚本强制包含 Redis（本提案不创建 README，但实现阶段可在现有部署变更中补）

- **任务状态双写（Redis + ClickHouse）时序问题**：
  - 风险：UI 看到的历史与实时状态不一致
  - 缓解：规定 Redis 为实时来源，ClickHouse 为审计来源；UI 列表可用 ClickHouse，详情页实时查询 Redis。

- **超时实现方式选择**：
  - Python 线程内无法可靠中断阻塞 I/O
  - 缓解：采用“每 task 子进程/可杀死执行”或“插件层超时”策略之一；实现阶段需选型并写入 spec（见 Open Questions）。

## Migration Plan
1. 第一阶段（兼容但不 fallback）：
   - 保留现有 API 形状，但当 Redis 不可用时直接失败
   - worker 端补齐 retry/timeout/status
2. 第二阶段（移除 legacy 执行）：
   - 移除 `SyncTaskManager` 内存队列与线程池 worker loop
   - `SyncTaskManager` 仅保留历史查询/ClickHouse 读写（如仍需要）
3. 部署：
   - docker/compose/k8s 中增加 Redis（如果尚未包含）
   - worker 进程独立部署（生产环境），本地可选自动拉起

## Open Questions
- **Timeout 实现**：
  - A) worker 为每个 task 开子进程并 join(timeout)，超时 kill（更可靠）
  - B) 强依赖 requests/tushare 超时 + 插件自身超时配置（实现简单但不完全可靠）

- **Retry 的“同 task_id 复用”还是“新 task_id”**：
  - 建议：自动重试复用同 task_id（attempt++），手动重试创建新 task_id（便于审计）

- **Execution 聚合统计**：attempt 失败是否计入 execution failed_plugins？建议仅当 attempts exhausted 后再计入失败。
