# Tasks: unify-news-center

## Task List

### Phase 1: 资讯中心页面重构

- [ ] **T1**: 重设计 `NewsView.vue` 为 Tab 布局
  - 添加三个 Tab：新闻快讯、机构调研、研报数据
  - 新闻快讯 Tab 改为两栏布局（列表 + 右侧面板）
  - 机构调研、研报 Tab 使用 `defineAsyncComponent` 懒加载
  - **验证**：三个 Tab 正常切换，内容正确显示

- [ ] **T2**: 新闻筛选内联化
  - 在 `NewsListPanel.vue` 顶部添加筛选工具栏
  - 提供来源/时间/分类下拉筛选
  - 移除 `NewsView.vue` 中独立 `NewsFilterPanel`
  - **验证**：筛选功能正常，新闻列表宽度增加

### Phase 2: 财报分析页面精简

- [ ] **T3**: 修改 `ResearchView.vue` 仅保留财报分析 Tab
  - 移除机构调研和研报数据 Tab
  - 标题与布局调整为"财报分析"
  - **验证**：`/research` 页面仅显示 A 股财报与港股财报

- [ ] **T4**: 更新侧边栏与路由 meta
  - 菜单名称由"研究数据"改为"财报分析"
  - 确保 `/research` 入口保留
  - **验证**：导航显示正确，路由正常访问

## Dependencies

- T1 依赖 T2（筛选内联化影响布局）
- T3 与 T4 可并行
