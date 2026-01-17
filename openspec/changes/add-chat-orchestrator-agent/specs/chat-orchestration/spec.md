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
