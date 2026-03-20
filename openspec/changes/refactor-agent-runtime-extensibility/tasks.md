## 1. Runtime Foundation

- [x] 1.1 建立 `AgentRuntime`、`AgentRegistry`、`ExecutionPlanner` 的基础骨架与 feature flag
  > 已完成：基于 `langgraph_supervisor.create_supervisor` + `create_react_agent` 重写，不再自造轮子
- [x] 1.2 将 `OrchestratorAgent` 重构为兼容入口，内部委托统一 runtime
  > 已完成：`OrchestratorAgent.execute()` 通过 feature flag 委托 `AgentRuntime.execute_stream_sse()`
- [x] 1.3 为现有业务 Agent 建立显式 capability 注册，保留扫描模式作为 fallback
  > 已完成：`agent_registrations.py` 注册 16 个 Agent，`AgentRegistry` 保留 fallback scan
- [x] 1.4 定义统一 execution plan 节点模型，覆盖 route / parallel / handoff / workflow / arena
  > 已完成：`ExecutionPlanner` 提供配置数据（并发组、handoff map），LangGraph Supervisor 做路由决策

## 2. Session & Memory Convergence

- [x] 2.1 新增 `SessionMemoryService`，统一 session_id、history_ref、user_id、shared state 访问
  > 已完成：含 hot state、history TTL、scoped history、session 驱逐、user preference 等
- [x] 2.2 将 `SessionMemory` 从真相源降级为 runtime 内部缓存或兼容层
  > 已完成：`SessionMemory` 改为 ~30 行的兼容 facade，所有调用转发到 `SessionMemoryService`
- [x] 2.3 将 `MemoryAgent` 的偏好与自选股迁移到持久化存储，并补齐 `user_id` 隔离
  > 已完成：移除 module-level `_memory_store`，4 个工具函数均通过 `_current_user_id` 委托到 `SessionMemoryService`
- [x] 2.4 收敛 `ChatService`、`AgentSharedCache`、长期记忆三者职责，清理重复存储
  > 已完成：`ChatService._session_cache` 已移除，ChatService 现为纯 ClickHouse 持久化层；热数据由 `SessionMemoryService` 统一管理

## 3. Redundancy & Performance Governance

- [x] 3.1 消除重复建 Agent / 重复绑定工具 / 重复意图分类的高成本路径
  > 已完成：LangGraph Supervisor 统一路由，Agent 单例通过 Registry 管理，不再重复实例化
- [x] 3.2 将子 Agent 上下文改为 `history_ref + scoped context`，避免重复拼装完整历史
  > 已完成：`chat/router.py` 和 `ChatService.process_message()` 改为传递 `[-10:]` 截断历史；`SessionMemoryService.get_scoped_history()` 提供轻量上下文
- [x] 3.3 为并发执行增加上限、超时、失败隔离与降级策略
  > 已完成：`AgentRuntime` 有 `default_timeout`、`recursion_limit=50`，LangGraph 原生失败隔离
- [x] 3.4 拆分调试事件与最终消息 metadata，降低 SSE 与持久化写放大
  > 已完成：`chat/router.py` 不再将完整 `debug_events` / `visualizations` 数组写入消息 metadata，改为仅存 `debug_event_count` / `visualization_count` 计数
- [x] 3.5 限制 `_session_cache` 等无界缓存，迁移清理逻辑到 TTL 或后台任务
  > 已完成：`SessionMemoryService` 含 TTL cache、MAX_SESSIONS 驱逐、cleanup_expired()

## 4. Skill & SubAgent Protocol

- [x] 4.1 新增 `SkillRegistry`，统一 MCP 工具、内置工具、工作区 skills 的 catalog 与 descriptor
  > 已完成：含 register/find_by_trigger/find_by_tool/to_catalog
- [x] 4.2 定义 `SkillDescriptor` 与权限、版本、触发器、tool refs 规范
  > 已完成：SkillDescriptor 含 name/version/category/triggers/tool_refs/permission_scope/execution_mode
- [x] 4.3 定义 `SubAgent` 调起协议，包括 session scope、message contract、result envelope
  > 已完成：`SubAgentEnvelope` dataclass（agent_name, session_id, user_id, query, scoped_history, shared_state_keys, response, success, metadata, tool_calls）；已集成到 `AgentRuntime.execute_stream_sse()`
- [x] 4.4 让 `WorkflowAgent` 改为 workflow runtime adapter，复用 skill registry 和 execution planner
  > 已完成：新增 `register_workflow_adapter()` 函数，以 `AgentRole.ADAPTER` 注册到 `AgentRegistry`
- [x] 4.5 让 `MultiAgentArena` 改为 arena runtime adapter，复用统一 session 与事件模型
  > 已完成：新增 `register_arena_adapter()` 函数，以 `AgentRole.ADAPTER` 注册 `ArenaAdapter` 到 `AgentRegistry`

## 5. Compatibility, Observability & Rollout

- [x] 5.1 统一事件 envelope，并为 chat SSE 提供兼容 adapter
  > 已完成：`adapt_langgraph_event_to_sse()` 将 LangGraph astream_events v2 转为前端 SSE 格式
- [x] 5.2 增加冷启动、token 成本、分类次数、并发失败率、缓存占用等核心指标
  > 已完成：`AgentRuntime.stats` 属性（cold_start_ms, total_invocations, classification_count, concurrent_failures, failure_rate, sub_agent_count）；`SessionMemoryService._stats` 含 cache_hits/misses/sessions_evicted/runtime_invocations/runtime_errors；`record_stat()` 方法供外部组件使用
- [x] 5.3 为 runtime、registry、memory pipeline、skill registry 编写单元与集成测试
  > 已完成：58 tests all passing（覆盖 AgentRegistry/ExecutionPlanner/AgentRuntime/SessionMemory/SkillRegistry/SubAgentEnvelope/RuntimeStats）
- [x] 5.4 设计灰度开关、双路径切换和回滚预案
  > 已完成：`AGENT_RUNTIME_ENABLED` env var feature flag，默认 false，OrchestratorAgent 双路径
