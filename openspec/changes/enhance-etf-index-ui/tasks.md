# Tasks

## Phase 1: 后端 API 开发（优先）

### 1.1 ETF 后端 API
- [x] 1.1.1 新增 `GET /api/etf/managers` 获取管理人列表
- [x] 1.1.2 新增 `GET /api/etf/tracking-indices` 获取跟踪指数列表
- [x] 1.1.3 新增 `GET /api/etf/trade-dates` 获取可用交易日期
- [x] 1.1.4 扩展 `GET /api/etf/etfs` 支持新筛选参数：
  - `trade_date`: 指定交易日期
  - `manager`: 管理人
  - `tracking_index`: 跟踪指数
  - `fee_min/fee_max`: 费率区间
  - `amount_min`: 最小成交额
  - `pct_chg_min/pct_chg_max`: 涨跌幅区间

### 1.2 指数后端 API
- [x] 1.2.1 新增 `GET /api/index/publishers` 获取发布机构列表
- [x] 1.2.2 新增 `GET /api/index/trade-dates` 获取可用交易日期
- [x] 1.2.3 扩展 `GET /api/index/indices` 支持新筛选参数：
  - `trade_date`: 指定交易日期
  - `publisher`: 发布机构
  - `pct_chg_min/pct_chg_max`: 涨跌幅区间

## Phase 2: 指数菜单入口

- [x] 2.1 在 `router/index.ts` 添加指数路由
- [x] 2.2 在 `App.vue` 添加指数菜单项（位于 ETF 之后）
- [x] 2.3 验证指数页面可正常访问

## Phase 3: 核心筛选功能（优先级最高）

### 3.1 日期切换功能
- [x] 3.1.1 ETF 页面添加日期选择器组件
- [x] 3.1.2 指数页面添加日期选择器组件
- [x] 3.1.3 实现日期切换后重新加载数据

### 3.2 数据不存在提示
- [x] 3.2.1 创建 `DataUpdateDialog.vue` 弹窗组件
- [x] 3.2.2 实现无数据时弹窗逻辑
- [x] 3.2.3 弹窗内容包含：
  - 提示文案
  - 「立即更新」按钮（跳转数据管理）
  - 「取消」按钮
  - Tip 提示：可在数据管理中执行插件

### 3.3 名称/代码检索优化
- [x] 3.3.1 确保 keyword 支持模糊匹配多字段

## Phase 4: ETF 页面筛选增强

- [x] 4.1 更新 `api/etf.ts` 新增筛选参数接口
- [x] 4.2 更新 `stores/etf.ts` 新增筛选状态
- [x] 4.3 增强 `EtfScreenerView.vue` 筛选条件面板
  - [x] 添加日期选择器
  - [x] 添加管理人筛选
  - [x] 添加跟踪指数筛选
  - [x] 添加管理费率区间筛选
  - [x] 添加成交额区间筛选
  - [x] 添加涨跌幅区间筛选

## Phase 5: 指数页面增强

- [x] 5.1 更新 `api/index.ts` 新增筛选参数接口
- [x] 5.2 更新 `stores/index.ts` 新增筛选状态
- [x] 5.3 增强 `IndexScreenerView.vue` 筛选条件面板
  - [x] 添加日期选择器
  - [x] 添加发布机构筛选
  - [x] 添加涨跌幅区间筛选
- [x] 5.4 统一指数页面样式与 ETF 页面一致

## Phase 6: 测试验证

- [ ] 6.1 验证后端新 API 正常工作
- [ ] 6.2 验证日期切换和无数据提示功能
- [ ] 6.3 验证指数菜单和路由正常工作
- [ ] 6.4 验证 ETF 新增筛选条件功能
- [ ] 6.5 验证指数新增筛选条件功能
- [ ] 6.6 验证两个页面样式一致性
