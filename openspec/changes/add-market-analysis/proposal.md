# Change: 增强M02行情分析模块 - 技术指标计算与可视化

## Why

根据任务大纲，M02行情分析是P0优先级功能模块，当前系统已有基础的行情功能（K线获取、简单KDJ计算），但存在以下不足：

1. **技术指标不完整**：仅实现了KDJ计算，缺少MACD、RSI、BOLL、MA等核心指标
2. **指标计算不规范**：当前KDJ计算分散在service中，没有独立的技术指标服务
3. **K线数据获取依赖DB直连**：未遵循Plugin优先原则
4. **缺少AI走势分析**：没有集成LLM进行智能分析
5. **前端K线图简陋**：缺少专业的金融K线图表（无法显示多指标叠加）
6. **缺少行情概览**：没有大盘指数、市场热点等宏观信息

## What Changes

### 1. 技术指标服务 (TechnicalIndicatorService)

创建独立的技术指标计算服务，支持：

| 指标 | 参数 | 说明 |
|------|------|------|
| MA | period=[5,10,20,60,120,250] | 移动平均线 |
| EMA | period=[12,26] | 指数移动平均 |
| MACD | fast=12, slow=26, signal=9 | 异同移动平均线 |
| RSI | period=14 | 相对强弱指标 |
| KDJ | n=9, m1=3, m2=3 | 随机指标 |
| BOLL | period=20, std=2 | 布林带 |
| ATR | period=14 | 平均真实波幅 |
| OBV | - | 能量潮 |
| DMI | period=14 | 趋向指标 |
| CCI | period=14 | 顺势指标 |

### 2. MarketAgent 增强

继承`LangGraphAgent`基类，新增行情分析能力：

**Agent Tools**：
| 工具函数 | 功能描述 |
|---------|---------|
| `get_kline(code, period, adjust)` | 获取K线数据 |
| `calculate_indicators(code, indicators)` | 计算技术指标 |
| `analyze_trend(code)` | AI走势分析 |
| `get_market_overview()` | 市场概览 |
| `get_index_data(index_code)` | 获取指数行情 |
| `find_pattern(code)` | 形态识别（头肩顶、双底等） |

### 3. 后端API增强

新增/增强API端点：
- `POST /api/market/kline` - K线数据（增强：使用Plugin Service）
- `POST /api/market/indicators` - 技术指标（增强：支持全部指标）
- `POST /api/market/analysis` - **新增** AI走势分析
- `GET /api/market/overview` - **新增** 市场概览
- `GET /api/market/index/{code}` - **新增** 指数行情
- `POST /api/market/pattern` - **新增** 形态识别
- `GET /api/market/hot-sectors` - **新增** 热门板块

### 4. 前端组件增强

- `MarketView.vue` - 行情主界面（增强布局）
- `KLineChart.vue` - K线图表（增强：使用ECharts专业K线、支持多指标）
- `IndicatorPanel.vue` - **新增** 指标面板（指标选择、参数配置）
- `MarketOverview.vue` - **新增** 市场概览组件
- `IndexChart.vue` - **新增** 指数走势图
- `TrendAnalysis.vue` - **新增** AI分析结果展示

### 5. 数据访问优化

遵循Plugin优先原则，使用已有服务：
- `TuShareDailyService` - 日线行情
- `TuShareIndexDailyService` - 指数日线
- `TuShareAdjFactorService` - 复权因子

## Impact

### Affected Specs
- market-analysis（新增）

### Affected Code

**后端**：
- `src/stock_datasource/modules/market/router.py` - 增强API路由
- `src/stock_datasource/modules/market/service.py` - 增强行情服务
- `src/stock_datasource/modules/market/schemas.py` - 增强数据模型
- `src/stock_datasource/modules/market/indicators.py` - **新增** 技术指标计算
- `src/stock_datasource/agents/market_agent.py` - **新增** 行情Agent

**前端**：
- `frontend/src/views/market/MarketView.vue` - 增强行情界面
- `frontend/src/views/market/components/` - **新增** 子组件目录
- `frontend/src/components/charts/KLineChart.vue` - 增强K线图表
- `frontend/src/api/market.ts` - 增强API
- `frontend/src/stores/market.ts` - 增强状态管理

### Dependencies
- 依赖 `tushare_daily` 插件获取日线数据
- 依赖 `tushare_index_daily` 插件获取指数数据
- 依赖 `tushare_adj_factor` 插件获取复权因子
- 依赖 `LangGraphAgent` 基类（AI分析）
- 依赖 Langfuse 配置（LLM可观测性）
- 依赖 ECharts 图表库（前端）

### Data Tables
- `ods_daily` - A股日线行情
- `ods_index_daily` - 指数日线
- `ods_adj_factor` - 复权因子
- `ods_stock_basic` - 股票基础信息
