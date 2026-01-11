# Change: 实现财报分析Agent

## Why
学习 fin-agent 案例，结合现有的 tushare_finace_indicator 能力，实现一个完整的财报分析 Agent 系统。当前系统虽然有基础的财报数据获取能力和简单的 ReportAgent，但缺乏完整的财报分析功能，包括三大报表展示、财务指标计算、同业对比和 AI 财报解读等核心功能。

## What Changes
- **增强 ReportAgent**: 扩展现有 ReportAgent，集成 tushare_finace_indicator 数据源
- **新增财报服务**: 实现 FinancialReportService，提供三大报表数据获取和分析功能
- **扩展后端接口**: 完善 report 模块的 API 接口，支持财务数据、AI分析、对比分析
- **增强前端组件**: 扩展现有 ReportView.vue，新增财务表格、趋势图表、AI洞察组件
- **新增分析功能**: 实现财务指标计算、同业对比、AI财报解读等功能

## Impact
- affected specs: 需要创建新的 financial-report-analysis 能力规范
- affected code: 
  - `src/stock_datasource/agents/report_agent.py` - 增强现有 Agent
  - `src/stock_datasource/modules/report/` - 扩展 report 模块
  - `frontend/src/views/report/` - 增强前端财报界面
  - `src/stock_datasource/services/` - 新增财报服务