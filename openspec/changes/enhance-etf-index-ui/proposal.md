# Change: 增强ETF和指数界面

## Why

当前系统存在以下界面问题：

1. **ETF 页面筛选条件不足**：
   - 缺少基于日期切换查看历史数据
   - 缺少按管理人筛选（基金公司）
   - 缺少按跟踪指数筛选
   - 缺少按费率区间筛选
   - 缺少按成交额/流动性筛选
   - 缺少行情相关筛选（涨跌幅区间、近N日涨幅等）

2. **指数页面缺失**：
   - 路由中未注册指数菜单
   - `App.vue` 菜单项中缺少指数入口
   - 指数页面 `IndexScreenerView.vue` 已存在但无法访问
   - 指数页面筛选条件较少（仅市场、类别、搜索）

3. **界面一致性**：
   - 指数和 ETF 页面结构相似，应复用样式
   - 需保持一致的用户体验

4. **数据更新提示缺失**：
   - 用户切换日期时若无数据，无法提示并引导更新

## What Changes

### 1. 新增指数菜单入口

在 `App.vue` 和 `router/index.ts` 中添加指数菜单：
- 路径：`/index`
- 标题：`指数行情`
- 图标：`TrendingUpIcon` (或类似图标)
- 位置：紧挨 ETF 菜单之后

### 2. 核心筛选功能（优先级最高）

#### 2.1 日期切换功能
- **ETF/指数页面新增日期选择器**
- 默认显示最新交易日数据
- 支持选择历史日期查看当日行情
- **无数据提示**：切换日期后若无数据，弹窗提示用户：
  - 提示文案：`当前日期 {date} 暂无数据，是否立即更新？`
  - 按钮选项：`立即更新` / `取消`
  - Tip 提示：`您也可以在「数据管理」中执行对应的插件来更新数据`

#### 2.2 名称/代码检索
- 保持现有 keyword 搜索功能
- 支持模糊匹配：代码、简称、全称、跟踪指数名称（ETF）

### 3. 增强 ETF 页面筛选条件

新增筛选维度：
- **管理人**：基金公司下拉选择
- **跟踪指数**：按跟踪指数筛选
- **管理费率区间**：0-0.2%、0.2%-0.5%、0.5%以上
- **成交额区间**：按日均成交额筛选（流动性）
- **涨跌幅区间**：今日涨跌幅筛选
- **近N日涨幅**：近5日/20日涨跌幅

### 4. 增强指数页面筛选条件

新增筛选维度（与 ETF 保持一致的体验）：
- **发布机构**：中证、上证、深证等
- **指数类型**：综合指数、规模指数、行业指数等
- **涨跌幅区间**：今日涨跌幅筛选
- **近N日涨幅**：近5日/20日涨跌幅

### 5. 新增后端 API

#### ETF 相关 API
- `GET /api/etf/managers` - 获取管理人列表
- `GET /api/etf/tracking-indices` - 获取跟踪指数列表
- `GET /api/etf/trade-dates` - 获取可用交易日期列表
- `GET /api/etf/etfs` 新增参数：
  - `trade_date`: 交易日期筛选
  - `manager`: 管理人筛选
  - `tracking_index`: 跟踪指数筛选
  - `fee_min` / `fee_max`: 费率区间
  - `amount_min`: 最小成交额
  - `pct_chg_min` / `pct_chg_max`: 涨跌幅区间

#### 指数相关 API
- `GET /api/index/publishers` - 获取发布机构列表
- `GET /api/index/trade-dates` - 获取可用交易日期列表
- `GET /api/index/indices` 新增参数：
  - `trade_date`: 交易日期筛选
  - `publisher`: 发布机构筛选
  - `pct_chg_min` / `pct_chg_max`: 涨跌幅区间

### 6. 样式统一

- 指数页面复用 ETF 页面的卡片样式、筛选面板布局
- 统一快速访问区域的渐变色系（ETF 粉色系、指数紫色系）
- 保持一致的表格列样式和分页组件

## Impact

### Affected Code

**前端**：
- `frontend/src/App.vue` - 添加指数菜单项
- `frontend/src/router/index.ts` - 添加指数路由
- `frontend/src/views/etf/EtfScreenerView.vue` - 增强筛选条件，添加日期选择
- `frontend/src/views/index/IndexScreenerView.vue` - 增强筛选条件，复用 ETF 样式
- `frontend/src/api/etf.ts` - 新增 API 接口
- `frontend/src/api/index.ts` - 新增 API 接口
- `frontend/src/stores/etf.ts` - 新增筛选状态
- `frontend/src/stores/index.ts` - 新增筛选状态
- `frontend/src/components/DataUpdateDialog.vue` - 新增数据更新提示弹窗组件

**后端**：
- `src/stock_datasource/modules/etf/router.py` - 新增 API 端点
- `src/stock_datasource/modules/etf/service.py` - 新增服务方法
- `src/stock_datasource/modules/index/router.py` - 新增 API 端点
- `src/stock_datasource/modules/index/service.py` - 新增服务方法

### Dependencies
- 后端 ETF API 已支持基本筛选（market、fund_type、invest_type、status、keyword）
- 后端指数 API 已支持基本筛选（market、category、keyword）
- 数据来源：`ods_etf_basic`、`ods_etf_fund_daily`、`dim_index_basic`、`ods_index_daily`

### UI/UX
- 保持移动端响应式设计
- 筛选条件过多时可使用折叠/展开
- 无数据时友好提示并引导用户操作
