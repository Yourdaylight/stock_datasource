# Capability: 前端导航 - 指数菜单

## ADDED Requirements

### Requirement: 指数菜单入口

系统 MUST 在侧边栏菜单中提供指数行情的入口。

**验收标准**：
- 菜单项位于「智能选ETF」之后
- 菜单标题为「指数行情」
- 菜单图标使用趋势图标
- 点击后跳转到 `/index` 路由
- 未登录用户显示锁定图标

#### Scenario: 已登录用户访问指数页面

**Given** 用户已登录系统
**When** 用户点击侧边栏「指数行情」菜单
**Then** 页面跳转到 `/index`
**And** 页面标题显示「指数行情」
**And** 指数列表正常加载

#### Scenario: 未登录用户点击指数菜单

**Given** 用户未登录系统
**When** 用户点击侧边栏「指数行情」菜单
**Then** 显示提示「请先登录」
**And** 页面跳转到登录页面
**And** 登录成功后自动跳转回指数页面

### Requirement: 指数路由配置

系统 MUST 配置指数页面的路由。

**验收标准**：
- 路由路径为 `/index`
- 路由名称为 `Index`
- 组件加载 `views/index/IndexScreenerView.vue`
- 路由需要登录认证

#### Scenario: 直接访问指数路由

**Given** 用户已登录系统
**When** 用户在浏览器地址栏输入 `/index`
**Then** 页面正常加载指数筛选视图
**And** 侧边栏菜单高亮「指数行情」项
