## ADDED Requirements

### Requirement: 持仓管理API接口
系统应当提供完整的RESTful API接口支持持仓的CRUD操作和相关查询功能。

#### Scenario: 获取持仓列表
- **WHEN** 客户端发送GET请求到 `/api/portfolio/positions`
- **THEN** 系统应当返回用户的所有持仓信息
- **AND** 包含实时计算的盈亏数据
- **AND** 支持分页和排序参数

#### Scenario: 添加新持仓
- **WHEN** 客户端发送POST请求到 `/api/portfolio/positions`
- **THEN** 系统应当验证请求参数的有效性
- **AND** 创建新的持仓记录
- **AND** 返回创建成功的持仓信息

#### Scenario: 更新持仓信息
- **WHEN** 客户端发送PUT请求到 `/api/portfolio/positions/{id}`
- **THEN** 系统应当更新指定的持仓记录
- **AND** 重新计算相关的盈亏数据
- **AND** 返回更新后的持仓信息

#### Scenario: 删除持仓
- **WHEN** 客户端发送DELETE请求到 `/api/portfolio/positions/{id}`
- **THEN** 系统应当删除指定的持仓记录
- **AND** 返回删除操作的确认信息

### Requirement: 投资组合汇总API
系统应当提供投资组合汇总数据的API接口，支持整体表现查询。

#### Scenario: 获取投资组合汇总
- **WHEN** 客户端发送GET请求到 `/api/portfolio/summary`
- **THEN** 系统应当返回投资组合的汇总信息：
  - 总市值和总成本
  - 总盈亏和收益率
  - 当日涨跌金额和幅度
  - 持仓数量统计

#### Scenario: 获取盈亏历史
- **WHEN** 客户端发送GET请求到 `/api/portfolio/profit-history`
- **THEN** 系统应当返回历史盈亏数据
- **AND** 支持时间范围筛选（日期参数）
- **AND** 提供不同时间粒度的数据（日、周、月）

### Requirement: 分析报告API接口
系统应当提供分析报告相关的API接口，支持AI分析功能的调用和结果查询。

#### Scenario: 触发每日分析
- **WHEN** 客户端发送POST请求到 `/api/portfolio/daily-analysis`
- **THEN** 系统应当启动持仓分析任务
- **AND** 返回任务ID用于状态查询
- **AND** 支持异步执行和进度跟踪

#### Scenario: 获取分析报告
- **WHEN** 客户端发送GET请求到 `/api/portfolio/analysis/{date}`
- **THEN** 系统应当返回指定日期的分析报告
- **AND** 包含完整的分析内容和建议
- **AND** 支持报告内容的结构化查询

#### Scenario: 获取分析历史
- **WHEN** 客户端发送GET请求到 `/api/portfolio/analysis`
- **THEN** 系统应当返回历史分析报告列表
- **AND** 支持分页和日期范围筛选
- **AND** 提供报告摘要信息

### Requirement: 预警管理API接口
系统应当提供持仓预警相关的API接口，支持预警规则的管理和通知。

#### Scenario: 设置持仓预警
- **WHEN** 客户端发送POST请求到 `/api/portfolio/alerts`
- **THEN** 系统应当创建新的预警规则
- **AND** 验证预警条件的有效性
- **AND** 返回创建成功的预警信息

#### Scenario: 获取预警列表
- **WHEN** 客户端发送GET请求到 `/api/portfolio/alerts`
- **THEN** 系统应当返回用户的所有预警规则
- **AND** 包含预警状态和触发历史
- **AND** 支持按股票代码筛选

#### Scenario: 更新预警规则
- **WHEN** 客户端发送PUT请求到 `/api/portfolio/alerts/{id}`
- **THEN** 系统应当更新指定的预警规则
- **AND** 验证新的预警条件
- **AND** 返回更新后的预警信息

#### Scenario: 删除预警规则
- **WHEN** 客户端发送DELETE请求到 `/api/portfolio/alerts/{id}`
- **THEN** 系统应当删除指定的预警规则
- **AND** 停止相关的监控任务
- **AND** 返回删除确认信息

### Requirement: API错误处理和验证
所有API接口应当提供统一的错误处理和参数验证机制。

#### Scenario: 参数验证错误
- **WHEN** 客户端发送包含无效参数的请求
- **THEN** 系统应当返回400状态码
- **AND** 提供详细的错误信息和字段验证结果
- **AND** 包含正确的参数格式说明

#### Scenario: 资源不存在错误
- **WHEN** 客户端请求不存在的资源
- **THEN** 系统应当返回404状态码
- **AND** 提供清晰的错误描述
- **AND** 建议可能的解决方案

#### Scenario: 服务器内部错误
- **WHEN** 系统发生内部错误
- **THEN** 应当返回500状态码
- **AND** 记录详细的错误日志
- **AND** 返回用户友好的错误信息（不暴露内部细节）

#### Scenario: 请求频率限制
- **WHEN** 客户端请求频率超过限制
- **THEN** 系统应当返回429状态码
- **AND** 提供重试建议和等待时间
- **AND** 在响应头中包含限制信息