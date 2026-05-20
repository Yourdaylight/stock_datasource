## MODIFIED Requirements

### Requirement: Chat协调Agent调度
系统 MUST 在chat入口使用协调Agent进行意图解析，并 MUST 通过数据库中的 Agent 配置构建 `ConfigDrivenHarnessAgent` 执行请求。

#### Scenario: 用户发起对话请求
- **WHEN** 用户向chat入口发送消息
- **THEN** 协调Agent解析意图并选择合适的配置驱动Agent执行

#### Scenario: 配置驱动Agent缺失
- **WHEN** 协调Agent无法找到匹配的数据库Agent配置
- **THEN** 系统返回可理解的错误事件而不是回退到旧Agent文件或AgentRuntime

### Requirement: Agent发现与能力编目
系统 MUST 从数据库 Agent 配置中读取可用Agent清单与能力描述以供调度。

#### Scenario: 系统启动或首次请求
- **WHEN** chat入口初始化调度
- **THEN** 协调Agent获取数据库中可见的Agent清单与能力描述

### Requirement: MCP回退调度
系统 MUST NOT 在chat协调入口维护独立的MCP回退执行路径；工具能力 MUST 通过配置驱动Agent的 skills 与 tool registry 装配。

#### Scenario: 无匹配Agent
- **WHEN** 协调Agent无法匹配可用Agent
- **THEN** 系统返回标准 error/done 事件并提示缺少可用Agent配置
