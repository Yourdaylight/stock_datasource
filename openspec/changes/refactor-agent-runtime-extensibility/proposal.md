# Change: 统一 Agent Runtime 与可扩展编排体系

## Why

当前项目已经具备 `OrchestratorAgent`、`WorkflowAgent`、`MultiAgentArena`、MCP Server、工作区 `skills/` 等多种能力，但运行时责任分散在多条链路中，形成了多套半重叠的调度与状态模型。随着 Agent 数量、插件数量和工作流复杂度增长，现状开始暴露出以下问题：

- `orchestrator.py`、`workflow_agent.py`、`arena/` 分别维护自己的执行模型，路由、并发、会话、事件流逻辑重复
- Agent 发现依赖运行时扫描与实例化，冷启动抖动明显，扩展治理能力弱
- `SessionMemory`、`ChatService`、`AgentSharedCache`、`MemoryAgent` 对会话、缓存、长期偏好的职责划分不清
- 同一请求中存在重复分类、重复上下文构建、重复调试数据持久化等高成本路径
- `skills/` 具备资产价值，但目前更像离散文档与脚本集合，缺少统一注册、版本、权限与编排协议

本变更旨在参考 OpenClaw 的 runtime / session / skill / 多会话协作思路，但保持与当前 Python + FastAPI + LangGraph + MCP 架构兼容，采用渐进式演进而非推倒重来。

## What Changes

- 新增统一 `Agent Runtime` 作为控制平面，承接聊天、workflow、arena 的执行入口
- 新增显式 `Agent Registry` 与 `Execution Planner`，收敛当前目录扫描、并发执行、handoff、fallback 逻辑
- 新增统一 `Session & Memory Service`，明确短期会话、共享状态、长期偏好、持久化历史的边界
- 新增 `Skill Registry`，统一 MCP 工具、内置工具、工作区技能、插件导出能力的描述与装配
- 定义 `SubAgent` 协议，使 coordinator + specialist 协作具备独立 session、消息传递与结果汇总能力
- 将 `WorkflowAgent` 与 `MultiAgentArena` 逐步降级为 runtime adapter，而不是独立运行时
- 对高成本冗余路径进行治理，包括：重复建 Agent、重复分类、重复上下文、重型调试 metadata、无界缓存
- 引入 feature flag / 双路径切换，支持灰度迁移与回滚

## Impact

- **Affected specs**:
  - `chat-orchestration`（修改）
  - `agent-runtime`（新增）
  - `skill-orchestration`（新增）
- **Affected code**:
  - `src/stock_datasource/agents/orchestrator.py`
  - `src/stock_datasource/agents/base_agent.py`
  - `src/stock_datasource/agents/memory_agent.py`
  - `src/stock_datasource/agents/workflow_agent.py`
  - `src/stock_datasource/agents/workflow_generator_agent.py`
  - `src/stock_datasource/arena/`
  - `src/stock_datasource/modules/chat/`
  - `src/stock_datasource/services/agent_cache.py`
  - `src/stock_datasource/services/mcp_server.py`
  - 新增 `services/agent_runtime.py`、`agent_registry.py`、`execution_planner.py`、`session_memory_service.py`、`skill_registry.py`

## Migration Strategy

- 第一阶段只引入 runtime 外壳与 registry，不要求一次性改写所有业务 Agent
- 第二阶段将 chat 主链路切到新 runtime，同时保留 `OrchestratorAgent` 作为兼容入口
- 第三阶段把 workflow / arena 通过 adapter 接入统一 runtime
- 第四阶段再逐步启用 skill 注册、subagent 协议与资源治理能力

## Risks

- 执行链路统一后，若事件模型设计不稳，可能影响现有 SSE 前端兼容性
- Runtime 与旧链路双跑期间，状态边界可能短期更复杂
- Skill / SubAgent 协议若抽象过重，会抬高简单 Agent 接入成本

## Success Criteria

- 聊天、workflow、arena 至少共享一套 execution plan / session / event 模型
- Agent 发现从运行时扫描逐步切换到显式 registry
- 会话短期记忆、共享状态、长期记忆职责明确且具备持久化边界
- Skill 能以统一 descriptor 被注册、发现、装配和权限控制
- 关键热点路径（重复分类、重复建 Agent、重型 metadata）得到系统性治理
