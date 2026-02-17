# agent-debug-sidebar Specification

## Purpose
在智能对话界面右侧提供群聊式 Agent 调试侧栏，实时展示 Agent 调度链路、Tool 调用详情和 LLM 思考过程，支持流式实时查看和历史回看。

## ADDED Requirements

### Requirement: Debug Event Streaming

系统 SHALL 在 SSE 流中新增 `debug` 类型事件，承载 Agent 执行链路的调试信息。

- 系统 SHALL 在 OrchestratorAgent 完成意图分类后发射 `debug(classification)` 事件，包含 intent、rationale、selected_agent、stock_codes
- 系统 SHALL 在路由到子 Agent 前发射 `debug(routing)` 事件，包含 from_agent、to_agent、is_parallel 标志
- 系统 SHALL 在 Agent 开始执行时发射 `debug(agent_start)` 事件，包含 agent 名称、input_summary 和可选的 parent_agent（嵌套调用场景）
- 系统 SHALL 在 Agent 执行完成时发射 `debug(agent_end)` 事件，包含 duration_ms 和 tool_calls_count
- 系统 SHALL 在 Tool 调用完成时发射 `debug(tool_result)` 事件，包含 tool 名称、args、result_summary 和 duration_ms
- 系统 SHALL 在 Agent 间任务移交时发射 `debug(handoff)` 事件，包含 from_agent、to_agent 和 shared_data_summary
- 系统 SHALL 在 Agent 间通过共享缓存传递数据时发射 `debug(data_sharing)` 事件，包含 from_agent、to_agent、data_key 和 data_summary
- 系统 SHALL 保证 `debug` 事件不影响现有 thinking/tool/content/done/error 事件的发送和处理
- 系统 SHALL 在 `done` 事件的 metadata 中收集所有 `debug_events` 数组用于持久化

#### Scenario: Orchestrator 意图分类后发送分类调试事件

- **GIVEN** 用户发送消息 "分析贵州茅台的日K线"
- **WHEN** OrchestratorAgent 完成 LLM 意图分类
- **THEN** SSE 流中产出一条 `{type: "debug", debug_type: "classification"}` 事件
- **AND** 事件 data 包含 `intent`, `rationale`, `selected_agent`, `stock_codes`

#### Scenario: Agent 执行开始和结束时发送边界事件

- **GIVEN** Orchestrator 将请求路由到 MarketAgent
- **WHEN** MarketAgent 开始执行
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "agent_start", agent: "MarketAgent"}`
- **WHEN** MarketAgent 执行完成
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "agent_end", agent: "MarketAgent", data: {duration_ms, tool_calls_count, success}}`

#### Scenario: Tool 调用完成时发送结果摘要事件

- **GIVEN** MarketAgent 正在执行中
- **WHEN** 工具 `get_daily_data` 调用完成并返回结果
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "tool_result"}` 事件
- **AND** 事件 data 包含 `tool`, `args`, `result_summary`, `duration_ms`

#### Scenario: 多 Agent 并行执行时发送各自独立的调试事件

- **GIVEN** 用户查询涉及多个 Agent 并行处理
- **WHEN** Orchestrator 并发调度 MarketAgent 和 ReportAgent
- **THEN** 每个 Agent 分别产出独立的 agent_start/tool_result/agent_end 事件
- **AND** 每条事件的 `agent` 字段标识所属 Agent

#### Scenario: debug 事件向后兼容

- **GIVEN** 前端版本不识别 `debug` 事件类型
- **WHEN** 收到 `debug` 类型 SSE 事件
- **THEN** 前端忽略该事件，不影响现有对话功能

#### Scenario: Agent Handoff 移交时发送 handoff 事件

- **GIVEN** MarketAgent 完成技术分析
- **WHEN** Orchestrator 根据 AGENT_HANDOFF_MAP 将任务移交给 BacktestAgent
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "handoff"}` 事件
- **AND** 事件 data 包含 `from_agent: "MarketAgent"`, `to_agent: "BacktestAgent"`, `shared_data_summary`

#### Scenario: Agent 嵌套调用时标记父子关系

- **GIVEN** ChatAgent 通过 execute_workflow 工具函数创建 WorkflowAgent
- **WHEN** WorkflowAgent 开始执行
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "agent_start", data: {parent_agent: "ChatAgent"}}` 事件

#### Scenario: Agent 间通过共享缓存传递数据时发送 data_sharing 事件

- **GIVEN** MarketAgent 将行情数据写入 AgentSharedCache
- **WHEN** ReportAgent 从缓存读取该数据
- **THEN** SSE 流中产出 `{type: "debug", debug_type: "data_sharing"}` 事件
- **AND** 事件 data 包含 `from_agent`, `to_agent`, `data_key`, `data_summary`

---

### Requirement: A2A Interaction Visualization

系统 SHALL 在调试侧栏中可视化 Agent 间的交互关系，包括并行执行、任务移交、嵌套调用和数据共享四种模式。

- 系统 SHALL 对并行执行的 Agent 以泳道（Swim Lanes）模式展示，每个 Agent 占据独立列
- 系统 SHALL 对 Agent Handoff 移交以带箭头的连接消息展示，标注来源 Agent、目标 Agent 和共享数据摘要
- 系统 SHALL 对嵌套调用的子 Agent 以缩进嵌套方式展示在父 Agent 区块内部
- 系统 SHALL 对 Agent 间数据共享以系统通知消息展示，标注数据来源、目标和数据摘要

#### Scenario: 并行 Agent 以泳道模式展示

- **GIVEN** Orchestrator 并发调度 MarketAgent 和 ReportAgent
- **WHEN** 调试侧栏渲染这两个 Agent 的事件流
- **THEN** MarketAgent 和 ReportAgent 的调试消息分别在左右两个泳道中展示
- **AND** 各泳道内的消息按时间排列，包含各自的 tool 调用和完成状态

#### Scenario: Agent Handoff 以箭头连接展示

- **GIVEN** MarketAgent 执行完成后移交给 BacktestAgent
- **WHEN** 调试侧栏渲染 handoff 事件
- **THEN** 显示带箭头的紫色连接消息 `📊 MarketAgent → 🔬 BacktestAgent`
- **AND** 展示移交的共享数据摘要

#### Scenario: 嵌套调用以缩进子级展示

- **GIVEN** ChatAgent 内部创建并执行了 WorkflowAgent
- **WHEN** 调试侧栏渲染 WorkflowAgent 的事件
- **THEN** WorkflowAgent 的所有调试消息以缩进方式嵌套在 ChatAgent 的消息区块内
- **AND** 嵌套区块有明显的左边框标识层级关系

#### Scenario: 数据共享以系统通知展示

- **GIVEN** MarketAgent 通过 AgentSharedCache 向 ReportAgent 传递了股票数据
- **WHEN** 调试侧栏渲染 data_sharing 事件
- **THEN** 显示居中的系统通知消息
- **AND** 标注 `MarketAgent → ReportAgent` 和数据键名及摘要

---

### Requirement: Agent Debug Sidebar UI

系统 SHALL 在对话界面右侧提供可折叠的调试侧栏，以群聊式消息流展示 Agent 执行链路。

- 系统 SHALL 提供调试开关按钮，点击后在右侧展开调试侧栏
- 系统 SHALL 默认收起调试侧栏，不影响对话主区域的可用性
- 系统 SHALL 以时间顺序展示 Orchestrator 调度消息（蓝色气泡）、Agent 执行消息（绿色气泡）、Tool 调用消息（灰色系统消息）
- 系统 SHALL 为不同 Agent 分配独立的图标以便区分
- 系统 SHALL 支持 Tool 调用消息的折叠/展开，展开后显示 args 代码块和 result_summary

#### Scenario: 用户打开调试侧栏查看实时推理过程

- **GIVEN** 用户在对话界面中
- **WHEN** 用户点击调试开关按钮
- **THEN** 右侧展开调试侧栏（默认 360px 宽度）
- **AND** 侧栏以时间序列展示调试消息流

#### Scenario: 群聊式消息展示不同角色

- **GIVEN** 调试侧栏已打开且正在流式响应
- **WHEN** 收到不同类型的 debug 事件
- **THEN** Orchestrator 消息以蓝色气泡左对齐展示（头像 🤖）
- **AND** Agent 消息以绿色气泡左对齐展示（各 Agent 有独立图标）
- **AND** Tool 调用以灰色系统消息居中展示（图标 🔧）

#### Scenario: Tool 调用展示输入输出详情

- **GIVEN** 调试侧栏收到 tool_result 事件
- **WHEN** 渲染该条调试消息
- **THEN** 默认显示工具名称和耗时的摘要行
- **AND** 点击展开后显示 args（JSON 代码块）和 result_summary（折叠区域）

#### Scenario: 侧栏默认折叠不影响对话体验

- **GIVEN** 用户首次使用对话功能
- **WHEN** 进入对话界面
- **THEN** 调试侧栏默认收起，仅在右侧边缘显示一个展开图标按钮
- **AND** 对话主区域占满剩余宽度

---

### Requirement: Debug History Playback

系统 SHALL 支持查看历史消息的调试信息，从消息 metadata 中恢复完整推理链路。

- 系统 SHALL 在 assistant 消息上提供"查看调试"入口
- 系统 SHALL 将调试数据随消息 metadata.debug_events 持久化到数据库
- 系统 SHALL 从 metadata 中恢复历史调试消息并在侧栏展示

#### Scenario: 查看历史消息的调试详情

- **GIVEN** 用户浏览历史对话消息
- **WHEN** 用户点击某条 assistant 消息上的"查看调试"按钮
- **THEN** 右侧调试侧栏展开
- **AND** 显示该条消息对应的完整 Agent 调试链路

#### Scenario: 调试数据随消息持久化

- **GIVEN** 一次对话流式响应完成
- **WHEN** assistant 消息保存到数据库
- **THEN** 该消息的 metadata 中包含 `debug_events` 字段

---

### Requirement: Debug Timeline Overview

系统 SHALL 在调试侧栏顶部提供执行时间线概览，可视化 Agent 和 Tool 的执行时序。

- 系统 SHALL 以横向时间条展示各 Agent 的执行区间
- 系统 SHALL 对并行执行的 Agent 用多行展示

#### Scenario: 显示 Agent 执行时间线

- **GIVEN** 调试侧栏已打开
- **WHEN** 一次对话涉及 Orchestrator → MarketAgent 的调度链路
- **THEN** 侧栏顶部显示横向时间线
- **AND** 时间线上标注各阶段的时间区间

#### Scenario: 并行 Agent 在时间线上多行显示

- **GIVEN** 一次对话并行执行了 MarketAgent 和 ReportAgent
- **WHEN** 查看调试时间线
- **THEN** MarketAgent 和 ReportAgent 在时间线上分别占据独立的行

---

### Requirement: Responsive Layout

系统 SHALL 保证调试侧栏适配不同屏幕宽度，不损害对话主区域的可用性。

- 系统 SHALL 在视口宽度 ≥ 1400px 时以三栏并列模式展示
- 系统 SHALL 在视口宽度 1024-1400px 时以 overlay 模式展示调试侧栏
- 系统 SHALL 在视口宽度 < 1024px 时以 drawer 模式展示调试侧栏

#### Scenario: 大屏三栏并列布局

- **GIVEN** 浏览器视口宽度 ≥ 1400px
- **WHEN** 调试侧栏打开
- **THEN** 会话列表、对话主区、调试侧栏三栏并列显示

#### Scenario: 中屏覆盖模式

- **GIVEN** 浏览器视口宽度在 1024-1400px 之间
- **WHEN** 调试侧栏打开
- **THEN** 调试侧栏以 overlay 模式覆盖在对话区域上方
- **AND** 可通过点击遮罩或关闭按钮收起
