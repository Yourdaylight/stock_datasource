# Change: 统一数据调度架构 — 合并调度系统、智能补数与自动启动

## Why

当前系统中数据调度存在三个关键问题：

1. **两套调度系统并存但均未生效**：旧版 `DataSyncScheduler`（基于 `schedule` 库）默认禁用且未在应用启动时启动；新版 `ScheduleService` 只提供 `trigger_now()` 手动触发，没有定时轮询能力。结果是系统从未自动执行过任何定时同步任务。
2. **全量更新缺乏智能规划**：全量同步需要用户手动触发、耗时长且无差别全量重跑。缺少"先查 DB 缺什么、再精准补数"的自动化流程。
3. **定时缺失检测未实现**：`enhance-data-management` 的 tasks.md 中 `2.4 每日16:00定时检测任务（APScheduler）` 至今未完成，无法在数据窗口期前发现缺失。

此外，三个已有 change（`enhance-data-management`、`add-predefined-plugin-groups`、`add-etf-data-plugins`）中与调度相关的 spec 散落在各处，存在职责重叠和冗余。本 change 将这些调度相关的能力合并为一个统一 spec，消除冗余。

## What Changes

### 核心变更

- **删除** 旧版 `DataSyncScheduler`（`tasks/data_sync_scheduler.py`），移除 `schedule` 库依赖
- **新增** `UnifiedScheduler` 统一调度器，基于 APScheduler，在应用启动时自动启动
- **新增** 智能补数策略：每日调度前先检测 DB 缺失，根据缺失程度自动决定增量/回填/告警
- **新增** 每日 16:00 定时缺失检测任务（填补 `enhance-data-management` 遗留空缺）
- **修改** `ScheduleService.trigger_now()` 增加前置缺失扫描逻辑
- **修改** `http_server.py` lifespan 中自动启动 `UnifiedScheduler`
- **合并** 三个已有 change 中关于调度频率配置、插件组合触发、ETF 插件调度的 spec 要求，统一到 `unified-data-scheduler` capability

### 不变更

- 不修改 `SyncTaskManager` 的任务创建/执行/队列机制
- 不修改预定义插件组合的 CRUD 和前端展示逻辑
- 不修改 ETF 插件的 ETL 逻辑
- 不修改现有的手动触发 API

## Impact

### Affected Specs
- `unified-data-scheduler`（新增 — 合并调度相关 Requirements）
- `data-management`（MODIFIED — 移除调度相关 Requirements，保留数据检测/任务管理/插件状态等）
- `predefined-plugin-groups`（MODIFIED — 移除调度执行相关 Requirements，保留组合配置/保护/展示）

### Affected Code
- `src/stock_datasource/tasks/data_sync_scheduler.py` — 删除（旧版调度器）
- `src/stock_datasource/tasks/unified_scheduler.py` — 新增（统一调度器）
- `src/stock_datasource/modules/datamanage/schedule_service.py` — 修改（增加智能补数前置逻辑）
- `src/stock_datasource/modules/datamanage/service.py` — 修改（暴露缺失检测供调度器调用）
- `src/stock_datasource/services/http_server.py` — 修改（lifespan 中启动 UnifiedScheduler）
- `src/stock_datasource/modules/datamanage/router.py` — 修改（调度器 API 统一到 ScheduleService）

### Dependencies
- `apscheduler>=3.10` — 替换 `schedule` 库
- 依赖 `ods_trade_calendar` 表提供交易日历数据
- 依赖 `ScheduleService` 现有的插件配置和执行记录基础设施
