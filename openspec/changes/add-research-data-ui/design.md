## Context

系统已实现机构调研（`tushare_stk_surv`）和研报盈利预测（`tushare_report_rc`）插件的后端服务，需要在前端提供数据展示界面。同时为了优化用户体验，将相关研究功能整合到统一页面。

### 现有后端 API

**机构调研 (StkSurvService):**
- `GET /api/stk_surv/get_surveys_by_date` - 按日期查询
- `GET /api/stk_surv/get_surveys_by_stock` - 按股票查询  
- `GET /api/stk_surv/get_hot_surveyed_stocks` - 热门调研股票
- `GET /api/stk_surv/get_org_type_stats` - 机构类型统计
- `GET /api/stk_surv/search_survey_content` - 内容搜索

**研报盈利预测 (ReportRcService):**
- `GET /api/report_rc/get_reports_by_date` - 按日期查询
- `GET /api/report_rc/get_reports_by_stock` - 按股票查询
- `GET /api/report_rc/get_hot_covered_stocks` - 热门覆盖股票
- `GET /api/report_rc/get_consensus_forecast` - 一致性预期
- `GET /api/report_rc/get_rating_distribution` - 评级分布

**财报分析 (现有):**
- 已有完整的 Store 和组件实现

## Goals / Non-Goals

### Goals
- 整合机构调研、研报数据、财报研读到统一"研究数据"页面
- 将龙虎榜整合到行情分析页面
- 减少独立页面数量，优化导航结构
- 统一的 UI 风格，与现有 TDesign 组件保持一致

### Non-Goals
- 不改变后端 API 实现
- 不新增数据分析功能（仅展示和整合）

## Decisions

### 页面结构重组

**整合前：**
```
/market    - 行情分析
/toplist   - 龙虎榜分析（独立）
/report    - 财报研读（独立）
```

**整合后：**
```
/market    - 行情分析
  ├── Tab: 市场概览
  └── Tab: 龙虎榜

/research  - 研究数据（新）
  ├── Tab: 机构调研
  ├── Tab: 研报数据
  └── Tab: 财报研读
```

### 组件复用策略

1. **龙虎榜组件**: 直接复用 `TopListTable`, `TopListAnalysis` 等
2. **财报组件**: 直接复用 `FinancialTable`, `TrendChart`, `AIInsight`
3. **新增组件**: 只新增机构调研和研报数据的展示组件

### 路由变更

```typescript
// 移除
{ path: '/toplist', ... }
{ path: '/report', ... }

// 新增  
{ path: '/research', name: 'Research', component: ResearchView, meta: { title: '研究数据' } }
```

## Risks / Trade-offs

- **用户习惯改变**: 财报研读从独立入口移到研究数据子 Tab
  - Mitigation: 功能完全保留，只是入口位置变化

- **页面加载**: 研究数据页面整合多个功能，首次加载可能稍慢
  - Mitigation: 使用懒加载，Tab 切换时才加载对应内容

## Migration Plan

1. 新增 API 模块和研究数据页面
2. 修改行情分析页面添加龙虎榜 Tab
3. 迁移财报组件到研究数据页面
4. 移除独立路由
5. 更新导航菜单
