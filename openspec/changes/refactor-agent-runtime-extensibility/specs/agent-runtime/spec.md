## ADDED Requirements

### Requirement: Unified Agent Runtime
系统 MUST 提供统一的 Agent Runtime 作为聊天、工作流和竞技场模式的共享执行控制平面。

#### Scenario: Chat 请求进入统一运行时
- **WHEN** chat 入口接收到用户请求
- **THEN** 请求被转换为统一的运行时执行请求，并由 Agent Runtime 负责规划、执行和事件输出

#### Scenario: Workflow 或 Arena 接入统一运行时
- **WHEN** workflow 或 arena 模块发起执行
- **THEN** 其执行通过 runtime adapter 接入统一的 session、execution plan 和事件模型，而不是维护独立运行时

### Requirement: Execution Plan Modes
系统 MUST 使用统一执行计划模型表示单Agent路由、并行聚合、顺序交接、工作流驱动和讨论竞技五类编排模式。

#### Scenario: 并行聚合执行
- **WHEN** 请求需要多个独立 Agent 并行完成分析
- **THEN** Runtime 创建包含多个并行节点的执行计划，并在完成后执行结构化聚合

#### Scenario: 顺序交接执行
- **WHEN** 上游节点输出需要作为下游 specialist 的输入
- **THEN** Runtime 使用顺序依赖节点表示 handoff，而不是通过共享可变上下文隐式传递

### Requirement: Explicit Agent Registry
系统 MUST 支持显式注册 Agent、SubAgent 与 adapter 化 capability，并将运行时扫描降级为兼容 fallback。

#### Scenario: 启动期注册 capability
- **WHEN** 系统启动或运行时初始化
- **THEN** Agent Registry 加载显式注册的 capability 描述，并供 planner 查询

#### Scenario: 兼容旧扫描模式
- **WHEN** 某 capability 尚未迁移到显式注册表
- **THEN** 系统可使用兼容扫描模式发现该能力，但该路径不作为主执行策略

### Requirement: Session and Memory Boundary
系统 MUST 统一 session、history reference、shared state 与长期记忆边界，避免多处重复保存同一会话上下文。

#### Scenario: 子Agent读取会话上下文
- **WHEN** Runtime 调起 SubAgent
- **THEN** SubAgent 获取 `history_ref` 和受限 `scoped context`，而不是复制完整历史消息

#### Scenario: 长期偏好持久化
- **WHEN** 用户保存投资偏好、自选股或长期记忆
- **THEN** 记忆按 `user_id` 隔离并持久化，不依赖进程内全局字典

### Requirement: Resource Governance
系统 MUST 对多Agent运行提供并发、超时、失败隔离和降级治理。

#### Scenario: 并发节点过多
- **WHEN** 执行计划包含多个并发节点
- **THEN** Runtime 按配置的并发上限调度，并对超时或失败节点进行隔离处理

#### Scenario: 单节点失败
- **WHEN** 某个 Agent / SubAgent 节点执行失败
- **THEN** Runtime 记录结构化错误并根据节点策略重试、跳过或降级，而不是让整个运行时无控制失败

### Requirement: Unified Event Envelope
系统 MUST 为 chat、workflow、arena 输出统一事件 envelope，并允许前端或传输层做协议适配。

#### Scenario: SSE 兼容输出
- **WHEN** chat SSE 需要把运行时事件流式输出到前端
- **THEN** 路由层基于统一 envelope 转换为兼容的 SSE 事件，而不重新发明内部事件结构
