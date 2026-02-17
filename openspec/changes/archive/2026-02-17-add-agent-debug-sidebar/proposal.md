# Proposal: Add Agent Debug Sidebar

## Change ID
`add-agent-debug-sidebar`

## Summary
在智能对话界面右侧新增 Agent 调试侧栏，以类似"群聊"的交互形式，实时展示一次对话过程中 OrchestratorAgent 的调度决策、子 Agent 的输入输出、Tool 调用的参数与返回值、以及 LLM 的思考过程。方便开发者和用户 review Agent 的完整推理链路。

## Motivation
当前系统已通过 SSE 流式事件传输了丰富的 Agent/Tool 执行信息（thinking、tool、content、done 事件），但前端仅在消息气泡上方以简单的"步骤条"形式展示 currentAgent/currentTool/currentStatus，存在以下问题：

1. **信息不完整** — Tool 调用的具体参数（args）和返回值（observation）未展示
2. **过程不可回溯** — thinking/tool 事件仅在流式过程中短暂显示，对话完成后无法查看
3. **多 Agent 不透明** — 并发执行多个 Agent 时，无法清晰区分各 Agent 的独立推理链
4. **缺乏调试能力** — 开发者无法直观看到 LLM 的意图分类结果、Agent 路由决策、Tool 错误等关键信息

## Approach

### 核心思路：群聊式调试面板

在对话视图右侧增加可折叠的调试侧栏，将 Agent 执行链路建模为"群聊"：
- **OrchestratorAgent** 作为"群主"，发出意图分类、Agent 路由等消息
- **子 Agent**（如 MarketAgent、ReportAgent）作为"群成员"，展示各自的思考和工具调用
- **Tool 调用** 以"系统消息"形式展示，包含输入参数和返回结果摘要
- **Agent 间交互** 以带箭头的"@提及"消息展示，清晰标注数据流向
- 所有消息按时间顺序排列，形成完整的推理链

### Agent-to-Agent (A2A) 交互场景覆盖

当前系统存在 4 种 A2A 交互模式，调试侧栏需要全部可视化：

| A2A 模式 | 代码位置 | 展示方式 |
|----------|---------|---------|
| **多 Agent 并行** | `orchestrator.py` CONCURRENT_AGENT_GROUPS，如 MarketAgent + ReportAgent 并行 | 并行泳道：两个 Agent 消息流并列，中间用虚线分隔，各自独立的 start→tool→end 链路 |
| **Agent Handoff 移交** | `AGENT_HANDOFF_MAP`，如 MarketAgent → ReportAgent | 带箭头的"@提及"消息：`📊 MarketAgent → 📋 ReportAgent`，展示移交的共享数据摘要 |
| **Agent 嵌套调用** | `ChatAgent` 内工具函数调用 `WorkflowAgent` | 缩进嵌套：WorkflowAgent 的消息在 ChatAgent 消息块内以子级形式展示，形成父子关系 |
| **Agent 数据共享** | `AgentSharedCache.share_data_between_agents()` 通过 Redis | 系统消息：`⚙️ 数据传递: MarketAgent → ReportAgent (stock_info: 600519)` |

### 数据流设计

```
SSE Events → ChatStore 收集 debug events → debugMessages[] → AgentDebugSidebar 渲染
```

**后端改动最小化**：当前 SSE 事件已包含大部分所需信息（agent、tool、args、status），主要补充：
- Tool 调用的 observation（返回值摘要）
- Agent 开始/结束的明确边界事件
- 意图分类的 rationale 字段
- Agent 间数据传递和 handoff 事件

**前端新增组件**：
- `AgentDebugSidebar.vue` — 侧栏容器（可折叠、可调宽度）
- `DebugMessage.vue` — 单条调试消息（区分 orchestrator/agent/tool/system/handoff 角色）
- `DebugTimeline.vue` — 执行时间线视图（支持并行泳道）

### 数据持久化

调试数据随消息 metadata 一起存储到 ClickHouse，支持历史对话的调试信息回看。

## Scope
- **In scope**: 前端调试侧栏 UI、后端 SSE 事件增强、调试数据持久化、A2A 交互可视化
- **Out of scope**: Langfuse 集成改造、Agent 性能分析面板、Tool 重试/编辑能力、Arena 竞技场调试（Arena 有独立的 ThinkingStream 可视化）

## Affected Capabilities
- New: `agent-debug-sidebar`
- Modified: `chat-orchestration` (SSE 事件增强)

## Risks
- 调试数据体积增长 — 通过 metadata 压缩和 TTL 策略缓解
- SSE 事件数量增加对性能的影响 — 调试事件仅在侧栏打开时前端处理，后端始终发送
- UI 布局变化对小屏设备的影响 — 侧栏默认收起，可手动展开
