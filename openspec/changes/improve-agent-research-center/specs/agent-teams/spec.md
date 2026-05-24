## ADDED Requirements

### Requirement: AI Agent 投研导航
系统 MUST 将 Agent 能力以专业投研工作台语义呈现，而不是以技术中心或竞技场作为主心智。

#### Scenario: 用户打开主导航
- **WHEN** 用户查看主导航
- **THEN** 系统展示 `AI Agent 投研` 入口，并包含 `投研 Agent`、`投研团队`、`哨兵选股`、`工具运行时` 等子入口

### Requirement: 投研团队模板
系统 MUST 在投研团队入口提供专业团队模板，帮助用户以真实投研任务启动协作流程。

#### Scenario: 用户创建投研团队
- **WHEN** 用户进入投研团队页面
- **THEN** 系统展示个股深度研究、组合调仓、事件冲击、盘后复盘等模板入口

### Requirement: 策略实验室弱化
系统 MUST 将竞技场定位为策略实验/候选比较能力，不应作为投研团队主流程默认入口。

#### Scenario: 用户查看策略系统菜单
- **WHEN** 用户查看策略系统
- **THEN** 系统不再在策略系统主菜单中展示 `Agent竞技场`

#### Scenario: 用户查看 AI Agent 投研菜单
- **WHEN** 用户查看 AI Agent 投研菜单
- **THEN** 系统以 `策略实验室` 名称提供旧竞技场能力入口
