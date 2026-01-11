# Change: 新增ETF/指数选股界面

## Why

当前系统已有三个指数相关数据插件（`tushare_index_basic`、`tushare_index_weight`、`tushare_idx_factor_pro`），但缺少专门的ETF/指数选股界面。用户无法：
1. 浏览和筛选指数列表（沪深300、中证500等）
2. 查看指数的成分股及权重分布
3. 获取基于ETF量化分析策略的AI投资建议

## What Changes

### 新增功能
- **ETF/指数列表页面**：展示所有指数的基础信息，支持按市场、类别筛选
- **指数详情面板**：展示指数成分股、权重分布、技术指标
- **AI量化分析**：基于ETF特有的量化分析策略提供投资建议

### 新增ETF Agent (`etf_agent.py`)
继承`LangGraphAgent`基类，专门处理ETF/指数量化分析任务：

**Agent职责**：
- 指数基础信息查询
- 成分股权重及集中度分析
- 基于80+技术指标的多维度分析
- 综合量化分析报告生成

**Agent Tools（基于实际schema.json中的指标）**：

| 工具函数 | 数据来源 | 功能描述 |
|---------|---------|---------|
| `get_index_info(ts_code)` | `dim_index_basic` | 获取指数基础信息（名称、市场、加权方式等） |
| `get_index_constituents(ts_code, trade_date)` | `ods_index_weight` | 获取成分股及权重 |
| `get_index_factors(ts_code, days)` | `ods_idx_factor_pro` | 获取最近N日技术因子 |
| `analyze_trend(ts_code)` | 均线+MACD+DMI | 分析趋势方向和强度 |
| `analyze_momentum(ts_code)` | KDJ+RSI+MTM+ROC | 分析动量和超买超卖 |
| `analyze_volatility(ts_code)` | ATR+BOLL+通道 | 分析波动率和支撑压力 |
| `analyze_volume(ts_code)` | OBV+VR+MFI | 分析量能和资金流向 |
| `analyze_sentiment(ts_code)` | PSY+BRAR+CCI+WR | 分析市场情绪 |
| `analyze_concentration(ts_code)` | 成分股权重 | 分析集中度风险（CR10、HHI） |
| `get_comprehensive_analysis(ts_code)` | 综合以上 | 生成完整分析报告 |

**System Prompt设计**：
- 角色：专业ETF/指数量化分析师
- 分析框架：趋势分析 → 动量分析 → 波动分析 → 量能分析 → 情绪分析 → 集中度分析 → 综合建议
- 输出格式：结构化Markdown报告，包含多空评分(0-100)

### 前端组件
- `ETFScreenerView.vue` - ETF选股主页面
- `ETFDetailDialog.vue` - 指数详情弹窗（成分股、权重、技术指标）
- `ETFAnalysisPanel.vue` - AI量化分析面板

### 后端接口
- `GET /api/etf/indices` - 获取指数列表（分页、筛选）
- `GET /api/etf/indices/{ts_code}` - 获取指数详情
- `GET /api/etf/indices/{ts_code}/constituents` - 获取成分股及权重
- `GET /api/etf/indices/{ts_code}/factors` - 获取技术因子数据
- `POST /api/etf/analyze` - AI量化分析接口（调用ETF Agent）

### ETF量化分析策略（基于ods_idx_factor_pro表80+技术指标）

**1. 趋势分析（权重30%）**
- 均线系统：MA5/10/20/60/250排列状态（多头/空头/交织）
- MACD指标：DIF/DEA/MACD柱状态、金叉死叉、零轴位置
- DMI趋势：+DI/-DI对比、ADX趋势强度（>25为趋势明确）

**2. 动量分析（权重25%）**
- KDJ指标：K/D/J值、超买(>80)/超卖(<20)
- RSI指标：RSI6/12/24、超买(>70)/超卖(<30)
- 动量指标：MTM/ROC方向和强度

**3. 波动分析（权重20%）**
- ATR波动率：当前波动水平
- 布林带：价格在通道中的位置、带宽变化
- 通道指标：唐安奇/肯特纳通道突破

**4. 量能分析（权重15%）**
- OBV能量潮：量价配合情况
- VR容量比率：成交活跃度
- MFI资金流量：资金流入流出

**5. 情绪分析（权重10%）**
- PSY心理线：市场情绪
- BRAR指标：人气(AR)和意愿(BR)
- CCI/WR：辅助超买超卖判断

**6. 集中度分析**
- CR10：前10大成分股权重占比
- HHI指数：赫芬达尔指数，衡量分散度

## Impact

### Affected Specs
- etf-screener（新增）

### Affected Code
- `src/stock_datasource/agents/etf_agent.py` - **新增ETF Agent**
- `src/stock_datasource/agents/etf_tools.py` - **新增ETF分析工具函数**
- `src/stock_datasource/agents/__init__.py` - 注册ETF Agent
- `frontend/src/views/etf/` - 新增ETF选股页面
- `frontend/src/api/etf.ts` - 新增ETF API
- `frontend/src/stores/etf.ts` - 新增ETF状态管理
- `frontend/src/router/index.ts` - 添加ETF路由
- `src/stock_datasource/modules/etf/` - 新增ETF后端模块
- `src/stock_datasource/modules/__init__.py` - 注册ETF模块

### Dependencies
- 依赖已有的三个指数插件数据及其service层
- 依赖现有的LangGraphAgent基类（`base_agent.py`）
- 依赖DeepAgents框架

### Data Tables
- `dim_index_basic` - 指数基础信息（名称、市场、发布方、加权方式、描述等）
- `ods_index_weight` - 指数成分权重（成分股代码、权重）
- `ods_idx_factor_pro` - 指数技术因子（80+指标：均线、MACD、KDJ、RSI、布林带、ATR、OBV、VR、MFI、PSY、BRAR、CCI、WR、DMI等）
