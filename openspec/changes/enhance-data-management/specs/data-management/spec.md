# Capability: Data Management

数据管理模块负责数据源监控、同步任务管理、数据质量检测和插件管理。

## ADDED Requirements

### Requirement: 基于交易日的数据缺失检测

系统 SHALL 基于交易日历检测各插件对应ODS表的数据缺失情况。

- 系统 SHALL 从 `ods_trade_calendar` 表获取交易日列表
- 系统 SHALL 仅检查 `schedule.frequency = "daily"` 的插件
- 系统 SHALL 返回每个插件的缺失日期列表
- 系统 SHALL 缓存检测结果，每小时自动刷新

#### Scenario: 检测到数据缺失

- **GIVEN** 插件 `tushare_daily` 的调度频率为 `daily`
- **AND** 交易日 `2026-01-08` 是开市日
- **AND** `ods_daily` 表中不存在 `trade_date = '2026-01-08'` 的数据
- **WHEN** 用户请求数据缺失检测
- **THEN** 系统返回 `tushare_daily` 的缺失日期包含 `2026-01-08`

#### Scenario: 数据完整无缺失

- **GIVEN** 插件 `tushare_daily` 的调度频率为 `daily`
- **AND** 所有交易日都有对应数据
- **WHEN** 用户请求数据缺失检测
- **THEN** 系统返回 `tushare_daily` 的缺失日期列表为空

#### Scenario: 周更新插件不参与每日检测

- **GIVEN** 插件 `tushare_stock_basic` 的调度频率为 `weekly`
- **WHEN** 用户请求每日数据缺失检测
- **THEN** 系统不检测 `tushare_stock_basic` 的缺失情况

---

### Requirement: 同步任务管理

系统 SHALL 提供同步任务的创建、执行、状态跟踪和历史查询功能。

- 系统 SHALL 支持创建增量同步、全量同步、回填同步任务
- 系统 SHALL 实时更新任务执行进度
- 系统 SHALL 记录任务执行历史到数据库
- 系统 SHALL 支持查询最近30天的任务历史

#### Scenario: 创建增量同步任务

- **GIVEN** 用户选择插件 `tushare_daily`
- **AND** 选择同步类型为 `incremental`
- **WHEN** 用户触发同步
- **THEN** 系统创建任务并返回 `task_id`
- **AND** 任务状态为 `pending`

#### Scenario: 任务执行进度更新

- **GIVEN** 同步任务正在执行
- **AND** 已处理 500 条记录，共 1000 条
- **WHEN** 用户查询任务状态
- **THEN** 系统返回 `progress = 50`
- **AND** `records_processed = 500`

#### Scenario: 任务执行完成

- **GIVEN** 同步任务执行完成
- **WHEN** 用户查询任务状态
- **THEN** 系统返回 `status = 'completed'`
- **AND** `completed_at` 有值

#### Scenario: 任务执行失败

- **GIVEN** 同步任务执行过程中发生错误
- **WHEN** 用户查询任务状态
- **THEN** 系统返回 `status = 'failed'`
- **AND** `error_message` 包含错误信息

---

### Requirement: 插件数据状态查询

系统 SHALL 提供各插件的数据状态查询，包括最新数据日期、缺失天数、数据预览。

- 系统 SHALL 返回插件对应ODS表的最新数据日期
- 系统 SHALL 返回插件的调度频率（daily/weekly）
- 系统 SHALL 返回插件的缺失日期数量
- 系统 SHALL 提供数据预览接口

#### Scenario: 查询插件数据状态

- **GIVEN** 插件 `tushare_daily` 对应表 `ods_daily`
- **AND** 表中最新数据日期为 `2026-01-09`
- **AND** 有 2 个交易日缺失数据
- **WHEN** 用户查询插件状态
- **THEN** 系统返回 `latest_date = '2026-01-09'`
- **AND** `missing_count = 2`
- **AND** `schedule_frequency = 'daily'`

#### Scenario: 预览插件数据

- **GIVEN** 用户请求预览 `tushare_daily` 的数据
- **AND** 指定日期为 `2026-01-09`
- **WHEN** 系统查询数据
- **THEN** 返回该日期的前100条数据记录

---

### Requirement: 插件调度频率展示

系统 SHALL 在插件列表中展示各插件的调度频率和执行时间。

- 系统 SHALL 从插件 `config.json` 读取 `schedule` 配置
- 系统 SHALL 区分显示 `daily` 和 `weekly` 频率
- 系统 SHALL 显示计划执行时间

#### Scenario: 展示每日更新插件

- **GIVEN** 插件 `tushare_daily` 的 `schedule.frequency = 'daily'`
- **AND** `schedule.time = '18:00'`
- **WHEN** 用户查看插件列表
- **THEN** 显示调度频率为 "每日"
- **AND** 显示执行时间为 "18:00"

#### Scenario: 展示每周更新插件

- **GIVEN** 插件 `tushare_stock_basic` 的 `schedule.frequency = 'weekly'`
- **AND** `schedule.day_of_week = 'monday'`
- **WHEN** 用户查看插件列表
- **THEN** 显示调度频率为 "每周一"

---

### Requirement: 数据跳转展示

系统 SHALL 支持从插件列表直接跳转查看插件数据。

- 系统 SHALL 在插件行提供"查看数据"操作
- 系统 SHALL 弹出数据预览弹窗
- 系统 SHALL 支持按日期筛选数据

#### Scenario: 跳转查看插件数据

- **GIVEN** 用户在插件列表页面
- **AND** 点击 `tushare_daily` 行的"查看数据"按钮
- **WHEN** 系统响应点击
- **THEN** 弹出数据预览弹窗
- **AND** 展示 `ods_daily` 表的最新数据

#### Scenario: 按日期筛选数据

- **GIVEN** 数据预览弹窗已打开
- **AND** 用户选择日期 `2026-01-09`
- **WHEN** 用户点击筛选
- **THEN** 弹窗展示该日期的数据
