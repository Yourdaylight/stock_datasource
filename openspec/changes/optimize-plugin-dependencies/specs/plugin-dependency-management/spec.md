# plugin-dependency-management Specification

## Purpose
完善插件依赖关系声明和执行前检查机制，确保数据获取的正确顺序和完整性。

## ADDED Requirements

### Requirement: Plugin Dependency Declaration
所有数据获取插件 SHALL 正确声明其依赖的前置插件。

#### Scenario: Stock Daily 插件依赖声明
- **GIVEN** `tushare_daily` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回 `["tushare_stock_basic"]`
- **AND** 表示需要先同步股票基础信息才能获取日线数据

#### Scenario: Stock Daily Basic 插件依赖声明
- **GIVEN** `tushare_daily_basic` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回 `["tushare_stock_basic"]`

#### Scenario: Adj Factor 插件依赖声明
- **GIVEN** `tushare_adj_factor` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回 `["tushare_stock_basic"]`

#### Scenario: Index Weight 插件依赖声明
- **GIVEN** `tushare_index_weight` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回 `["tushare_index_basic"]`

#### Scenario: Index Factor 插件依赖声明
- **GIVEN** `tushare_idx_factor_pro` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回 `["tushare_index_basic"]`

#### Scenario: Basic 插件无依赖
- **GIVEN** `tushare_stock_basic`, `tushare_etf_basic`, `tushare_index_basic` 插件
- **WHEN** 调用 `get_dependencies()`
- **THEN** 返回空列表 `[]`
- **AND** 表示这些是基础插件，无前置依赖

### Requirement: Plugin Data Existence Check
每个插件 SHALL 提供检查其数据是否存在的方法。

#### Scenario: 检查插件数据是否存在
- **GIVEN** 任意已注册的插件
- **WHEN** 调用 `has_data()`
- **THEN** 返回 `True` 如果对应数据表有数据
- **AND** 返回 `False` 如果数据表为空或不存在

#### Scenario: Basic 插件数据检查
- **GIVEN** `tushare_stock_basic` 插件
- **WHEN** 调用 `has_data()`
- **THEN** 检查 `dim_security` 表是否有股票数据
- **AND** 返回相应的布尔值

#### Scenario: Index Basic 插件数据检查
- **GIVEN** `tushare_index_basic` 插件
- **WHEN** 调用 `has_data()`
- **THEN** 检查 `dim_index_basic` 表是否有指数数据
- **AND** 返回相应的布尔值

### Requirement: Dependency Check Before Execution
`PluginManager` SHALL 在执行插件前检查依赖是否满足。

#### Scenario: 检查依赖状态
- **GIVEN** 用户请求执行 `tushare_daily` 插件
- **WHEN** 调用 `check_dependencies('tushare_daily')`
- **THEN** 返回 `DependencyCheckResult` 对象
- **AND** `satisfied=True` 如果 `tushare_stock_basic` 有数据
- **AND** `satisfied=False` 如果 `tushare_stock_basic` 无数据
- **AND** `missing_data` 包含缺失数据的插件名称和原因

#### Scenario: 依赖满足时执行插件
- **GIVEN** `tushare_stock_basic` 已有数据
- **WHEN** 执行 `tushare_daily` 插件
- **THEN** 插件正常执行
- **AND** 返回执行结果

#### Scenario: 依赖不满足时拒绝执行
- **GIVEN** `tushare_stock_basic` 无数据
- **AND** `auto_run_deps=False`
- **WHEN** 执行 `tushare_daily` 插件
- **THEN** 抛出 `DependencyNotSatisfiedError` 异常
- **AND** 异常信息包含缺失的依赖列表
- **AND** 提示用户先执行依赖插件

#### Scenario: 自动执行依赖插件
- **GIVEN** `tushare_stock_basic` 无数据
- **AND** `auto_run_deps=True`
- **WHEN** 执行 `execute_with_dependencies('tushare_daily', auto_run_deps=True)`
- **THEN** 系统先执行 `tushare_stock_basic` 插件
- **AND** 依赖执行成功后执行 `tushare_daily` 插件
- **AND** 返回包含所有执行结果的汇总

### Requirement: Dependency Graph Query
系统 SHALL 支持查询插件依赖关系图。

#### Scenario: 获取依赖关系图
- **GIVEN** 所有插件已注册
- **WHEN** 调用 `get_dependency_graph()`
- **THEN** 返回字典格式的依赖关系图
- **AND** 格式为 `{plugin_name: [dependency_list]}`

#### Scenario: 获取单个插件依赖链
- **GIVEN** 插件可能有多级依赖
- **WHEN** 调用 `get_dependency_chain('plugin_name')`
- **THEN** 返回该插件的完整依赖链（按执行顺序）
- **AND** 支持检测循环依赖

## MODIFIED Requirements

### Requirement: Plugin Info Enhancement
`PluginManager.get_plugin_info()` SHALL 包含依赖状态信息。

#### Scenario: 获取插件信息含依赖状态
- **GIVEN** 用户请求插件列表
- **WHEN** 调用 `get_plugin_info()`
- **THEN** 每个插件信息包含:
  - `dependencies`: 依赖的插件列表
  - `dependencies_satisfied`: 依赖是否满足
  - `missing_dependencies`: 缺失的依赖列表

### Requirement: Sync Trigger API Enhancement
数据同步触发 API SHALL 返回依赖检查结果。

#### Scenario: 触发同步时依赖未满足
- **GIVEN** 用户通过 API 触发 `tushare_daily` 同步
- **AND** `tushare_stock_basic` 无数据
- **WHEN** 调用 `POST /api/datamanage/sync/trigger`
- **THEN** 返回 HTTP 400 错误
- **AND** 响应体包含:
  - `error`: "dependencies_not_satisfied"
  - `missing`: ["tushare_stock_basic"]
  - `message`: "请先同步股票基础信息"

#### Scenario: 获取插件依赖状态
- **GIVEN** 用户需要查看插件依赖
- **WHEN** 调用 `GET /api/datamanage/plugins/{name}/check-dependencies`
- **THEN** 返回依赖检查结果
- **AND** 包含 `satisfied`, `missing_dependencies`, `missing_data` 字段

## Error Handling

### Requirement: Dependency Error Messages
系统 SHALL 提供清晰的依赖相关错误信息。

#### Scenario: 依赖未满足错误
- **GIVEN** 插件依赖未满足
- **WHEN** 尝试执行插件
- **THEN** 错误信息格式为:
  ```
  Plugin 'tushare_daily' dependencies not satisfied.
  Missing: tushare_stock_basic (no data in dim_security).
  Please run 'tushare_stock_basic' first.
  ```

#### Scenario: 循环依赖检测
- **GIVEN** 插件配置存在循环依赖
- **WHEN** 系统检测依赖关系
- **THEN** 抛出 `CircularDependencyError` 异常
- **AND** 异常信息包含循环依赖链
