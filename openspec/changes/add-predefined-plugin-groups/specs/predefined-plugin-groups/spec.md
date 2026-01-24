# predefined-plugin-groups Specification

## Purpose

提供预定义的插件组合，基于表依赖关系自动配置，覆盖常见的数据同步场景，用户可直接使用这些组合进行一键同步。

## ADDED Requirements

### Requirement: Predefined Plugin Groups Configuration
系统 SHALL 支持通过配置文件定义预设的插件组合。

#### Scenario: 加载预定义组合配置
- **GIVEN** 系统启动
- **AND** 存在配置文件 `config/predefined_groups.json`
- **WHEN** 系统初始化完成
- **THEN** 预定义组合配置被加载到内存
- **AND** 预定义组合可通过 API 访问

#### Scenario: 配置文件不存在时的处理
- **GIVEN** 系统启动
- **AND** 配置文件 `config/predefined_groups.json` 不存在
- **WHEN** 系统初始化完成
- **THEN** 系统正常启动
- **AND** 预定义组合列表为空
- **AND** 日志记录警告信息

### Requirement: Predefined Groups in Group List API
组合列表 API SHALL 返回预定义组合，与用户自定义组合合并显示。

#### Scenario: 获取所有组合
- **GIVEN** 存在 10 个预定义组合
- **AND** 用户创建了 2 个自定义组合
- **WHEN** 调用 `GET /api/datamanage/groups`
- **THEN** 返回 12 个组合
- **AND** 预定义组合的 `is_predefined` 为 `true`
- **AND** 用户自定义组合的 `is_predefined` 为 `false`
- **AND** 预定义组合排在列表前面

#### Scenario: 按分类筛选组合
- **GIVEN** 预定义组合包含 5 个 A股组合、2 个指数组合
- **WHEN** 调用 `GET /api/datamanage/groups?category=cn_stock`
- **THEN** 仅返回分类为 `cn_stock` 的组合
- **AND** 包括预定义和用户自定义的 A股组合

#### Scenario: 仅获取预定义组合
- **WHEN** 调用 `GET /api/datamanage/groups/predefined`
- **THEN** 仅返回预定义组合
- **AND** 不包含用户自定义组合

### Requirement: Predefined Groups Protection
预定义组合 SHALL 为只读，不可修改或删除。

#### Scenario: 尝试删除预定义组合
- **GIVEN** 存在预定义组合 `predefined_cn_stock_basic`
- **WHEN** 调用 `DELETE /api/datamanage/groups/predefined_cn_stock_basic`
- **THEN** 返回 HTTP 403 Forbidden
- **AND** 响应消息为 "Cannot delete predefined group"

#### Scenario: 尝试修改预定义组合
- **GIVEN** 存在预定义组合 `predefined_cn_stock_basic`
- **WHEN** 调用 `PUT /api/datamanage/groups/predefined_cn_stock_basic`
- **THEN** 返回 HTTP 403 Forbidden
- **AND** 响应消息为 "Cannot modify predefined group"

#### Scenario: 正常删除用户自定义组合
- **GIVEN** 用户创建了组合 `user_custom_123`
- **WHEN** 调用 `DELETE /api/datamanage/groups/user_custom_123`
- **THEN** 返回 HTTP 200 OK
- **AND** 组合被成功删除

### Requirement: Predefined Groups Execution
预定义组合 SHALL 可正常触发同步执行。

#### Scenario: 执行预定义组合同步
- **GIVEN** 预定义组合 `predefined_financial_basic` 包含插件：
  - `tushare_stock_basic`
  - `tushare_income`
  - `tushare_balancesheet`
  - `tushare_cashflow`
- **WHEN** 调用 `POST /api/datamanage/groups/predefined_financial_basic/trigger`
- **THEN** 系统按依赖顺序创建同步任务
- **AND** `tushare_stock_basic` 先执行
- **AND** 其余三个插件在 `tushare_stock_basic` 完成后执行

#### Scenario: 预定义组合中插件不可用
- **GIVEN** 预定义组合包含插件 `tushare_income_vip`
- **AND** 该插件未注册（如未安装）
- **WHEN** 尝试执行该组合
- **THEN** 返回 HTTP 400 Bad Request
- **AND** 响应消息包含不可用的插件列表

### Requirement: Group Detail with Dependency Graph
组合详情 API SHALL 返回依赖关系图和执行顺序。

#### Scenario: 获取组合详情
- **GIVEN** 预定义组合 `predefined_financial_basic`
- **WHEN** 调用 `GET /api/datamanage/groups/predefined_financial_basic`
- **THEN** 返回组合详情
- **AND** 包含 `dependency_graph` 字段表示依赖关系
- **AND** 包含 `execution_order` 字段表示执行顺序
- **AND** 包含 `plugin_status` 字段表示各插件状态

#### Scenario: 依赖关系图格式
- **GIVEN** 组合包含 4 个插件
- **AND** `tushare_income`, `tushare_balancesheet`, `tushare_cashflow` 都依赖 `tushare_stock_basic`
- **WHEN** 获取组合详情
- **THEN** `dependency_graph` 格式为：
  ```json
  {
    "tushare_stock_basic": [],
    "tushare_income": ["tushare_stock_basic"],
    "tushare_balancesheet": ["tushare_stock_basic"],
    "tushare_cashflow": ["tushare_stock_basic"]
  }
  ```

### Requirement: Group Category Filtering
系统 SHALL 支持按分类筛选和展示组合。

#### Scenario: 前端分类筛选
- **GIVEN** 用户在"自定义组合"Tab 页
- **WHEN** 点击"A股"分类标签
- **THEN** 仅显示分类为 `cn_stock` 的组合
- **AND** 包括预定义组合和用户自定义组合

#### Scenario: 分类列表定义
- **WHEN** 获取分类列表
- **THEN** 返回以下分类：
  - `cn_stock` - A股
  - `index` - 指数
  - `etf_fund` - ETF基金
  - `daily` - 每日更新
  - `custom` - 自定义（默认）

## MODIFIED Requirements

### Requirement: Plugin Group Data Model Enhancement
`PluginGroup` 数据模型 SHALL 扩展以支持预定义组合。

#### Scenario: 扩展后的组合模型
- **GIVEN** 需要创建组合实例
- **WHEN** 定义 `PluginGroup` 模型
- **THEN** 模型包含以下字段：
  - `group_id`: 组合唯一标识
  - `name`: 组合名称
  - `description`: 组合描述
  - `plugin_names`: 包含的插件列表
  - `default_task_type`: 默认同步类型
  - `category`: 分类（新增）
  - `is_predefined`: 是否为预定义组合（新增）
  - `is_readonly`: 是否只读（新增）
  - `created_at`: 创建时间
  - `updated_at`: 更新时间

### Requirement: Frontend Group List Enhancement
前端组合列表 SHALL 分组显示预定义组合和用户自定义组合。

#### Scenario: 组合列表分组显示
- **GIVEN** 用户访问"自定义组合"Tab
- **WHEN** 页面加载完成
- **THEN** 显示"预定义组合"分组标题
- **AND** 预定义组合显示锁定图标（🔒）
- **AND** 预定义组合无"编辑"和"删除"按钮
- **AND** 显示"我的组合"分组标题
- **AND** 用户自定义组合显示"编辑"和"删除"按钮

#### Scenario: 空状态提示
- **GIVEN** 用户访问"自定义组合"Tab
- **AND** 用户没有创建任何自定义组合
- **WHEN** 页面加载完成
- **THEN** "我的组合"分组显示空状态提示
- **AND** 提示文字为"暂无自定义组合，点击"创建组合"添加"

## Error Handling

### Requirement: Predefined Group Error Messages
系统 SHALL 提供清晰的预定义组合相关错误信息。

#### Scenario: 预定义组合操作被拒绝
- **GIVEN** 用户尝试修改或删除预定义组合
- **WHEN** 操作被拒绝
- **THEN** 返回明确的错误信息
- **AND** 前端显示友好的提示："预定义组合不可修改/删除"

#### Scenario: 组合中插件不存在
- **GIVEN** 预定义组合配置了不存在的插件
- **WHEN** 加载组合配置
- **THEN** 组合正常加载
- **AND** 组合详情中标记该插件为"未安装"
- **AND** 执行同步时返回插件不存在的错误
