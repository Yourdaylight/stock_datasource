## Context

当前代码中至少存在四类重叠运行时责任：

1. **聊天编排链路**
   - `agents/orchestrator.py` 负责意图分类、Agent 发现、并发执行、MCP fallback、部分 debug 事件
   - `agents/base_agent.py` 负责模型初始化、会话历史、流式执行、checkpointer、tool 调用包装
   - `modules/chat/router.py` / `service.py` 负责 SSE 输出、消息持久化、会话缓存

2. **Workflow 链路**
   - `workflow_service.py` 维护工具目录、模板、工作流文件存储
   - `workflow_agent.py` 重新从 `create_mcp_server()` 动态加载工具并执行
   - `workflow_generator_agent.py` 又单独维护一套“可用工具目录注入 + 生成配置”链路

3. **Arena 链路**
   - `arena/arena_manager.py`、`discussion_orchestrator.py`、`stream_processor.py` 自成一套多Agent协调、状态管理和事件流
   - 与 chat 主链路未共享 session、memory、event schema、resource governance

4. **Skill / 插件 / MCP 链路**
   - `skills/` 中存在高价值能力包，但目前没有统一运行时注册协议
   - `services/mcp_server.py` + `core/service_generator.py` 已经具备“工具发现 + 描述生成 + handler 装配”基础能力
   - `workflow_service.py` 和 `workflow_agent.py` 继续重复做工具目录提取与装配

## Goals / Non-Goals

### Goals

- 建立统一 `Agent Runtime`，作为 chat / workflow / arena 共用控制平面
- 让 `Agent`、`SubAgent`、`Skill` 三类能力边界清晰且可组合
- 收敛会话与记忆链路，明确热状态、持久化历史、长期偏好三层职责
- 把工具发现和能力描述沉淀为 registry，而不是散落在扫描代码和文档里
- 在不破坏现有 API 与前端事件协议的前提下，降低性能与维护成本

### Non-Goals

- 本次变更不重写所有业务 Agent 的业务逻辑
- 本次变更不替换 LangGraph / DeepAgents 作为推理框架
- 本次变更不要求前端一次性改成全新的协议
- 本次变更不把 skill 设计成另一个复杂插件系统；优先复用现有 MCP / 插件资产

## Audit Summary

### A. 编排与执行计划重叠

- `orchestrator.py` 负责 route-only、parallel-aggregate 和 MCP fallback
- `workflow_agent.py` 负责“配置化工具执行”
- `arena/discussion_orchestrator.py` 负责多轮讨论、review、collaboration

**结论**：三者都在做“把用户目标转成若干执行节点并驱动执行”，但没有共享 execution plan 抽象。

### B. 会话与记忆重叠

- `base_agent.py::SessionMemory` 维护进程内历史与工具缓存
- `modules/chat/service.py` 维护持久化历史与 `_session_cache`
- `services/agent_cache.py` 维护 Redis 共享状态与 Agent 间共享数据
- `memory_agent.py` 维护长期偏好与自选股，但仍是全局内存字典

**结论**：短期、中期、长期记忆边界未明确，且存在重复存储与持久化不一致问题。

### C. 事件流与调试重叠

- `base_agent.py` 输出 agent/tool/thinking 事件
- `modules/chat/router.py` 将内部事件转换为 SSE
- `arena/stream_processor.py` 又维护一套独立的思考流事件模型
- 调试数据会进入最终消息 metadata，形成写放大

**结论**：应统一 event envelope，SSE 只做 adapter，调试归档与最终消息元数据分离。

### D. Tool / Skill 目录重叠

- `mcp_server.py` 已能从插件 service 自动发现工具
- `workflow_service.py::get_available_tools()` 重复组装工具目录
- `workflow_agent.py::_load_mcp_tools()` 重复组装 handler
- `skills/` 中的 `SKILL.md` 提供使用说明，但没有统一 descriptor 与 registry

**结论**：可把 `ServiceGenerator` + workspace skill metadata 提升为 `Skill Registry` 的底层来源。

## Decisions

### Decision 1: 引入统一 Agent Runtime 作为控制平面

新增 `services/agent_runtime.py`，统一负责：

- `ExecutionPlan` 构建与执行
- session / run_id / parent_run_id 生命周期
- 并发上限、超时、重试、降级
- 统一事件流输出
- Adapter 调用 `Agent` / `SubAgent` / `Workflow` / `Arena`

保留 `OrchestratorAgent` 作为兼容入口，但其主要职责变为：

- 请求归一化
- 调用 runtime
- 兼容旧的调用方与 metadata 结构

### Decision 2: 用显式 Registry 替代运行时扫描作为主路径

新增 `services/agent_registry.py`：

- 维护 `AgentDescriptor` / `CapabilityDescriptor`
- 注册普通业务 Agent、subagent、workflow adapter、arena adapter
- 支持启动时显式注册
- 保留目录扫描作为兼容 fallback，但不再作为主路径

这样可以降低 `pkgutil + importlib + instance()` 带来的冷启动抖动和不可控副作用。

### Decision 3: 统一五种编排模式

定义统一 `ExecutionPlanNode`，覆盖以下模式：

- `route_only`
- `parallel_aggregate`
- `sequential_handoff`
- `workflow_driven`
- `discussion_arena`

这五种模式共用同一执行图与事件模型，避免 chat / workflow / arena 各自维护调度逻辑。

### Decision 4: 明确 Agent / SubAgent / Skill 三种边界

#### Agent

- 面向业务能力暴露
- 通常可被 chat 直接路由
- 拥有稳定 capability 名称和输入输出语义

#### SubAgent

- 由 coordinator / runtime 临时或受控地调起
- 拥有独立 session scope、history_ref、run_id
- 输出结构化结果给上游节点
- 默认不直接暴露给所有外部入口

#### Skill

- 是可复用能力包，不等于 Agent
- 封装 prompt 片段、工具引用、触发条件、权限边界、版本信息
- 可被 Agent、SubAgent、Workflow 节点装配
- 可以来源于：workspace `SKILL.md`、MCP tool catalog、内置 capability bundle

### Decision 5: 统一 Session & Memory Service

新增 `services/session_memory_service.py`，统一三层职责：

- **Hot State**：Redis，保存短期共享状态、history 引用、运行态索引
- **Persistent History**：ClickHouse，保存会话消息与关键事件摘要
- **Long-term Memory**：用户偏好、自选股、记忆摘要，按 `user_id` 隔离并持久化

核心原则：

- `SessionMemory` 不再直接承担最终会话真相源角色
- `ChatService` 不再维护无界 `_session_cache`
- `MemoryAgent` 不再维护全局内存 `_memory_store`
- 历史按 `history_ref` 引用和按需注入，避免每个子 Agent 重复吃完整历史

### Decision 6: Skill Registry 复用现有 MCP / 插件基础能力

新增 `services/skill_registry.py`，底层来源包括：

1. `mcp_server.py` / `ServiceGenerator` 导出的结构化工具定义
2. 内置工具（如 `agents/tools.py` 等）
3. 工作区 `skills/*/SKILL.md` 的 metadata 与可选 descriptor
4. 后续显式注册的 workflow template / capability bundle

`SkillDescriptor` 应至少包含：

- `name`
- `version`
- `category`
- `tool_refs`
- `prompt_refs`
- `triggers`
- `permission_scope`
- `execution_mode`

### Decision 7: 统一事件模型并削减重型 metadata

引入统一事件 envelope：

- `run.start`
- `plan.created`
- `node.start`
- `node.output`
- `tool.call`
- `tool.result`
- `node.error`
- `run.complete`

原则：

- SSE 层只做协议适配，不负责重新发明事件结构
- 调试明细和可视化负载单独存储或按引用关联
- assistant 最终消息只保留必要摘要和索引，避免 metadata 失控膨胀

### Decision 8: 通过 adapter 吸纳 Workflow 与 Arena

- `WorkflowAgent` 迁移为 `WorkflowRuntimeAdapter`
- `MultiAgentArena` 迁移为 `ArenaRuntimeAdapter`
- 两者复用 runtime 的 session、resource governance、event schema
- 保留原业务模型和讨论/竞技规则，不重写领域逻辑

## Architecture Sketch

```text
Chat/API
  -> AgentRuntime
      -> AgentRegistry
      -> ExecutionPlanner
      -> SessionMemoryService
      -> SkillRegistry
      -> [AgentAdapter | SubAgentAdapter | WorkflowAdapter | ArenaAdapter]
```

## Data Contracts

### ExecutionPlanNode

```python
class ExecutionPlanNode(BaseModel):
    id: str
    mode: str
    target: str
    depends_on: list[str] = []
    input_keys: list[str] = []
    output_key: str = ""
    timeout_seconds: int = 0
    retry_count: int = 0
```

### AgentSessionContext

```python
class AgentSessionContext(BaseModel):
    session_id: str
    user_id: str
    parent_run_id: str = ""
    history_ref: str = ""
    memory_scope: str = ""
    shared_state_keys: list[str] = []
```

### SkillDescriptor

```python
class SkillDescriptor(BaseModel):
    name: str
    version: str
    category: str
    triggers: list[str] = []
    tool_refs: list[str] = []
    prompt_refs: list[str] = []
    permission_scope: str = ""
```

## Performance Strategy

- 把 Agent 发现从请求时扫描切到显式注册表
- 复用稳定的 deep agent / model / tool binding，减少重复构造
- 使用 `history_ref + scoped context` 替代子 Agent 重复拼装完整历史
- 对多Agent执行增加并发上限、超时、失败隔离与降级
- 调试数据拆分存储，降低 SSE 和 ClickHouse 写放大
- 将清理逻辑从请求路径移出，改为 TTL 或后台清理

## Migration Plan

### Phase 0: 提案与基线

- 完成 OpenSpec 提案、设计、任务拆分
- 建立 runtime feature flag
- 补齐基线指标：冷启动时延、分类调用次数、平均 prompt 大小、会话缓存占用

### Phase 1: Runtime Shell

- 新增 `AgentRuntime`、`AgentRegistry`、`ExecutionPlanner`
- `OrchestratorAgent` 改为委托 runtime
- 保留旧的 Agent 实现与原始业务工具

### Phase 2: Memory Pipeline

- 新增 `SessionMemoryService`
- 统一 session_id / history_ref / user_id
- 将 `MemoryAgent` 持久化并补齐用户隔离

### Phase 3: Redundancy & Governance

- 移除重复分类与重复上下文构建热点
- 收敛 `_session_cache` 和重型 metadata
- 增加并发治理、超时和失败隔离

### Phase 4: Skill & SubAgent Protocol

- 引入 `SkillRegistry`
- 定义 subagent 调起、handoff、message contract
- 让 workflow / arena 接入统一 runtime

## Risks / Trade-offs

- 显式 registry 会增加接入约束，但换来更稳定的扩展治理
- 双路径迁移会短期提升复杂度，但能降低一次性切换风险
- Skill 抽象若太重会影响简单能力接入，因此优先从 descriptor 层起步，而不是强绑定复杂生命周期

## Rollback Plan

- 保留 `OrchestratorAgent` 兼容入口，可通过 feature flag 回退到旧执行链路
- Workflow / Arena adapter 接入失败时，仍可回退到原模块直接执行
- Skill registry 初期仅作为 catalog，不阻断既有 MCP 调用

## Open Questions

- 长期记忆继续完全落在 ClickHouse，还是为高频偏好建立更轻量 KV 层
- Skill versioning 是采用 workspace 本地版本优先，还是支持托管版本覆盖
- Arena 的实时流是否保留独立事件类型，还是完全映射到统一 envelope
