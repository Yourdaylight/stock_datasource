# Change: 添加持仓管理功能

## Why

当前股票数据源项目缺乏完整的持仓管理功能，用户无法有效地：
- 记录和管理个人股票持仓
- 实时查看盈亏情况和投资组合表现
- 获得基于AI的持仓分析和建议
- 设置持仓预警和风险提示

学习 fin-agent 项目的优秀实践，我们需要构建一个完整的持仓管理系统，提供从数据录入到智能分析的全链路功能。

## What Changes

- **前端组件**: 新增持仓管理相关的Vue组件，包括持仓列表、添加持仓弹窗、盈亏图表、每日分析报告等
- **后端API**: 完善持仓管理的RESTful API接口，支持CRUD操作、汇总统计、盈亏历史等
- **Agent智能体**: 新增PortfolioAgent，提供持仓分析、风险评估、投资建议等AI功能
- **服务层**: 增强PortfolioService和新增DailyAnalysisService，提供核心业务逻辑
- **定时任务**: 新增每日持仓分析任务，自动生成投资报告和预警
- **数据模型**: 完善持仓相关的数据表结构和模型定义

## Impact

- 影响的规格: `portfolio-management` (新增), `agent-system` (修改), `api-endpoints` (修改)
- 影响的代码: 
  - 前端: `frontend/src/views/`, `frontend/src/components/`
  - 后端: `src/stock_datasource/modules/portfolio/`, `src/stock_datasource/agents/`
  - 服务: `src/stock_datasource/services/`, `src/stock_datasource/tasks/`
- **BREAKING**: 无破坏性变更，纯新增功能
- 数据库: 需要新增持仓分析相关表结构