# Change: 新增M03智能选股模块

## Why

根据任务大纲，M03智能选股是P0优先级功能模块，当前系统已有基础的选股功能（条件筛选、预设策略），但存在以下不足：

1. **筛选维度有限**：仅支持PE/PB/换手率/涨跌幅等基础指标，缺少技术指标筛选
2. **自然语言选股不完善**：当前NL选股仅返回空结果，未真正实现AI解析
3. **缺少十维画像**：任务大纲要求基于多维度指标(十维画像)自动筛选股票
4. **缺少AI推荐**：没有基于用户偏好和市场状态的智能推荐功能
5. **缺少行业/板块筛选**：无法按行业、概念板块进行筛选

## What Changes

### 新增功能

#### 1. 多维度条件筛选增强
- **估值维度**：PE/PB/PS/股息率/市值等
- **技术维度**：均线位置、MACD信号、RSI超买超卖、KDJ金叉死叉
- **量能维度**：换手率、量比、成交额
- **涨跌维度**：日涨跌幅、N日涨跌幅、连涨连跌天数
- **行业维度**：行业分类、概念板块
- **财务维度**：ROE、营收增速、净利润增速（依赖财报数据）

#### 2. 十维画像选股
基于任务大纲要求，构建股票十维画像评分体系：
| 维度 | 权重 | 指标 |
|------|------|------|
| 估值 | 15% | PE百分位、PB百分位 |
| 成长 | 15% | 营收增速、净利润增速 |
| 盈利 | 10% | ROE、毛利率 |
| 动量 | 15% | 近期涨幅、相对强弱 |
| 趋势 | 10% | 均线多头排列、MACD |
| 量能 | 10% | 换手率、量比 |
| 波动 | 5% | 波动率、ATR |
| 资金 | 10% | 主力资金流向 |
| 情绪 | 5% | 涨停板、龙虎榜 |
| 风险 | 5% | ST风险、停牌风险 |

#### 3. 自然语言选股（NL Screener）
- 使用ScreenerAgent解析用户自然语言描述
- 转换为结构化筛选条件
- 支持模糊匹配和智能纠错
- 示例："找出低估值高成长的科技股"

#### 4. AI智能推荐
- 基于用户历史偏好推荐
- 基于市场热点推荐
- 基于策略回测结果推荐
- 每日精选推荐

#### 5. 预设策略增强
- **低估值策略**：PE<15, PB<2, 股息率>2%
- **高成长策略**：营收增速>20%, 净利润增速>30%
- **动量策略**：5日涨幅>10%, 量比>1.5
- **价值投资策略**：ROE>15%, PE<20, 连续盈利
- **技术突破策略**：突破20日均线, MACD金叉
- **龙头股策略**：行业龙头, 市值>500亿

### 后端增强

#### 数据访问原则

**优先使用 Plugin Services 获取数据**：所有数据访问应通过 `plugins/` 目录下的 Service 类进行，而非直接写 SQL 查询。

可用的 Plugin Services：
| Service | 功能 |
|---------|------|
| `TuShareDailyBasicService` | PE/PB/换手率等估值指标 |
| `TuShareStockBasicService` | 股票基本信息/行业/上市状态 |
| `TuShareDailyService` | 日线行情数据 |
| `TuShareFinaceIndicatorService` | 财务指标数据 |
| `TuShareAdjFactorService` | 复权因子 |

好处：
1. 统一数据访问接口，复用现有逻辑
2. Plugin Services 已实现输入验证和 SQL 注入防护
3. 数据表结构变更只需修改 Plugin Service
4. 便于 Mock 测试

#### ScreenerAgent 增强
继承`LangGraphAgent`基类，增强选股能力：

**Agent Tools**：
| 工具函数 | 功能描述 |
|---------|---------|
| `screen_by_conditions(conditions)` | 多条件组合筛选 |
| `screen_by_nl(query)` | 自然语言选股 |
| `get_stock_profile(ts_code)` | 获取股票十维画像 |
| `get_ai_recommendations(user_id)` | AI智能推荐 |
| `get_sector_stocks(sector)` | 行业板块选股 |
| `get_technical_signals()` | 技术信号选股 |

#### ScreenerService 新增
```python
class ScreenerService:
    # 多维度筛选
    async def filter_by_conditions(conditions: List[Condition]) -> List[Stock]
    
    # 十维画像计算
    async def calculate_profile(ts_code: str) -> StockProfile
    
    # 批量画像计算
    async def batch_calculate_profiles(ts_codes: List[str]) -> List[StockProfile]
    
    # 自然语言解析
    async def parse_nl_conditions(query: str) -> List[Condition]
    
    # AI推荐
    async def get_recommendations(user_id: str) -> List[Recommendation]
```

#### 新增API接口
- `POST /api/screener/filter` - 多条件筛选（增强）
- `POST /api/screener/nl` - 自然语言选股（增强）
- `GET /api/screener/profile/{ts_code}` - 获取股票画像
- `POST /api/screener/batch-profile` - 批量获取画像
- `GET /api/screener/recommendations` - AI推荐
- `GET /api/screener/sectors` - 获取行业列表
- `GET /api/screener/sectors/{sector}/stocks` - 行业内选股
- `GET /api/screener/signals` - 技术信号选股
- `POST /api/screener/presets/{id}/apply` - 应用预设策略

### 前端增强

#### 组件增强
- `ScreenerView.vue` - 选股主界面（增强）
- `ConditionBuilder.vue` - 条件构建器（增强，支持更多维度）
- `ProfileCard.vue` - **新增** 股票画像卡片
- `ProfileRadar.vue` - **新增** 十维画像雷达图
- `NLScreener.vue` - **新增** 自然语言选股组件
- `RecommendationPanel.vue` - **新增** AI推荐面板
- `SectorFilter.vue` - **新增** 行业板块筛选器
- `TechnicalSignals.vue` - **新增** 技术信号面板

#### Store增强
- 新增画像数据状态
- 新增推荐数据状态
- 新增行业筛选状态

## Impact

### Affected Specs
- stock-screener（新增）

### Affected Code

**后端**：
- `src/stock_datasource/modules/screener/router.py` - 增强API路由
- `src/stock_datasource/modules/screener/service.py` - **新增** 选股服务
- `src/stock_datasource/modules/screener/schemas.py` - **新增** 数据模型
- `src/stock_datasource/modules/screener/profile.py` - **新增** 十维画像计算
- `src/stock_datasource/agents/screener_agent.py` - 增强选股Agent
- `src/stock_datasource/agents/tools.py` - 增强选股工具

**前端**：
- `frontend/src/views/screener/ScreenerView.vue` - 增强选股界面
- `frontend/src/views/screener/components/` - 新增子组件
- `frontend/src/api/screener.ts` - 增强API
- `frontend/src/stores/screener.ts` - 增强状态管理

### Dependencies
- 依赖已有的 `ods_daily`、`ods_daily_basic`、`ods_stock_basic` 数据表
- 依赖已有的 `LangGraphAgent` 基类
- 依赖 M02 行情分析模块的技术指标计算能力
- **依赖 Langfuse 配置**：LLM 调用（自然语言选股、AI推荐）需要配置 Langfuse 实现可观测性

### Langfuse 配置要求

大模型调用需要配置 Langfuse 以实现可观测性：

```bash
# .env 配置
LANGFUSE_PUBLIC_KEY=pk-xxx      # Langfuse Public Key
LANGFUSE_SECRET_KEY=sk-xxx      # Langfuse Secret Key  
LANGFUSE_HOST=https://cloud.langfuse.com  # 或私有部署地址
LANGFUSE_ENABLED=true           # 启用 Langfuse
```

项目已有 Langfuse 集成（`src/stock_datasource/llm/client.py`），ScreenerAgent 需使用 `get_llm_client()` 获取已配置 Langfuse 追踪的 LLM 客户端。

### Data Tables
- `ods_daily` - 日线行情
- `ods_daily_basic` - 每日估值指标
- `ods_stock_basic` - 股票基础信息（行业分类）
- `ods_stk_limit` - 涨跌停数据
