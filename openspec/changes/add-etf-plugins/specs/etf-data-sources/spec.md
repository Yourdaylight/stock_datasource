# Capability: ETF Data Sources

ETF数据源模块负责获取和维护指数相关的各类数据，包括技术因子、基础信息和成分权重。

## ADDED Requirements

### Requirement: 指数技术因子数据获取

系统 SHALL 提供指数技术因子数据的获取和存储功能。

- 系统 SHALL 从TuShare API获取指数技术因子数据
- 系统 SHALL 支持100+技术指标字段（MACD、KDJ、RSI、BOLL等）
- 系统 SHALL 每日更新指数技术因子数据
- 系统 SHALL 按月分区存储数据以提高查询性能
- 系统 SHALL 支持指数代码和交易日期的范围查询

#### Scenario: 获取单日技术因子数据

- **GIVEN** 插件 `tushare_idx_factor_pro` 已初始化
- **AND** 请求日期为 `2026-01-10`
- **WHEN** 系统执行 `extract_data(trade_date='20260110')`
- **THEN** 系统从TuShare API调用 `idx_factor_pro` 接口
- **AND** 返回包含约100个技术指标的DataFrame
- **AND** 数据包含 `ts_code`、`trade_date` 等基础字段

#### Scenario: 验证技术因子数据

- **GIVEN** 提取的技术因子数据
- **WHEN** 系统执行 `validate_data()`
- **THEN** 系统检查必需字段 `ts_code`、`trade_date`、`close` 存在
- **AND** 系统检查价格关系 `high >= low`
- **AND** 系统返回验证结果 `True` 或 `False`

#### Scenario: 加载技术因子数据

- **GIVEN** 验证通过的技术因子数据
- **WHEN** 系统执行 `load_data()`
- **THEN** 系统将数据插入 `ods_idx_factor_pro` 表
- **AND** 数据按月分区 `toYYYYMM(trade_date)`
- **AND** 相同(ts_code, trade_date)的数据保留最新版本

#### Scenario: 查询技术因子数据

- **GIVEN** `ods_idx_factor_pro` 表包含数据
- **WHEN** 用户查询特定指数和日期的技术因子
- **THEN** 系统返回该指数在该日期的所有技术指标
- **AND** 包含MACD、KDJ、RSI等指标值

---

### Requirement: 指数基础信息管理

系统 SHALL 提供指数基础信息的管理功能。

- 系统 SHALL 从TuShare API获取指数基础信息
- 系统 SHALL 支持全量初始化和增量更新
- 系统 SHALL 存储指数代码、名称、市场、发布方等信息
- 系统 SHALL 每周或每月检查指数信息更新

#### Scenario: 初始化指数基础信息

- **GIVEN** 插件 `tushare_index_basic` 首次运行
- **WHEN** 系统执行 `extract_data()`
- **THEN** 系统从TuShare API调用 `index_basic` 接口
- **AND** 获取所有市场（SSE/SZSE/CSI/SW等）的指数列表
- **AND** 返回包含指数代码、名称、全称、市场等信息的DataFrame

#### Scenario: 验证指数基础信息

- **GIVEN** 提取的指数基础信息
- **WHEN** 系统执行 `validate_data()`
- **THEN** 系统检查必需字段 `ts_code`、`name`、`market` 存在
- **AND** 系统检查 `ts_code` 格式正确（如 000300.SH）
- **AND** 系统返回验证结果

#### Scenario: 加载指数基础信息

- **GIVEN** 验证通过的指数基础信息
- **WHEN** 系统执行 `load_data()`
- **THEN** 系统将数据插入 `dim_index_basic` 维度表
- **AND** 相同 `ts_code` 的数据保留最新版本

#### Scenario: 增量更新指数信息

- **GIVEN** 系统已存在指数基础信息
- **AND** TuShare API中新增了指数
- **WHEN** 系统执行增量更新
- **THEN** 系统只更新新增或变化的指数信息
- **AND** 未变化的指数不重复写入

#### Scenario: 查询指数基础信息

- **GIVEN** `dim_index_basic` 表包含数据
- **WHEN** 用户查询指数代码 `000300.SH`
- **THEN** 系统返回该指数的基础信息
- **AND** 包含指数名称、市场、发布方、类别等信息

---

### Requirement: 指数成分和权重管理

系统 SHALL 提供指数成分和权重数据的管理功能。

- 系统 SHALL 从TuShare API获取指数成分和权重数据
- 系统 SHALL 按月更新指数成分权重
- 系统 SHALL 支持按指数代码和日期范围查询
- 系统 SHALL 跟踪成分权重变化历史

#### Scenario: 获取月度指数成分权重

- **GIVEN** 插件 `tushare_index_weight` 运行
- **AND** 指定指数代码 `000300.SZ` 和日期范围 `20260101` 到 `20260131`
- **WHEN** 系统执行 `extract_data(index_code='000300.SZ', start_date='20260101', end_date='20260131')`
- **THEN** 系统从TuShare API调用 `index_weight` 接口
- **AND** 返回沪深300指数在该月的所有成分股及权重
- **AND** 数据包含 `index_code`、`con_code`、`trade_date`、`weight` 字段

#### Scenario: 验证指数成分权重数据

- **GIVEN** 提取的指数成分权重数据
- **WHEN** 系统执行 `validate_data()`
- **THEN** 系统检查必需字段 `index_code`、`con_code`、`trade_date`、`weight` 存在
- **AND** 系统检查权重值在合理范围内（0-100）
- **AND** 系统返回验证结果

#### Scenario: 加载指数成分权重

- **GIVEN** 验证通过的指数成分权重数据
- **WHEN** 系统执行 `load_data()`
- **THEN** 系统将数据插入 `ods_index_weight` 表
- **AND** 数据按月分区 `toYYYYMM(trade_date)`
- **AND** 相同(index_code, con_code, trade_date)的数据保留最新版本

#### Scenario: 查询指数成分

- **GIVEN** `ods_index_weight` 表包含数据
- **WHEN** 用户查询指数 `000300.SZ` 在 `2026-01-10` 的成分
- **THEN** 系统返回该指数在指定日期的所有成分股
- **AND** 返回每个成分股的权重值

#### Scenario: 追踪成分权重变化

- **GIVEN** 指数成分权重数据包含多个日期
- **WHEN** 用户查询成分股权重变化历史
- **THEN** 系统返回该成分股在不同日期的权重
- **AND** 可以分析权重增减变化

---

### Requirement: 插件API限流

系统 SHALL 遵循TuShare API的限流规则。

- 系统 SHALL 为每个插件配置独立的rate_limit
- 系统 SHALL 在API调用间添加延迟
- 系统 SHALL 实现失败重试机制
- 系统 SHALL 记录API调用日志

#### Scenario: idx_factor_pro限流

- **GIVEN** 插件 `tushare_idx_factor_pro` 的rate_limit为30
- **WHEN** 系统连续调用API
- **THEN** 系统在两次调用间等待至少2秒（60/30=2秒）
- **AND** 不超过每分钟30次的限制

#### Scenario: API调用失败重试

- **GIVEN** API调用失败（网络错误或超时）
- **WHEN** 系统检测到失败
- **THEN** 系统重试最多3次
- **AND** 使用指数退避策略（1s, 2s, 4s）
- **AND** 记录失败日志

---

### Requirement: 插件注册与发现

系统 SHALL 自动注册和发现新增的ETF插件。

- 系统 SHALL 在 `plugins/__init__.py` 中注册新插件
- 系统 SHALL 支持通过CLI命令调用插件
- 系统 SHALL 在数据管理界面显示插件信息
- 系统 SHALL 通过MCP协议暴露插件查询接口

#### Scenario: 注册新插件

- **GIVEN** 插件文件已创建
- **WHEN** 系统启动时加载插件
- **THEN** 系统从 `tushare_idx_factor_pro` 目录导入 `TuShareIdxFactorProPlugin`
- **AND** 插件管理器识别插件名称 `tushare_idx_factor_pro`

#### Scenario: CLI命令调用

- **GIVEN** 插件已注册
- **WHEN** 用户执行 `uv run cli.py ingest-daily --plugin tushare_idx_factor_pro --date 20260110`
- **THEN** 系统调用该插件的 `run()` 方法
- **AND** 返回执行结果

#### Scenario: 数据管理界面显示

- **GIVEN** 插件已注册
- **WHEN** 用户打开数据管理界面
- **THEN** 系统在插件列表中显示 `tushare_idx_factor_pro`
- **AND** 显示插件描述、调度频率、最新数据日期

#### Scenario: MCP查询接口

- **GIVEN** 插件已注册
- **WHEN** 用户通过MCP协议查询数据
- **THEN** 系统调用插件的 `service.py` 提供的查询方法
- **AND** 返回查询结果

---

### Requirement: 数据质量控制

系统 SHALL 确保ETF数据的质量和完整性。

- 系统 SHALL 验证必需字段不为空
- 系统 SHALL 验证数值类型字段的合理性
- 系统 SHALL 验证日期格式正确
- 系统 SHALL 记录数据质量指标

#### Scenario: 验证技术因子数值合理性

- **GIVEN** 技术因子数据包含价格相关指标
- **WHEN** 系统验证数据
- **THEN** 系统检查 `high >= low`
- **AND** 系统检查 `close` 在 `high` 和 `low` 之间
- **AND** 不合理数据被拒绝并记录日志

#### Scenario: 验证权重值范围

- **GIVEN** 指数成分权重数据
- **WHEN** 系统验证数据
- **THEN** 系统检查 `weight` 值在 0-100 范围内
- **AND** 超出范围的值被拒绝

#### Scenario: 验证指数代码格式

- **GIVEN** 指数基础信息数据
- **WHEN** 系统验证数据
- **THEN** 系统检查 `ts_code` 格式为 `6位数字.市场代码`
- **AND** 市场代码为 `.SH` 或 `.SZ` 或 `.SI`
- **AND** 格式错误的记录被拒绝

#### Scenario: 记录数据质量指标

- **GIVEN** 插件执行完成
- **WHEN** 系统记录执行日志
- **THEN** 系统记录提取记录数
- **AND** 系统记录验证通过/失败的记录数
- **AND** 系统记录加载的记录数
