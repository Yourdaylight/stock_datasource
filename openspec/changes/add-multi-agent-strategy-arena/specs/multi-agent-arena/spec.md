# 多Agent竞技场核心能力规范

## ADDED Requirements

### Requirement: Arena Lifecycle Management
系统 SHALL 提供多Agent竞技场的完整生命周期管理，包括创建、启动、暂停、恢复和销毁。

#### Scenario: Create arena with configurable agents
- **WHEN** 用户请求创建竞技场并指定Agent数量和配置
- **THEN** 系统创建竞技场实例
- **AND** 初始化指定数量的异质化Agent
- **AND** 返回唯一的arena_id

#### Scenario: Start arena competition
- **WHEN** 用户启动已创建的竞技场
- **THEN** 系统异步启动所有Agent的策略生成任务
- **AND** 进入讨论阶段
- **AND** 开始推送思考流

#### Scenario: Pause and resume arena
- **WHEN** 用户暂停运行中的竞技场
- **THEN** 系统保存当前状态
- **AND** 暂停所有异步任务
- **WHEN** 用户恢复竞技场
- **THEN** 从保存的状态继续执行

### Requirement: Agent Heterogeneity Support
系统 SHALL 支持异质化Agent配置，允许不同Agent使用不同的LLM模型和策略生成逻辑。

#### Scenario: Configure heterogeneous agents
- **WHEN** 用户配置竞技场时指定不同Agent的模型类型
- **THEN** 系统为每个Agent分配指定的LLM适配器
- **AND** 每个Agent可独立生成差异化策略

#### Scenario: Dynamic agent model switching
- **WHEN** 管理员需要更换某Agent的底层模型
- **THEN** 系统支持热更新Agent的LLM配置
- **AND** 不影响竞技场的整体运行

### Requirement: Thinking Stream Real-time Output
系统 SHALL 提供Agent思考过程的实时流式输出，支持类似聊天界面的展示方式。

#### Scenario: Subscribe to thinking stream via SSE
- **WHEN** 用户连接到 `/api/arena/{id}/thinking-stream` SSE端点
- **THEN** 系统实时推送每个Agent的思考消息
- **AND** 消息包含Agent标识、消息类型和时间戳
- **AND** 延迟不超过500ms

#### Scenario: Reconnect and resume stream
- **WHEN** 用户SSE连接断开后重新连接
- **AND** 提供上次接收的消息ID
- **THEN** 系统从断点继续推送消息
- **AND** 不丢失任何思考消息

#### Scenario: Persist thinking messages
- **WHEN** Agent产生思考消息
- **THEN** 系统同时写入持久化存储
- **AND** 支持历史回溯查询

### Requirement: Asynchronous Execution
系统 SHALL 确保所有长时间运行的任务异步执行，用户可在等待期间切换页面执行其他操作。

#### Scenario: Background task execution
- **WHEN** 用户启动竞技场后切换到其他页面
- **THEN** 策略生成和讨论任务继续在后台运行
- **AND** 用户返回时可查看最新状态

#### Scenario: Task status polling
- **WHEN** 用户查询竞技场状态
- **THEN** 系统返回当前阶段、进度和活跃任务信息
- **AND** 不阻塞用户界面

### Requirement: Market Context Integration
系统 SHALL 整合实时市场数据，为Agent提供全面的市场环境分析。

#### Scenario: Provide real-time quotes
- **WHEN** Agent需要分析特定股票
- **THEN** 系统提供最新的实时行情数据
- **AND** 包括价格、成交量、涨跌幅等

#### Scenario: Provide technical analysis
- **WHEN** Agent需要技术面分析
- **THEN** 系统计算并提供MA、MACD、RSI、KDJ等技术指标
- **AND** 包括趋势判断和形态识别

#### Scenario: Provide fundamental data
- **WHEN** Agent需要基本面数据
- **THEN** 系统提供PE、PB、ROE等估值指标
- **AND** 包括财务报表关键数据

#### Scenario: Provide market sentiment
- **WHEN** Agent需要市场情绪判断
- **THEN** 系统提供资金流向、涨跌比、VIX等情绪指标
- **AND** 整合新闻舆情分析结果

### Requirement: Arena Configuration
系统 SHALL 提供灵活的竞技场配置选项。

#### Scenario: Configure agent count
- **WHEN** 用户创建竞技场
- **THEN** 可配置Agent数量（范围3-10个，默认5个）
- **AND** 系统根据资源限制验证配置有效性
- **AND** 低于3个时提示警告，超过10个时需管理员确认

#### Scenario: Configure competition parameters
- **WHEN** 用户配置竞技场
- **THEN** 可设置回测周期、初始资金、手续费率等参数
- **AND** 可设置评估周期（日/周/月）
- **AND** 可设置淘汰比例

#### Scenario: Configure discussion modes
- **WHEN** 用户配置讨论机制
- **THEN** 可选择启用的讨论模式（辩论/协作/评审）
- **AND** 可设置每种模式的轮次（默认每种模式1轮，共3轮）

### Requirement: Thinking Stream Retention Policy
系统 SHALL 实施思考流历史数据保留策略。

#### Scenario: Retain thinking history for 30 days
- **WHEN** 思考消息产生
- **THEN** 系统保存消息到持久化存储
- **AND** 消息默认保留30天
- **AND** 超过30天的消息自动归档到冷存储

#### Scenario: Query archived thinking history
- **WHEN** 用户查询超过30天的历史思考流
- **THEN** 系统从归档存储中检索
- **AND** 返回归档数据（查询延迟可能较高）
