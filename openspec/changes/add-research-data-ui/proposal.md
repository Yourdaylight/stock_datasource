# Change: 添加研究数据综合页面并整合龙虎榜

## Why

当前系统已完成 `tushare_stk_surv`（机构调研）和 `tushare_report_rc`（研报盈利预测）两个插件的后端实现，但缺少前端展示页面。同时，现有的"财报研读"、"龙虎榜分析"分散在不同页面，用户需要多次跳转才能获取完整的研究信息。

整合目标：
1. 将机构调研、研报数据、财报研读整合到统一的"研究数据"页面
2. 将龙虎榜分析整合到"行情分析"页面

## What Changes

1. **新增前端 API 模块** - 创建 `research.ts` 调用机构调研和研报数据接口
2. **新增研究数据页面** - 创建 `/research` 路由，整合：
   - Tab 1: 机构调研（新增）
   - Tab 2: 研报数据（新增）
   - Tab 3: 财报研读（整合现有 ReportView）
3. **整合龙虎榜到行情分析** - 将龙虎榜分析作为行情分析页面的子模块
4. **调整路由和导航** - 移除独立路由，更新导航菜单

## Impact

- Affected specs: 新增 `research-data-ui` 规范
- Affected code:
  - `frontend/src/api/research.ts` (新增)
  - `frontend/src/views/research/ResearchView.vue` (新增)
  - `frontend/src/views/market/MarketView.vue` (修改)
  - `frontend/src/router/index.ts` (修改)
  - 移除 `/toplist` 和 `/report` 独立路由
