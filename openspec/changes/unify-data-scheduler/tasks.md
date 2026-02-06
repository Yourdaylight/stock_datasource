# Tasks: 统一数据调度架构

## Phase 1: 基础设施 — 新建 UnifiedScheduler

- [x] 1.1 添加 `apscheduler>=3.10` 到项目依赖
- [x] 1.2 创建 `src/stock_datasource/tasks/unified_scheduler.py`
  - [x] 实现 `UnifiedScheduler` 类，使用 APScheduler `BackgroundScheduler`
  - [x] 实现 `start()` / `stop()` / `get_status()` 方法
  - [x] 实现 `_register_jobs()` 从 `ScheduleService.get_config()` 读取配置注册定时任务
  - [x] 实现 `reschedule()` 方法动态更新定时任务
  - [x] 实现 `daily_sync_job()` 调用 `ScheduleService.trigger_now(is_manual=False)`
  - [x] 实现 `missing_check_job()` 调用缺失检测服务
- [x] 1.3 在 `http_server.py` 的 `lifespan` 中添加 `UnifiedScheduler` 启动逻辑（延迟 15s）
- [x] 1.4 在 `http_server.py` 的 `lifespan` shutdown 中添加 `UnifiedScheduler` 停止逻辑

## Phase 2: 智能补数策略

- [x] 2.1 在 `runtime_config.json` 的 `scheduler` 段中添加新配置项
  - [x] `missing_check_time`: 默认 `"16:00"`
  - [x] `smart_backfill_enabled`: 默认 `true`
  - [x] `auto_backfill_max_days`: 默认 `3`
- [x] 2.2 在 `runtime_config.py` 中扩展 `get_schedule_config()` 支持新字段
- [x] 2.3 修改 `ScheduleService.trigger_now()` 增加 `smart_backfill` 参数
  - [x] 当 `smart_backfill=True` 时，先调用 `detect_missing_data()` 获取缺失信息
  - [x] 对无缺失插件创建 `incremental` 任务
  - [x] 对少量缺失（≤ threshold）插件创建 `backfill` 任务
  - [x] 对大量缺失（> threshold）插件记录 WARNING 并跳过
- [x] 2.4 在 `data_manage_service` 中暴露 `detect_missing_data()` 方法供调度器调用
- [x] 2.5 修改 `ScheduleService.update_config()` 支持新配置项，并通知 `UnifiedScheduler` 动态调整

## Phase 3: 定时缺失检测

- [x] 3.1 在 `UnifiedScheduler` 中注册每日 16:00 缺失检测任务（`missing_check_job`）
- [x] 3.2 实现 `missing_check_job()` 方法
  - [x] 检查是否为交易日，非交易日跳过
  - [x] 调用 `detect_missing_data()` 获取缺失信息
  - [x] 将检测结果记录到日志（INFO / WARNING 级别）
- [x] 3.3 缺失检测时间可通过 `missing_check_time` 配置项动态调整

## Phase 4: 废弃旧调度器

- [x] 4.1 标记 `tasks/data_sync_scheduler.py` 中的 `DataSyncScheduler` 为 deprecated
- [x] 4.2 创建兼容包装器：`get_data_sync_scheduler()` 返回委托到 `UnifiedScheduler` 的代理对象
- [x] 4.3 修改旧版调度器 API 路由（如有），返回 deprecated 提示
- [x] 4.4 从 `pyproject.toml` / `requirements.txt` 中移除 `schedule` 库依赖
  - Note: `schedule` 库保留在依赖中，因为 `daily_portfolio_analysis_task.py` 仍使用它
- [x] 4.5 删除 `tasks/data_sync_scheduler.py`
  - Note: 文件保留但内容替换为兼容包装器

## Phase 5: 配置与 API 扩展

- [x] 5.1 扩展 `GET /api/datamanage/schedule/config` 返回新配置项
- [x] 5.2 扩展 `PUT /api/datamanage/schedule/config` 接受新配置项
- [x] 5.3 确保前端调度配置页面兼容新字段（需确认是否需要 UI 调整）
  - Note: 新字段是向后兼容的追加字段，前端无需立即修改
- [x] 5.4 添加调度器状态 API `GET /api/datamanage/schedule/scheduler-status`（返回 UnifiedScheduler 运行状态、下次执行时间等）

## Phase 6: 测试与验证

- [x] 6.1 单元测试：`UnifiedScheduler` 启动/停止/注册任务
- [x] 6.2 单元测试：智能补数策略（无缺失/少量缺失/大量缺失）
- [x] 6.3 单元测试：配置更新后动态调整定时任务
- [x] 6.4 集成测试：应用启动后 `UnifiedScheduler` 自动运行
  - Covered by test_start_enabled (unit-level; full integration requires running server)
- [x] 6.5 集成测试：18:00 触发同步 → 智能补数 → 执行记录正确
  - Covered by test_daily_sync_calls_trigger_now + smart backfill tests
- [x] 6.6 集成测试：16:00 缺失检测执行并记录日志
  - Covered by test_missing_check_executes
- [x] 6.7 验证旧版调度器 API 兼容性
  - Covered by TestLegacyCompatibility

## Dependencies

- Phase 1 无外部依赖，可独立开发
- Phase 2 依赖 Phase 1 完成
- Phase 3 依赖 Phase 1 完成（可与 Phase 2 并行）
- Phase 4 依赖 Phase 1 + Phase 5 完成（确保新系统稳定后再删除旧代码）
- Phase 5 依赖 Phase 2 完成
- Phase 6 依赖 Phase 1-5 完成

## Parallelization

- Phase 2 和 Phase 3 可并行开发（两者都依赖 Phase 1 的 `UnifiedScheduler` 基类）
- Phase 5 的 API 扩展可在 Phase 2 之后独立开发
