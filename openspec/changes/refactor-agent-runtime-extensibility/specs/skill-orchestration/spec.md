## ADDED Requirements

### Requirement: Skill Registry
系统 MUST 提供统一的 Skill Registry，用于编目、发现和装配 MCP 工具、内置工具、工作区技能及其元数据。

#### Scenario: 汇聚多来源能力目录
- **WHEN** Runtime 初始化 skill catalog
- **THEN** Skill Registry 汇聚 MCP service generator、内置工具和工作区 `SKILL.md` 元数据，形成统一目录

#### Scenario: Agent 装配技能
- **WHEN** 某 Agent、SubAgent 或 Workflow 节点声明所需 skill
- **THEN** Runtime 可通过 Skill Registry 解析对应的工具引用、提示词片段和权限配置

### Requirement: Skill Descriptor Contract
系统 MUST 为每个 skill 定义结构化 descriptor，至少包含名称、版本、分类、触发条件、工具引用和权限范围。

#### Scenario: 读取工作区技能描述
- **WHEN** 系统读取工作区 skill
- **THEN** 能解析 skill 的基础元数据，并补充生成运行时所需的 descriptor 字段

#### Scenario: Skill 版本冲突
- **WHEN** 同名 skill 存在多个版本或来源
- **THEN** Skill Registry 按预定义优先级选择活动版本，并记录冲突来源

### Requirement: Skill Permission and Trigger Control
系统 MUST 对 skill 的触发条件和权限范围进行显式控制，避免任意能力被无约束装配。

#### Scenario: 受限 skill 被请求装配
- **WHEN** 某执行节点尝试使用超出权限范围的 skill
- **THEN** Runtime 阻止装配并返回可操作的错误信息

#### Scenario: 自动触发 skill
- **WHEN** 用户请求或 planner 命中 skill 的触发条件
- **THEN** Runtime 仅在权限满足时自动装配该 skill

### Requirement: Skill-backed Workflow Compatibility
系统 MUST 允许 workflow 配置引用 skill，而不仅仅是直接引用底层工具名。

#### Scenario: Workflow 选择 skill
- **WHEN** 用户创建或生成工作流
- **THEN** 工作流可引用 skill 或 capability bundle，由 runtime 在执行时解析到底层工具集合

### Requirement: SubAgent Collaboration Contract
系统 MUST 为 coordinator 与 specialist 间的 subagent 协作定义标准消息与结果契约。

#### Scenario: Coordinator 调起 specialist
- **WHEN** planner 选择以 SubAgent 方式执行某个 specialist capability
- **THEN** Runtime 创建独立的 subagent session scope，并通过标准输入输出 envelope 返回结果

#### Scenario: SubAgent 结果回传
- **WHEN** SubAgent 完成执行
- **THEN** 返回结构化结果、摘要、状态和可选调试引用，供上游节点安全聚合
