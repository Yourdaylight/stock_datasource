# Spec Delta: schedule-management

## ADDED Requirements

### Requirement: 全局调度配置
系统 MUST 提供全局定时调度配置功能，支持启用/禁用定时调度、配置执行时间和同步选项。

#### Scenario: 获取调度配置
- **WHEN** 管理员请求获取调度配置
- **THEN** 系统返回当前调度配置，包括启用状态、Cron表达式、可选依赖设置和非交易日跳过设置

#### Scenario: 更新调度配置
- **WHEN** 管理员更新调度配置（如修改执行时间为每天18:00）
- **THEN** 系统保存配置并在下次调度时使用新配置

#### Scenario: 禁用定时调度
- **WHEN** 管理员将调度配置的 enabled 设置为 false
- **THEN** 系统停止自动执行定时同步任务

---

### Requirement: 插件调度配置
系统 MUST 支持为每个插件单独配置是否加入定时任务和是否启用全量扫描。

#### Scenario: 获取插件调度配置列表
- **WHEN** 管理员请求获取插件调度配置列表
- **THEN** 系统返回所有插件的调度配置，包括插件名称、是否加入定时任务、是否全量扫描

#### Scenario: 启用插件定时同步
- **WHEN** 管理员将某插件的 schedule_enabled 设置为 true
- **THEN** 该插件将在定时调度执行时被包含在同步队列中

#### Scenario: 禁用插件定时同步
- **WHEN** 管理员将某插件的 schedule_enabled 设置为 false
- **THEN** 该插件将不会在定时调度执行时被同步

#### Scenario: 启用全量扫描
- **WHEN** 管理员将某插件的 full_scan_enabled 设置为 true
- **THEN** 定时调度执行时该插件将使用 FULL 类型任务（重新获取全部数据）

#### Scenario: 禁用全量扫描
- **WHEN** 管理员将某插件的 full_scan_enabled 设置为 false（默认）
- **THEN** 定时调度执行时该插件将使用 INCREMENTAL 类型任务（仅获取最新数据）

---

### Requirement: 调度执行
系统 MUST 按配置的时间自动执行定时调度，并按插件依赖顺序同步数据。

#### Scenario: 交易日自动执行
- **WHEN** 到达配置的执行时间且当天为交易日
- **THEN** 系统自动获取启用的插件列表，按依赖顺序创建同步任务

#### Scenario: 非交易日跳过
- **WHEN** 到达配置的执行时间但当天为非交易日，且 skip_non_trading_days 为 true
- **THEN** 系统跳过本次执行，不创建任何同步任务

#### Scenario: 按依赖顺序执行
- **WHEN** 调度执行时存在多个待同步插件
- **THEN** 系统按依赖关系拓扑排序：basic 插件 → primary 插件 → derived/auxiliary 插件

#### Scenario: 手动触发调度
- **WHEN** 管理员点击"立即执行一次"按钮
- **THEN** 系统立即执行一次调度（不等待 Cron 时间），创建同步任务

---

### Requirement: 调度执行历史
系统 MUST 记录调度执行历史，供管理员查看和排查问题。

#### Scenario: 查看执行历史
- **WHEN** 管理员请求查看调度执行历史
- **THEN** 系统返回最近的调度执行记录，包括执行时间、状态、涉及的插件数量和任务ID

#### Scenario: 执行失败记录
- **WHEN** 调度执行过程中某个插件同步失败
- **THEN** 系统记录失败信息，但继续执行其他不依赖该插件的任务

---

### Requirement: 插件分类筛选
系统 MUST 支持按市场分类（A股/港股/指数/ETF）筛选插件列表。

#### Scenario: 按 A股 分类筛选
- **WHEN** 管理员选择 "A股" 分类筛选
- **THEN** 系统仅显示 category 为 cn_stock 的插件

#### Scenario: 按港股分类筛选
- **WHEN** 管理员选择 "港股" 分类筛选
- **THEN** 系统仅显示 category 为 hk_stock 的插件

#### Scenario: 按指数分类筛选
- **WHEN** 管理员选择 "指数" 分类筛选
- **THEN** 系统仅显示 category 为 index 的插件

#### Scenario: 按 ETF 分类筛选
- **WHEN** 管理员选择 "ETF基金" 分类筛选
- **THEN** 系统仅显示 category 为 etf_fund 的插件

---

### Requirement: 操作说明显示
系统 MUST 在关键操作位置显示操作说明和帮助提示，帮助用户理解功能。

#### Scenario: 调度面板操作说明
- **WHEN** 管理员打开调度管理面板
- **THEN** 系统显示操作说明，包括定时调度的工作原理、执行顺序和全量扫描建议

#### Scenario: 定时任务开关提示
- **WHEN** 管理员将鼠标悬停在"加入定时任务"开关上
- **THEN** 系统显示 Tooltip 说明："启用后，该插件将加入每日自动同步队列"

#### Scenario: 全量扫描开关提示
- **WHEN** 管理员将鼠标悬停在"全量扫描"开关上
- **THEN** 系统显示 Tooltip 说明："开启后重新获取全部数据，而非仅获取最新数据"
