## 1. 前端 API 模块

- [x] 1.1 创建 `frontend/src/api/research.ts`，定义机构调研和研报数据接口
- [x] 1.2 添加 TypeScript 类型定义

## 2. 研究数据页面

- [x] 2.1 创建 `frontend/src/views/research/ResearchView.vue` 主页面（Tab 容器）
- [x] 2.2 创建 `InstitutionalSurveyPanel.vue` 机构调研面板组件
- [x] 2.3 创建 `ResearchReportPanel.vue` 研报数据面板组件
- [x] 2.4 整合现有财报分析组件到 `FinancialReportPanel.vue`

## 3. 龙虎榜整合

- [x] 3.1 修改 `MarketView.vue`，添加 Tab 切换支持龙虎榜
- [x] 3.2 将现有龙虎榜组件集成到行情分析页面
- [x] 3.3 创建 `TopListPanel.vue` 封装龙虎榜功能

## 4. 路由和导航

- [x] 4.1 添加 `/research` 路由配置
- [x] 4.2 移除 `/toplist` 和 `/report` 独立路由（添加重定向）
- [x] 4.3 更新导航菜单

## 5. 验证

- [x] 5.1 测试机构调研数据查询和展示
- [x] 5.2 测试研报数据查询和展示
- [x] 5.3 测试财报研读功能正常
- [x] 5.4 测试行情分析页面龙虎榜 Tab
- [x] 5.5 验证路由跳转正常
