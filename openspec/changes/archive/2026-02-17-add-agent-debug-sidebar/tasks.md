# Tasks: Add Agent Debug Sidebar

## Phase 1: 后端 SSE Debug 事件

- [x] **1.1** 在 `base_agent.py` 的 `execute_stream()` 中新增 `debug` 事件发射：`agent_start`（开始时带 input_summary、tools 列表和可选 parent_agent）、`agent_end`（完成时带 duration_ms 和 tool_calls_count）、`tool_result`（`on_tool_end` 时带 args 和 result_summary）
- [x] **1.2** 在 `orchestrator.py` 中新增 `debug` 事件发射：`_classify_with_llm()` 后发射 `classification`（含 intent, rationale, selected_agent），路由到子 Agent 前发射 `routing`（含 from/to agent 和 is_parallel 标志）
- [x] **1.3** 在 `orchestrator.py` 中新增 A2A 相关 `debug` 事件：`_share_data_to_next_agent()` 调用时发射 `data_sharing`（含 from/to agent 和 data_summary），Agent handoff 触发时发射 `handoff`（含 from/to agent 和 shared_data_summary）
- [x] **1.4** 在 `chat/router.py` 的 `_stream_response` 中透传 `debug` 类型事件为 SSE 帧，并在 `done` 事件的 metadata 中收集 `debug_events` 数组
- [x] **1.5** 在 `chat/service.py` 中确保 `add_message()` 保存包含 `debug_events` 的 metadata 到 ClickHouse

## Phase 2: 前端数据层

- [x] **2.1** 在 `api/chat.ts` 中新增 `DebugEvent` 类型定义（含 handoff/data_sharing 类型），扩展 `StreamEvent` 联合类型
- [x] **2.2** 在 `stores/chat.ts` 中新增 `debugMessages`、`debugSidebarOpen`、`messageDebugMap` 响应式状态，以及 `DebugMessage` 接口（含 targetAgent、parentAgent、laneId 字段）
- [x] **2.3** 在 `stores/chat.ts` 的 SSE 事件处理 switch 中增加 `debug` 分支，将 debug 事件转换为 `DebugMessage` 追加到 `debugMessages`；对 `is_parallel` 的 routing 事件分配 laneId，对带 `parent_agent` 的 agent_start 标记父子关系
- [x] **2.4** 在 `done` 事件处理中，将当前 `debugMessages` 快照写入消息的 `metadata.debug_events`，并添加 `viewDebug(messageId)` 方法从历史 metadata 恢复调试消息

## Phase 3: 前端 UI 组件

- [x] **3.1** 创建 `views/chat/components/DebugMessage.vue` 组件：根据 role（orchestrator/agent/tool/system/handoff）渲染不同样式的消息气泡，支持折叠/展开详情（Tool args/result 用代码块展示），handoff 消息渲染带箭头连接线
- [x] **3.2** 创建 `views/chat/components/AgentDebugSidebar.vue` 组件：可折叠侧栏容器（默认 360px），内含调试消息列表，支持并行 Agent 泳道布局（根据 laneId 分列）和嵌套 Agent 缩进展示（根据 parentAgent 缩进）
- [x] **3.3** 创建 `views/chat/components/DebugTimeline.vue` 组件：侧栏顶部的横向时间线，标注 Agent 执行区间，并行 Agent 多行显示
- [x] **3.4** 修改 `ChatView.vue` 布局：集成 AgentDebugSidebar，添加调试开关按钮，实现三栏响应式布局（≥1400px 并列，1024-1400px overlay，<1024px drawer）
- [x] **3.5** 在 `MessageList.vue` 中为 assistant 消息添加"查看调试 🔍"按钮，点击时打开侧栏并通过 `viewDebug(messageId)` 加载对应调试数据
