## ADDED Requirements

### Requirement: 知识库服务可选接入
系统 MUST 支持通过环境变量可选接入 WeKnora 知识库服务，未配置时系统行为不受影响。

#### Scenario: WeKnora 未配置
- **GIVEN** 环境变量 `WEKNORA_ENABLED` 为 `false` 或未设置
- **WHEN** 系统启动
- **THEN** KnowledgeAgent 不注册，不产生任何 WeKnora 网络请求，系统行为与接入前完全一致

#### Scenario: WeKnora 已配置且可用
- **GIVEN** `WEKNORA_ENABLED=true` 且 `WEKNORA_BASE_URL` 和 `WEKNORA_API_KEY` 已配置
- **WHEN** 系统启动并通过健康检查
- **THEN** KnowledgeAgent 自动注册到 Orchestrator，可参与意图路由

#### Scenario: WeKnora 已配置但不可达
- **GIVEN** `WEKNORA_ENABLED=true` 但 WeKnora 服务不可达
- **WHEN** 系统启动
- **THEN** 记录警告日志，KnowledgeAgent 不注册，系统降级为无知识库模式正常运行

### Requirement: 知识库语义检索
系统 MUST 通过 WeKnora REST API 执行知识库语义检索，返回带评分的文档片段。

#### Scenario: 检索到相关内容
- **WHEN** KnowledgeAgent 对用户查询执行 `search_knowledge`
- **THEN** 返回按相关性排序的知识片段列表，每条包含 content、source、score 字段

#### Scenario: 检索无结果
- **WHEN** 知识库中无匹配内容
- **THEN** KnowledgeAgent 明确告知用户"知识库中未找到相关信息"，不捏造内容

### Requirement: 知识库 Agent 与现有 Agent 并发协作
系统 MUST 支持 KnowledgeAgent 与其他 Agent（MarketAgent、ReportAgent）并发执行。

#### Scenario: 混合查询（知识库 + 技术分析）
- **WHEN** 用户查询同时涉及知识库内容和技术分析（如"根据最新研报分析茅台走势"）
- **THEN** Orchestrator 同时调度 KnowledgeAgent 和 MarketAgent 并发执行，合并结果

#### Scenario: 纯知识库查询
- **WHEN** 用户查询仅涉及文档内容（如"公司章程中关于分红的规定"）
- **THEN** Orchestrator 仅调度 KnowledgeAgent

### Requirement: 未部署知识库时提供引导说明和快速部署方案
系统 MUST 在知识库未配置时，通过前端界面向用户展示功能说明和快速部署方案，而非隐藏该功能或显示空白。

#### Scenario: 数据配置页展示知识库引导面板
- **GIVEN** 后端返回知识库状态为 `not_configured`
- **WHEN** 用户打开数据配置页的知识库 Tab
- **THEN** 展示引导面板，包含：知识库功能介绍（RAG 增强分析能力说明）、分步快速部署命令（支持一键复制）、WeKnora 官方文档和 GitHub 链接、"测试连接"按钮

#### Scenario: 数据配置页知识库服务不可达
- **GIVEN** 后端返回知识库状态为 `unreachable`
- **WHEN** 用户打开数据配置页的知识库 Tab
- **THEN** 展示错误状态，提示服务不可达，显示排查建议（检查服务运行状态、网络连接、端口），提供"重试连接"按钮

#### Scenario: 聊天页未启用知识库的功能提示
- **GIVEN** 知识库未配置或不可用
- **WHEN** 用户进入聊天页看到 welcome-state 功能卡片
- **THEN** 知识库功能卡片以灰色/半透明样式展示，标注"需部署知识库服务"，点击跳转到 `/datamanage/config?tab=knowledge` 配置页

#### Scenario: 测试连接功能
- **WHEN** 用户在知识库配置页点击"测试连接"按钮
- **THEN** 后端向 WeKnora 发送健康检查请求，返回连接结果（成功/失败 + 错误信息），前端即时展示测试结果
