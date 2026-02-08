# Capability: Unified Data Scheduler

统一数据调度系统，负责定时数据同步、智能补数和缺失检测的自动化调度。

## ADDED Requirements

### Requirement: 统一调度器自动启动

系统 SHALL 在应用启动时自动初始化并启动统一调度器 `UnifiedScheduler`。

- 系统 SHALL 使用 APScheduler `BackgroundScheduler` 作为定时引擎
- 系统 SHALL 在 `SyncTaskManager` 就绪后启动调度器（延迟 15 秒）
- 系统 SHALL 从 `runtime_config.json` 的 `scheduler` 段读取调度配置
- 系统 SHALL 在调度器启用（`enabled=true`）时自动注册定时任务
- 系统 SHALL 在调度器禁用时不注册任何定时任务但保持调度器实例运行
- 系统 SHALL 在应用关闭时优雅停止调度器

#### Scenario: 应用启动时调度器自动启动

- **GIVEN** `runtime_config.json` 中 `scheduler.enabled = true`
- **AND** `scheduler.execute_time = "18:00"`
- **WHEN** 应用启动完成
- **THEN** `UnifiedScheduler` 自动启动
- **AND** 注册每日 18:00 数据同步任务
- **AND** 注册每日 16:00 缺失检测任务
- **AND** 日志输出 "UnifiedScheduler started with 2 jobs"

#### Scenario: 调度器禁用时不注册任务

- **GIVEN** `runtime_config.json` 中 `scheduler.enabled = false`
- **WHEN** 应用启动完成
- **THEN** `UnifiedScheduler` 实例被创建
- **AND** 不注册任何定时任务
- **AND** 日志输出 "UnifiedScheduler started (disabled, no jobs registered)"

#### Scenario: 应用关闭时优雅停止

- **GIVEN** `UnifiedScheduler` 正在运行
- **WHEN** 应用收到关闭信号
- **THEN** 调度器停止接受新任务
- **AND** 等待当前执行中的任务完成（最多 10 秒）
- **AND** 日志输出 "UnifiedScheduler stopped"

---

### Requirement: 定时数据同步

系统 SHALL 按配置的时间和频率自动触发数据同步任务。

- 系统 SHALL 支持配置每日执行时间（默认 18:00）
- 系统 SHALL 支持 `daily`（每天）和 `weekday`（工作日）两种频率
- 系统 SHALL 在 `skip_non_trading_days = true` 时跳过非交易日
- 系统 SHALL 通过 `ScheduleService.trigger_now(is_manual=False)` 执行同步
- 系统 SHALL 在调度配置变更时动态更新定时任务

#### Scenario: 交易日自动执行同步

- **GIVEN** `scheduler.enabled = true`
- **AND** `scheduler.execute_time = "18:00"`
- **AND** `scheduler.skip_non_trading_days = true`
- **AND** 当天是交易日
- **WHEN** 时钟到达 18:00
- **THEN** 系统调用 `ScheduleService.trigger_now(is_manual=False)`
- **AND** 按依赖排序为所有启用的插件创建同步任务

#### Scenario: 非交易日跳过同步

- **GIVEN** `scheduler.skip_non_trading_days = true`
- **AND** 当天是周六（非交易日）
- **WHEN** 时钟到达 18:00
- **THEN** 系统不触发同步
- **AND** 记录跳过日志 "Skipped: non-trading day"

#### Scenario: 动态更新执行时间

- **GIVEN** 调度器正在运行，执行时间为 18:00
- **WHEN** 用户通过 API 修改 `execute_time = "19:00"`
- **THEN** 调度器动态更新定时任务
- **AND** 下次执行时间变为 19:00
- **AND** 无需重启应用

---

### Requirement: 每日定时缺失检测

系统 SHALL 每日 16:00 自动执行数据缺失检测。

- 系统 SHALL 在交易日 16:00 自动触发缺失检测
- 系统 SHALL 仅检测 `schedule.frequency = "daily"` 且 `schedule_enabled = true` 的插件
- 系统 SHALL 检测结果记录到日志
- 系统 SHALL 在检测到严重缺失时记录 WARNING 级别日志
- 系统 SHALL 支持配置缺失检测时间（默认 16:00）

#### Scenario: 交易日 16:00 自动检测

- **GIVEN** `scheduler.enabled = true`
- **AND** `scheduler.missing_check_time = "16:00"`
- **AND** 当天是交易日
- **WHEN** 时钟到达 16:00
- **THEN** 系统自动执行缺失检测
- **AND** 检查所有启用的 daily 插件的数据完整性
- **AND** 日志输出检测结果摘要

#### Scenario: 检测到缺失记录告警

- **GIVEN** 缺失检测执行完毕
- **AND** 插件 `tushare_daily` 缺失 5 个交易日数据
- **WHEN** 检测结果汇总
- **THEN** 日志输出 WARNING: "tushare_daily missing 5 trading days"
- **AND** 缺失信息可通过 API `/api/datamanage/missing-data` 查询

#### Scenario: 非交易日不检测

- **GIVEN** 当天是周日
- **WHEN** 时钟到达 16:00
- **THEN** 系统跳过缺失检测

---

### Requirement: 智能补数策略

系统 SHALL 在定时同步时根据数据缺失情况智能决定同步策略。

- 系统 SHALL 在触发同步前先检测各插件的数据缺失情况
- 系统 SHALL 对无缺失的插件创建 `incremental` 任务（仅同步当天数据）
- 系统 SHALL 对缺失天数 ≤ `auto_backfill_max_days` 的插件创建 `backfill` 任务（精准补缺失日期）
- 系统 SHALL 对缺失天数 > `auto_backfill_max_days` 的插件标记为异常并记录告警
- 系统 SHALL 支持配置 `auto_backfill_max_days`（默认 3 天）
- 系统 SHALL 支持通过 `smart_backfill_enabled` 开关启用/禁用智能补数
- 系统 SHALL 在智能补数禁用时退化为普通增量同步

#### Scenario: 无缺失时执行增量同步

- **GIVEN** `smart_backfill_enabled = true`
- **AND** 插件 `tushare_daily` 无缺失数据
- **WHEN** 定时同步触发
- **THEN** 系统为 `tushare_daily` 创建 `incremental` 任务
- **AND** 任务仅同步当天交易日数据

#### Scenario: 少量缺失时自动补数

- **GIVEN** `smart_backfill_enabled = true`
- **AND** `auto_backfill_max_days = 3`
- **AND** 插件 `tushare_daily` 缺失 2 个交易日（`20260105`、`20260106`）
- **WHEN** 定时同步触发
- **THEN** 系统为 `tushare_daily` 创建 `backfill` 任务
- **AND** `trade_dates` 包含 `['20260105', '20260106']` 加上当天日期
- **AND** 日志输出 "Auto backfill: tushare_daily, 2 missing days + today"

#### Scenario: 大量缺失时标记异常

- **GIVEN** `smart_backfill_enabled = true`
- **AND** `auto_backfill_max_days = 3`
- **AND** 插件 `tushare_daily` 缺失 10 个交易日
- **WHEN** 定时同步触发
- **THEN** 系统不为 `tushare_daily` 创建自动任务
- **AND** 日志输出 WARNING: "tushare_daily missing 10 days (exceeds threshold 3), requires manual intervention"
- **AND** 执行记录中标记该插件为 `skipped_excessive_missing`

#### Scenario: 智能补数禁用时退化

- **GIVEN** `smart_backfill_enabled = false`
- **AND** 插件 `tushare_daily` 缺失 2 个交易日
- **WHEN** 定时同步触发
- **THEN** 系统为 `tushare_daily` 创建 `incremental` 任务（仅当天）
- **AND** 不执行缺失补数

---

### Requirement: 调度配置统一管理

系统 SHALL 提供统一的调度配置管理，所有调度参数存储在 `runtime_config.json` 的 `scheduler` 段。

- 系统 SHALL 支持以下配置项：
  - `enabled`: 调度器开关（默认 `false`）
  - `execute_time`: 同步执行时间（默认 `"18:00"`）
  - `frequency`: 执行频率 `"daily"` 或 `"weekday"`（默认 `"weekday"`）
  - `skip_non_trading_days`: 跳过非交易日（默认 `true`）
  - `missing_check_time`: 缺失检测时间（默认 `"16:00"`）
  - `smart_backfill_enabled`: 智能补数开关（默认 `true`）
  - `auto_backfill_max_days`: 自动补数最大天数（默认 `3`）
- 系统 SHALL 通过现有 `ScheduleService.update_config()` API 更新配置
- 系统 SHALL 在配置更新后通知 `UnifiedScheduler` 动态调整定时任务

#### Scenario: 更新配置后调度器动态调整

- **GIVEN** 调度器正在运行
- **WHEN** 用户调用 `PUT /api/datamanage/schedule/config` 修改 `execute_time = "19:30"`
- **THEN** 配置保存到 `runtime_config.json`
- **AND** `UnifiedScheduler` 动态调整同步任务时间为 19:30
- **AND** API 返回更新后的完整配置

#### Scenario: 读取调度配置含新增字段

- **WHEN** 用户调用 `GET /api/datamanage/schedule/config`
- **THEN** 返回包含所有配置项：
  ```json
  {
    "enabled": true,
    "execute_time": "18:00",
    "frequency": "weekday",
    "skip_non_trading_days": true,
    "missing_check_time": "16:00",
    "smart_backfill_enabled": true,
    "auto_backfill_max_days": 3,
    "next_run_at": "2026-02-07T18:00:00"
  }
  ```

---

### Requirement: 旧调度器废弃与兼容

系统 SHALL 废弃旧版 `DataSyncScheduler` 并提供兼容过渡。

- 系统 SHALL 删除 `tasks/data_sync_scheduler.py`
- 系统 SHALL 移除 `schedule` 库依赖
- 系统 SHALL 保留 `get_data_sync_scheduler()` 函数签名，返回兼容性包装器
- 兼容包装器 SHALL 将 `start()`/`stop()`/`get_status()` 调用委托给 `UnifiedScheduler`
- 系统 SHALL 在旧 API 路径被调用时返回 deprecated 提示和重定向信息

#### Scenario: 旧 API 调用返回 deprecated 提示

- **GIVEN** 用户调用 `POST /api/scheduler/start`（旧 API）
- **WHEN** 系统处理请求
- **THEN** 返回 HTTP 200
- **AND** 响应包含 `deprecated: true`
- **AND** 响应包含 `message: "Use /api/datamanage/schedule/config to manage scheduler"`

#### Scenario: 兼容函数委托到新调度器

- **GIVEN** 外部代码调用 `get_data_sync_scheduler().get_status()`
- **WHEN** 函数执行
- **THEN** 返回 `UnifiedScheduler` 的状态信息
- **AND** 格式与旧版兼容

## MODIFIED Requirements

### Requirement: 基于交易日的数据缺失检测

系统 SHALL 基于交易日历检测各插件对应ODS表的数据缺失情况。

- 系统 SHALL 从 `ods_trade_calendar` 表获取交易日列表
- 系统 SHALL 仅检查 `schedule.frequency = "daily"` 且 `schedule_enabled = true` 的插件
- 系统 SHALL 返回每个插件的缺失日期列表
- 系统 SHALL 每日 16:00 由 `UnifiedScheduler` 自动执行检测
- 系统 SHALL 支持手动触发检测
- 系统 SHALL 将检测结果供智能补数策略使用

#### Scenario: 检测到数据缺失

- **GIVEN** 插件 `tushare_daily` 的调度频率为 `daily`
- **AND** `schedule_enabled = true`
- **AND** 交易日 `2026-01-08` 是开市日
- **AND** `ods_daily` 表中不存在 `trade_date = '2026-01-08'` 的数据
- **WHEN** 用户请求数据缺失检测
- **THEN** 系统返回 `tushare_daily` 的缺失日期包含 `2026-01-08`

#### Scenario: 数据完整无缺失

- **GIVEN** 插件 `tushare_daily` 的调度频率为 `daily`
- **AND** 所有交易日都有对应数据
- **WHEN** 用户请求数据缺失检测
- **THEN** 系统返回 `tushare_daily` 的缺失日期列表为空

#### Scenario: 未启用调度的插件不参与检测

- **GIVEN** 插件 `tushare_rt_k` 的 `schedule_enabled = false`
- **WHEN** 用户请求每日数据缺失检测
- **THEN** 系统不检测 `tushare_rt_k` 的缺失情况
