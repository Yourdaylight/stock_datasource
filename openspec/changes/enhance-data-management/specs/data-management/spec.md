# Capability: Data Management

数据管理模块负责数据源监控、同步任务管理、数据质量检测和插件管理。

## ADDED Requirements

### Requirement: 基于交易日的数据缺失检测

系统 SHALL 基于交易日历检测各插件对应ODS表的数据缺失情况。

- 系统 SHALL 从 `ods_trade_calendar` 表获取交易日列表
- 系统 SHALL 仅检查 `schedule.frequency = "daily"` 的插件
- 系统 SHALL 返回每个插件的缺失日期列表
- 系统 SHALL 每日 16:00 自动执行检测
- 系统 SHALL 支持手动触发检测

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
- 系统 SHALL 支持至少3个任务并行执行
- 系统 SHALL 在单次任务涉及多个日期时，在限速允许范围内并行处理多个日期
- 系统 SHALL 根据插件配置的 `rate_limit` 动态调整日期并发数
- 系统 SHALL 实时更新任务执行进度
- 系统 SHALL 记录任务执行历史到数据库
- 系统 SHALL 保留30天的任务历史，超过30天自动清理

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

#### Scenario: 多任务并行执行

- **GIVEN** 当前有2个任务正在执行
- **AND** 用户触发第3个同步任务
- **WHEN** 系统处理新任务
- **THEN** 第3个任务立即开始执行
- **AND** 3个任务同时处于 `running` 状态

#### Scenario: 并行任务达到上限

- **GIVEN** 当前有3个任务正在执行
- **AND** 用户触发第4个同步任务
- **WHEN** 系统处理新任务
- **THEN** 第4个任务状态为 `pending`
- **AND** 等待有任务完成后自动执行

#### Scenario: 单任务多日期并行处理

- **GIVEN** 用户触发回填任务，包含日期 `['2026-01-05', '2026-01-06', '2026-01-07']`
- **AND** 插件 `rate_limit = 500`（每分钟500次）
- **WHEN** 系统执行任务
- **THEN** 系统根据限速计算并发数（如3个日期并行）
- **AND** 同时拉取多个日期的数据

#### Scenario: 限速较低时减少并发

- **GIVEN** 用户触发回填任务，包含5个日期
- **AND** 插件 `rate_limit = 60`（每分钟60次）
- **WHEN** 系统执行任务
- **THEN** 系统降低日期并发数（如1-2个日期并行）
- **AND** 确保不超过API限速

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

---

### Requirement: 插件详情查看

系统 SHALL 提供插件详情查看功能，展示插件的配置、数据结构和运行状态。

- 系统 SHALL 展示插件的 `config.json` 配置信息
- 系统 SHALL 展示插件的 `schema.json` 数据结构定义
- 系统 SHALL 展示插件的运行状态（最新数据、缺失情况）
- 系统 SHALL 以可读的方式格式化展示字段定义

#### Scenario: 查看插件详情

- **GIVEN** 用户在插件列表页面
- **AND** 点击 `tushare_daily` 行的"查看详情"按钮
- **WHEN** 系统响应点击
- **THEN** 弹出插件详情弹窗
- **AND** 展示插件基本信息（名称、版本、描述）
- **AND** 展示调度配置（频率、执行时间）
- **AND** 展示数据结构（表名、字段列表、分区键、排序键）

#### Scenario: 查看插件数据结构

- **GIVEN** 插件详情弹窗已打开
- **AND** 用户切换到"数据结构"标签
- **WHEN** 系统展示数据结构
- **THEN** 显示表名 `ods_daily`
- **AND** 显示字段列表（字段名、数据类型、是否可空、注释）
- **AND** 显示分区键 `toYYYYMM(trade_date)`
- **AND** 显示排序键 `["ts_code", "trade_date"]`

#### Scenario: 查看插件API接口信息

- **GIVEN** 插件详情弹窗已打开
- **AND** 用户切换到"接口配置"标签
- **WHEN** 系统展示接口配置
- **THEN** 显示数据源类型（tushare/akshare）
- **AND** 显示API接口名称
- **AND** 显示参数定义（如有）

---

### Requirement: 插件包导入导出（预留）

系统 SHALL 预留插件包导入导出接口，为后续AI生成插件功能做准备。

- 系统 SHALL 定义标准的插件包格式（.plugin.zip）
- 系统 SHALL 预留导出API接口
- 系统 SHALL 预留导入API接口
- 本期不实现具体功能，仅定义接口规范

#### Scenario: 导出插件包（预留）

- **GIVEN** 用户选择导出插件 `tushare_daily`
- **WHEN** 系统执行导出
- **THEN** 生成包含 manifest.json、config.json、schema.json、plugin.py 的 zip 包

#### Scenario: 导入插件包（预留）

- **GIVEN** 用户上传插件包 `custom_plugin.plugin.zip`
- **WHEN** 系统验证并导入
- **THEN** 解压并注册新插件
- **AND** 创建对应的ODS表

---

### Requirement: AI日志诊断

系统 SHALL 提供AI驱动的日志诊断功能，分析系统日志并给出修复建议。

- 系统 SHALL 读取最近的系统日志
- 系统 SHALL 识别已知的错误模式
- 系统 SHALL 为每个问题提供严重程度、类别和修复建议
- 系统 SHALL 支持按错误级别过滤日志

#### Scenario: 诊断发现配置问题

- **GIVEN** 日志中包含 "TUSHARE_TOKEN environment variable not set"
- **WHEN** 用户执行AI诊断
- **THEN** 系统返回严重程度为 `critical`
- **AND** 类别为 `config`
- **AND** 建议为 "请在.env文件中添加 TUSHARE_TOKEN=your_token"

#### Scenario: 诊断发现数据问题

- **GIVEN** 日志中包含 "No trading days found in calendar"
- **WHEN** 用户执行AI诊断
- **THEN** 系统返回严重程度为 `critical`
- **AND** 类别为 `data`
- **AND** 建议为 "请先运行交易日历插件同步数据"

#### Scenario: 系统运行正常

- **GIVEN** 日志中没有错误或警告
- **WHEN** 用户执行AI诊断
- **THEN** 系统返回摘要为 "系统运行正常，未发现明显问题"
- **AND** 建议列表为空
