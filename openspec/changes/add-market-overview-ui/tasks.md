# Tasks: ETF/指数行情展示与每日概览

## Phase 1: 后端通用基础设施 (P0)

### 1.1 创建通用列表服务基类
- [x] 创建 `src/stock_datasource/core/base_list_service.py`
- [x] 实现通用分页、筛选、搜索逻辑
- [ ] 添加单元测试验证基类功能

### 1.2 重构 Index Service 使用基类
- [ ] IndexService 继承 BaseListService
- [x] 验证现有功能不受影响
- [ ] 更新相关测试

## Phase 2: ETF后端模块 (P0)

### 2.1 创建ETF模块结构
- [x] 创建 `src/stock_datasource/modules/etf/__init__.py`
- [x] 创建 `src/stock_datasource/modules/etf/schemas.py`
- [x] 创建 `src/stock_datasource/modules/etf/service.py`
- [x] 创建 `src/stock_datasource/modules/etf/router.py`

### 2.2 实现ETF列表接口
- [x] 实现 `GET /etfs` - ETF列表（分页、筛选）
- [x] 实现 `GET /exchanges` - 交易所列表
- [x] 实现 `GET /types` - ETF类型列表
- [ ] 验证：调用API返回正确的ETF列表

### 2.3 实现ETF详情接口
- [x] 实现 `GET /etfs/{ts_code}` - ETF详情
- [ ] 验证：返回完整的ETF基础信息

### 2.4 实现ETF行情接口
- [x] 实现 `GET /etfs/{ts_code}/daily` - 日线数据
- [x] 实现 `GET /etfs/{ts_code}/kline` - K线数据（含复权）
- [ ] 验证：K线数据正确计算复权价格

### 2.5 实现ETF AI分析
- [x] 创建 `src/stock_datasource/agents/etf_tools.py` - ETF分析工具集
  - `get_etf_basic_info` - 获取ETF基础信息
  - `get_etf_daily_data` - 获取日线数据
  - `get_etf_tracking_index` - 获取跟踪指数信息
  - `calculate_etf_metrics` - 计算ETF指标（跟踪误差、折溢价等）
- [x] 创建 `src/stock_datasource/agents/etf_agent.py` - ETF Agent
- [x] 实现 `POST /analyze` - ETF AI量化分析接口
- [x] 实现 `GET /etfs/{ts_code}/quick-analysis` - 快速分析接口
- [ ] 验证：AI分析返回有效结果，支持多轮对话

### 2.6 注册ETF路由
- [x] 在 `src/stock_datasource/modules/__init__.py` 注册 `/api/etf` 路由
- [ ] 验证：所有ETF接口可访问

## Phase 3: Index模块扩展 (P0)

### 3.1 添加指数行情接口
- [x] 实现 `GET /indices/{ts_code}/daily` - 指数日线
- [x] 实现 `GET /indices/{ts_code}/kline` - 指数K线
- [ ] 验证：返回正确的指数行情数据

## Phase 4: 每日概览后端模块 (P1)

### 4.1 创建Overview模块结构
- [x] 创建 `src/stock_datasource/modules/overview/__init__.py`
- [x] 创建 `src/stock_datasource/modules/overview/schemas.py`
- [x] 创建 `src/stock_datasource/modules/overview/service.py`
- [x] 创建 `src/stock_datasource/modules/overview/router.py`

### 4.2 实现每日概览接口
- [x] 实现 `GET /overview/daily` - 每日市场概览
  - 主要指数涨跌（沪深300、中证500等）
  - 市场统计（涨跌家数、成交额）
- [ ] 验证：返回当日市场概览数据

### 4.3 实现热门ETF接口
- [x] 实现 `GET /overview/hot-etfs` - 热门ETF
  - 支持按成交额/涨跌幅排序
  - 支持limit参数
- [ ] 验证：返回正确排序的ETF列表

### 4.4 实现市场概览AI分析
- [x] 创建 `src/stock_datasource/agents/overview_tools.py` - 市场概览工具集
  - `get_major_indices_status` - 获取主要指数状态
  - `get_market_breadth` - 获取市场广度（涨跌家数）
  - `get_sector_performance` - 获取板块表现
  - `get_hot_etfs_analysis` - 获取热门ETF分析
  - `get_market_sentiment` - 获取市场情绪指标
- [x] 创建 `src/stock_datasource/agents/overview_agent.py` - 市场概览Agent
- [x] 实现 `POST /overview/analyze` - 市场AI分析接口
- [x] 实现 `GET /overview/quick-analysis` - 市场快速分析接口
- [ ] 验证：AI分析返回有效结果，支持多轮对话

### 4.5 注册Overview路由
- [x] 在 `src/stock_datasource/modules/__init__.py` 注册 `/api/overview` 路由
- [ ] 验证：所有概览接口可访问

## Phase 4B: 同花顺板块指数后端 (P1) - 新增

### 4B.1 创建THS Index模块
- [x] 数据插件 `tushare_ths_index` 已创建
- [x] 数据插件 `tushare_ths_daily` 已创建
- [x] 数据已入库（1,724条板块元数据）
- [x] 创建 `src/stock_datasource/modules/ths_index/__init__.py`
- [x] 创建 `src/stock_datasource/modules/ths_index/schemas.py`
- [x] 创建 `src/stock_datasource/modules/ths_index/service.py`
- [x] 创建 `src/stock_datasource/modules/ths_index/router.py`

### 4B.2 实现THS Index API
- [x] 实现 `GET /api/ths-index/list` - 板块指数列表
  - 支持 exchange 筛选（A/HK/US）
  - 支持 type 筛选（N-概念/I-行业/R-地域）
- [x] 实现 `GET /api/ths-index/{ts_code}/daily` - 板块日线数据
- [x] 实现 `GET /api/ths-index/ranking` - 板块涨跌排行
  - 支持 sort_by（pct_change/vol/turnover_rate）
  - 支持 order（desc/asc）
- [x] 实现 `GET /api/ths-index/search` - 板块搜索
- [ ] 验证：所有THS Index接口可访问

### 4B.3 注册THS Index路由
- [x] 在 `src/stock_datasource/modules/__init__.py` 注册 `/api/ths-index` 路由

## Phase 5: 前端通用组件 (P0)

### 5.1 创建通用列表组件
- [x] ETF列表视图直接实现（未抽取独立组件）
- [x] 支持配置化列定义
- [x] 支持配置化筛选条件
- [x] 支持分页、搜索
- [ ] 验证：组件可正常渲染和交互

### 5.2 创建通用筛选面板
- [x] ETF视图内置筛选面板
- [x] 支持多种筛选类型（下拉、输入）
- [ ] 验证：筛选条件变更触发回调

## Phase 6: ETF前端界面 (P0)

### 6.1 创建ETF API和Store
- [x] 创建 `frontend/src/api/etf.ts`
- [x] 创建 `frontend/src/stores/etf.ts`
- [ ] 验证：API调用正常

### 6.2 创建ETF主视图
- [x] 创建 `frontend/src/views/etf/EtfScreenerView.vue`
- [x] 实现ETF列表展示
- [x] 实现筛选功能（交易所、类型、管理人）
- [x] 实现搜索功能
- [ ] 验证：ETF列表正确展示和筛选

### 6.3 创建ETF详情弹窗
- [x] 创建 `frontend/src/views/etf/components/EtfDetailDialog.vue`
- [x] 展示ETF基础信息
- [x] 展示跟踪指数信息
- [ ] 验证：详情弹窗正确展示

### 6.4 创建ETF K线面板
- [x] K线功能集成在详情弹窗中
- [x] 复用现有KLineChart组件
- [ ] 支持复权切换
- [ ] 验证：K线图正确渲染

### 6.5 创建ETF AI分析面板
- [x] 创建 `frontend/src/views/etf/components/EtfAnalysisPanel.vue`
- [x] 参考IndexAnalysisPanel实现
- [x] 支持快速分析（无AI）
- [x] 支持AI深度分析（多轮对话）
- [ ] 验证：AI分析面板正常工作

### 6.6 添加ETF路由
- [x] 在 `frontend/src/router/index.ts` 添加 `/etf` 路由
- [ ] 在侧边栏菜单添加ETF入口
- [ ] 验证：可正常访问ETF页面

## Phase 7: 行情分析页面增强 (P1)

### 7.1 创建概览API和Store
- [x] 创建 `frontend/src/api/overview.ts`
- [x] 创建 `frontend/src/stores/overview.ts`
- [ ] 验证：API调用正常

### 7.2 增强MarketView布局
- [x] 添加每日概览卡片区域
- [x] 展示主要指数涨跌（一排横向展示）
- [x] 展示热门ETF列表
- [ ] 支持切换股票/ETF/指数行情
- [ ] 验证：概览数据正确展示

### 7.3 添加快捷入口
- [ ] 添加常用指数快捷标签
- [ ] 添加热门ETF快捷入口
- [ ] 验证：点击快捷入口跳转正确

### 7.4 创建AI问答悬浮窗
- [x] 创建 `frontend/src/components/market/MarketAiFloatButton.vue` - 悬浮按钮
- [x] 创建 `frontend/src/components/market/MarketAiDialog.vue` - 悬浮窗组件
- [x] 复用智能对话组件界面
- [x] 实现行情分析预设问题：
  - "今日市场整体表现如何？"
  - "哪些板块表现最强？"
  - "今日热门ETF有哪些？"
  - "当前市场情绪如何？"
  - "今日涨停板有多少家？"
  - "哪些行业板块领涨？"
- [x] 支持悬浮窗拖拽、最小化、关闭
- [ ] 验证：AI问答悬浮窗正常工作

## Phase 7B: 板块热力图与排行榜前端 (P1) - 新增

### 7B.1 创建THS Index API和Store
- [x] 创建 `frontend/src/api/thsIndex.ts`
- [x] 创建 `frontend/src/stores/thsIndex.ts`
- [ ] 验证：API调用正常

### 7B.2 创建板块热力图组件
- [x] 创建 `frontend/src/components/market/SectorHeatmap.vue`
- [x] 实现行业/概念/地域板块切换
- [x] 实现热力图颜色映射（涨跌幅→红绿色深浅）
- [x] 支持点击板块查看详情
- [ ] 验证：热力图正确渲染

### 7B.3 创建板块详情弹窗
- [x] 创建 `frontend/src/components/market/SectorDetailDialog.vue`
- [x] 展示板块K线走势（近30日）
- [x] 展示板块基本信息
- [ ] 验证：详情弹窗正确展示

### 7B.4 创建板块涨跌排行组件
- [x] 创建 `frontend/src/components/market/SectorRankingTable.vue`
- [x] 实现涨幅榜/跌幅榜/换手率榜切换
- [x] 实现板块类型筛选
- [ ] 验证：排行榜正确展示

### 7B.5 创建指数走势对比图
- [x] 创建 `frontend/src/components/market/IndexCompareChart.vue`
- [x] 实现多指数叠加走势（归一化百分比）
- [x] 支持添加/移除对比指数
- [x] 支持时间范围切换（7日/30日/90日）
- [ ] 验证：对比图正确渲染

### 7B.6 整合到MarketView
- [x] 在MarketView第二行添加板块热力图区域
- [x] 主内容区改为左右两栏布局（板块排行 + 指数对比）
- [x] 移除 Tab 导航和 K线图表（K线在详情弹窗中展示）
- [x] 美化整体布局样式
- [ ] 验证：所有组件正确集成

## Phase 8: 测试与优化 (P2)

### 8.1 后端测试
- [ ] 添加ETF模块单元测试
- [ ] 添加Overview模块单元测试
- [ ] 添加THS Index模块单元测试
- [ ] 添加集成测试

### 8.2 前端测试
- [ ] 添加ETF视图组件测试
- [ ] 添加通用组件测试
- [ ] 添加板块热力图组件测试

### 8.3 性能优化
- [ ] 添加概览数据缓存
- [ ] 优化列表查询性能
- [ ] 添加数据加载骨架屏

## 依赖关系

```
Phase 1 (基础设施)
    │
    ├──▶ Phase 2 (ETF后端) ──▶ Phase 6 (ETF前端)
    │
    ├──▶ Phase 3 (Index扩展)
    │
    ├──▶ Phase 4 (概览后端) ──▶ Phase 7 (行情增强)
    │                              │
    │                              └──▶ Phase 7.4 (AI悬浮窗)
    │
    └──▶ Phase 4B (THS Index后端) ──▶ Phase 7B (板块热力图/排行榜)

Phase 5 (通用组件) ──▶ Phase 6, Phase 7, Phase 7B

Phase 8 (测试优化) 依赖所有其他Phase
```

## 可并行任务

- Phase 2 和 Phase 3 可并行
- Phase 4 和 Phase 4B 可并行（数据插件已就绪）
- Phase 5 和 Phase 2/3/4/4B 可并行
- Phase 6 和 Phase 7 可并行（在各自后端完成后）
- Phase 7.4 (AI悬浮窗) 和 Phase 7B 可并行

## 实施总结

### 已完成
- Phase 1-7 核心功能已实现
- 后端：ETF模块、Overview模块、Index扩展
- 前端：ETF视图、MarketView增强、API和Store
- **新增：同花顺板块指数数据插件（tushare_ths_index, tushare_ths_daily）已创建并入库**

### 待完成
- ~~Phase 4B：THS Index 后端 API 模块~~ ✅
- ~~Phase 7.4：AI问答悬浮窗（复用智能对话组件，内置预设问题）~~ ✅
- ~~Phase 7B：板块热力图、涨跌排行榜、指数走势对比图~~ ✅
- 验证测试（需要运行环境）
- Phase 8 测试与优化
- 侧边栏菜单入口
