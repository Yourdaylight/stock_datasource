# Proposal: unify-news-center

## Problem Statement

新闻资讯（`/news`）与研究数据（`/research`）中的机构调研、研报数据属于同一类"市场资讯"，但被分散在不同页面，用户需要在多个入口之间切换才能获取完整信息。

## Proposed Solution

### 策略：页面整合与布局重设计（不改变后端接口）

1. 将 `/news` 页面升级为"资讯中心"，采用 Tab 布局统一入口。
2. 资讯中心包含三个 Tab：**新闻快讯 / 机构调研 / 研报数据**。
3. 新闻快讯 Tab 改为两栏布局，筛选条件内联到列表上方工具栏。
4. 机构调研与研报数据 Tab 复用现有组件并懒加载。
5. `/research` 页面精简为"财报分析"，仅保留 A 股财报与港股财报 Tab。

## Impact

- **前端**：
  - 重设计 `NewsView.vue` → Tab 布局资讯中心
  - 新闻 Tab 内联筛选工具栏 + 两栏布局
  - 引入 `InstitutionalSurveyPanel` 与 `ResearchReportPanel`（懒加载）
  - 精简 `ResearchView.vue` 仅保留财报分析
  - 更新侧边栏菜单名称与路由 meta
- **后端**：不改动接口，不调整数据源

## Risks

- 页面迁移可能影响旧路径的用户习惯，需要保留 `/research` 入口
- 机构调研与研报组件较大，需懒加载避免首屏性能问题
