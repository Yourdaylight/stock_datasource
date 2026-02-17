## ADDED Requirements

### Requirement: Chat协调Agent调度
系统 MUST 在chat入口使用协调Agent进行意图解析与调度。

#### Scenario: 用户发起对话请求
- **WHEN** 用户向chat入口发送消息
- **THEN** 协调Agent解析意图并选择合适的Agent执行

### Requirement: Agent发现与能力编目
系统 MUST 能够发现Agents目录下的Agent并读取其能力描述以供调度。

#### Scenario: 系统启动或首次请求
- **WHEN** chat入口初始化调度
- **THEN** 协调Agent获取可用Agent清单与能力描述

### Requirement: MCP回退调度
系统 MUST 在无可用Agent可处理请求时回退到MCP工具调度。

#### Scenario: 无匹配Agent
- **WHEN** 协调Agent无法匹配可用Agent
- **THEN** 协调Agent列出MCP工具并调用合适工具完成任务

### Requirement: SSE流式输出完整事件
系统 MUST 在前端流式输出中展示完整过程事件。

#### Scenario: 处理对话并流式返回
- **WHEN** chat入口处理用户消息
- **THEN** 前端流式输出包含至少 thinking/tool/content/done/error 事件

### Requirement: Agent与API数据一致性
系统 MUST 确保Agent分析使用的数据与API返回的数据保持一致。

#### Scenario: 持仓分析数据一致性
- **WHEN** 用户通过智能对话查询持仓
- **THEN** 返回的持仓数据与 `/api/portfolio/positions` 接口一致

#### Scenario: 数据库多用户支持
- **GIVEN** user_positions 表包含 user_id 字段
- **WHEN** Agent查询用户持仓
- **THEN** 仅返回该用户的持仓数据

### Requirement: LLM调用追踪（Langfuse）
系统 MUST 集成Langfuse记录LLM调用追踪信息。

#### Scenario: 对话追踪记录
- **WHEN** 用户进行智能对话
- **THEN** Langfuse记录包含用户ID、会话ID、Agent名称的trace

#### Scenario: Langfuse配置
- **GIVEN** 环境变量 LANGFUSE_HOST/LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY 已配置
- **WHEN** 系统启动
- **THEN** Langfuse CallbackHandler 可正常创建

### Requirement: 服务层兼容性
系统 MUST 在数据库表结构变更时保持向后兼容。

#### Scenario: user_id字段兼容性
- **GIVEN** user_positions 表可能不包含 user_id 字段（旧版本）
- **WHEN** PortfolioService 查询持仓
- **THEN** 自动检测字段存在性并降级处理（返回所有持仓）
