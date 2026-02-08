## Context

当前系统有两套互相独立的调度机制，且均未真正生效：

| 调度器 | 文件 | 技术栈 | 状态 |
|--------|------|--------|------|
| `DataSyncScheduler` | `tasks/data_sync_scheduler.py` | `schedule` 库 + threading | 默认 `enabled=False`；应用启动时未调用 `start()`；需手动 API 触发 |
| `ScheduleService` | `modules/datamanage/schedule_service.py` | 无定时机制 | 仅提供 `trigger_now()` 手动触发；有完善的执行记录/重试/停止能力 |

此外 `enhance-data-management` 遗留了"每日16:00缺失检测（APScheduler）"的未完成任务。

### 架构问题

1. **旧调度器职责过窄**：`DataSyncScheduler` 直接调用 `sync_task_manager.create_task()`，绕过了 `ScheduleService` 的依赖排序、执行记录、插件级开关等能力。
2. **新调度服务无定时驱动**：`ScheduleService` 功能完善但没有定时引擎驱动，只能被 API 手动触发。
3. **全量同步无差别重跑**：当用户触发全量同步时，所有数据从头拉取，没有先检测缺什么再精准补数的智能策略。
4. **启动时无自动调度**：`http_server.py` 的 `lifespan` 只启动了 `SyncTaskManager`，未启动任何定时调度器。

## Goals / Non-Goals

### Goals
- 统一为一套调度系统，以 `ScheduleService` 为核心，APScheduler 为定时引擎
- 应用启动时自动启动定时调度，无需手动 API 触发
- 实现智能补数：每日调度前先检测 DB 缺失，精准补数而非全量重跑
- 实现每日 16:00 定时缺失检测任务
- 删除旧版 `DataSyncScheduler` 和 `schedule` 库依赖

### Non-Goals
- 不实现分布式调度（单进程 APScheduler 即可）
- 不修改现有的任务执行引擎（`SyncTaskManager` + Redis Queue）
- 不修改前端调度配置 UI（复用现有 `ScheduleService` 的 API）
- 不实现自动修复（仅检测+创建补数任务，不做数据纠正）

## Decisions

### Decision 1: 以 ScheduleService 为核心，APScheduler 为定时引擎

**选择**：保留 `ScheduleService` 作为核心调度服务，引入 APScheduler `BackgroundScheduler` 作为定时触发引擎。

**替代方案**：
- A) 保留旧版 `DataSyncScheduler` + `schedule` 库 → 功能过于简单，无法支持智能补数和执行记录
- B) 使用 Celery Beat → 过重，引入 broker 依赖，当前规模不需要
- C) 使用 `asyncio` 定时循环 → 需要手动管理任务调度，不如 APScheduler 成熟

**理由**：`ScheduleService` 已有完善的插件级开关、依赖排序、执行记录、重试/停止等能力。APScheduler 轻量且功能完备（cron 触发、misfire 处理、持久化支持），是 Python 生态中成熟的定时调度库。

### Decision 2: 统一调度器 UnifiedScheduler

新建 `tasks/unified_scheduler.py`，职责：

```
UnifiedScheduler
├── 定时任务1: daily_sync_job (默认 18:00)
│   └── 调用 ScheduleService.trigger_now(is_manual=False)
├── 定时任务2: missing_data_check_job (默认 16:00)
│   └── 调用 data_manage_service.detect_missing_data()
├── 定时任务3: smart_backfill_job (默认 18:30, daily_sync 完成后)
│   └── 检测缺失 → 判断策略 → 创建 backfill 任务
└── 配置同步: 从 ScheduleService.get_config() 读取时间/频率/开关
```

### Decision 3: 智能补数策略

在 `ScheduleService.trigger_now()` 中增加前置缺失扫描步骤：

```
trigger_now(smart_backfill=True)
  ├── Step 1: 调用 detect_missing_data() 获取各插件缺失日期
  ├── Step 2: 对每个启用的插件
  │   ├── 无缺失 → 创建 incremental 任务（仅当天）
  │   ├── 缺失 ≤ 3天 → 创建 backfill 任务（精准补缺失日期）
  │   └── 缺失 > 3天 → 标记为异常，记录告警日志，不自动全量
  └── Step 3: 记录执行记录，含补数详情
```

**阈值配置**（可在 `runtime_config.json` 的 `scheduler` 段中配置）：
- `auto_backfill_max_days`: 3（自动补数最大天数，超过则需人工干预）
- `smart_backfill_enabled`: true（是否启用智能补数）

### Decision 4: 应用启动时自动启动

在 `http_server.py` 的 `lifespan` 中，`SyncTaskManager.start()` 之后，自动启动 `UnifiedScheduler`。调度器读取 `ScheduleService.get_config()` 中的 `enabled` 开关，如果为 `true` 则注册定时任务。

**启动顺序**：
1. SyncTaskManager（延迟 8s）
2. UnifiedScheduler（延迟 15s，确保 SyncTaskManager 就绪）

### Decision 5: 配置统一管理

所有调度配置统一存储在 `runtime_config.json` 的 `scheduler` 段：

```json
{
  "scheduler": {
    "enabled": true,
    "execute_time": "18:00",
    "frequency": "weekday",
    "skip_non_trading_days": true,
    "missing_check_time": "16:00",
    "smart_backfill_enabled": true,
    "auto_backfill_max_days": 3
  }
}
```

现有的 `ScheduleService.update_config()` API 继续作为配置入口，`UnifiedScheduler` 监听配置变更并动态调整定时任务。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| APScheduler 进程内运行，重启后定时任务丢失 | 启动时自动重新注册所有任务；使用 `misfire_grace_time` 处理错过的任务 |
| 智能补数误判（如数据源本身无当天数据） | 设置 `auto_backfill_max_days` 阈值，超过阈值不自动补数；增量同步使用交易日历校验 |
| 删除旧调度器可能影响依赖旧 API 的代码 | 旧调度器 API（`/scheduler/start`、`/scheduler/status`）重定向到新系统；保留 `get_data_sync_scheduler()` 函数作为兼容层 |
| 缺失检测和补数同时运行造成资源竞争 | 16:00 只做检测；18:00 做同步+补数；时间错开避免竞争 |

## Migration Plan

1. **Phase 1**：新增 `UnifiedScheduler`，同时保留旧版 `DataSyncScheduler`（标记为 deprecated）
2. **Phase 2**：修改 `http_server.py` 启动 `UnifiedScheduler`，旧调度器 API 返回 deprecated 提示
3. **Phase 3**：确认新调度器稳定后，删除 `DataSyncScheduler` 和 `schedule` 库依赖

## Open Questions

1. 是否需要在前端增加"智能补数"的独立入口按钮？（建议：Phase 2，先通过调度器自动执行）
2. 是否需要将缺失检测结果推送到通知系统（如邮件/webhook）？（建议：Phase 2）
