# Change: 将 Agent 中心升级为 AI Agent 投研工作台

## Why

当前 Agent 中心更像后台配置入口，`Agent Teams` 也偏技术编排语义；同时 Agent 竞技场作为主菜单项容易让用户把系统理解成策略 PK demo。专业投研/投顾场景更需要以投研角色、团队协作、研究任务、风险审查和决策留痕为中心的工作台。

## What Changes

- 将导航中的 `Agent中心` 改名为 `AI Agent 投研`。
- 将 `Agent管理`、`Agent Teams`、`Runtime` 分别改为 `投研 Agent`、`投研团队`、`工具运行时`。
- 将 `Agent竞技场` 从策略系统主菜单移入 AI Agent 投研下的 `策略实验室`，弱化为实验/候选比较入口。
- 调整 Agent 列表、Agent 编辑、团队列表、运行时页面文案，使其面向投研团队和研究任务。
- 在投研团队列表页增加专业模板入口：个股深度研究、组合调仓、事件冲击、盘后复盘。

## Impact

- Affected specs: `agent-teams`
- Affected code:
  - `frontend/src/App.vue`
  - `frontend/src/router/index.ts`
  - `frontend/src/views/agent-management/AgentList.vue`
  - `frontend/src/views/agent-management/AgentEditor.vue`
  - `frontend/src/views/agent-management/RuntimeManagement.vue`
  - `frontend/src/views/orchestration/OrchestrationList.vue`

## Non-Goals

- 本变更不改 Arena 后端执行逻辑。
- 本变更不引入自动交易或真实下单能力。
- 本变更不使用 mock 数据作为验证依据。
