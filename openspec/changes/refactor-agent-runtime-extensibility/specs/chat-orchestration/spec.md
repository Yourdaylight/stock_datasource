## MODIFIED Requirements

### Requirement: Chat协调Agent调度
系统 MUST 在 chat 入口使用统一运行时驱动的协调能力进行意图解析、执行计划生成与调度，而不是仅依赖单一编排器内嵌逻辑。

#### Scenario: 用户发起对话请求
- **WHEN** 用户向 chat 入口发送消息
- **THEN** chat 入口将请求交给统一运行时，由其解析意图、生成执行计划并调度合适的 Agent、SubAgent 或 fallback 能力

### Requirement: Agent发现与能力编目
系统 MUST 支持显式 Agent Registry 进行能力编目，并允许兼容模式下的目录扫描发现能力。

#### Scenario: 系统启动或首次请求
- **WHEN** chat 入口初始化调度
- **THEN** 协调层优先从显式注册表获取 capability 清单与能力描述，并仅在必要时回退到兼容扫描模式

### Requirement: SSE流式输出完整事件
系统 MUST 在前端流式输出中展示统一运行时事件，并保持现有 SSE 消费方可兼容处理。

#### Scenario: 处理对话并流式返回
- **WHEN** chat 入口处理用户消息
- **THEN** 前端流式输出包含统一运行时事件映射后的至少 thinking/tool/content/done/error 事件，并可追踪计划与节点执行状态

## ADDED Requirements

### Requirement: Chat资源治理与上下文隔离
系统 MUST 在 chat 多Agent执行过程中控制并发、隔离上下文并避免重复历史注入。

#### Scenario: Chat 并发调起多个能力
- **WHEN** chat 执行计划包含多个并发能力节点
- **THEN** 运行时对每个节点提供隔离的 scoped context，并按并发限制执行，而不是共享同一个可变上下文字典

#### Scenario: 子能力读取历史
- **WHEN** 某个子能力需要读取历史消息
- **THEN** 运行时通过 history reference 或裁剪后的上下文注入历史，避免完整历史在多个节点重复复制
