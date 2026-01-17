# Design: M02行情分析模块技术设计

## Context

M02行情分析模块是AI智能选股与分析平台的核心功能之一（P0优先级），负责提供股票K线、技术指标计算和AI走势分析能力。当前系统已有基础实现，但技术指标不完整且未遵循Plugin优先原则。

### 利益相关者
- 用户：需要专业的技术分析工具辅助投资决策
- 开发者：需要清晰的模块边界和可扩展的架构
- 其他模块：M03选股、M08回测依赖技术指标计算能力

### 约束
- 必须使用Plugin Service获取数据，不直接写SQL
- 技术指标计算需高效（单次请求<500ms）
- 前端图表需支持移动端响应式
- AI分析需集成Langfuse可观测性

## Goals / Non-Goals

### Goals
- 提供完整的技术指标计算服务（MA/MACD/RSI/KDJ/BOLL等）
- 实现AI走势分析功能
- 增强K线图表，支持多指标叠加显示
- 提供市场概览（大盘指数、涨跌统计）

### Non-Goals
- 不实现实时行情推送（当前为T+1数据）
- 不实现自定义公式指标编辑器
- 不实现高频交易相关指标

## Decisions

### 决策1：技术指标计算独立模块

**选择**：创建独立的 `indicators.py` 模块，基于pandas/numpy实现

**理由**：
- 指标计算逻辑复杂，独立模块便于测试和维护
- pandas/numpy性能足够（单股100日数据<10ms）
- 可被多个模块复用（行情分析、选股、回测）

**替代方案**：
- 使用TA-Lib库：依赖C扩展，安装复杂
- 数据库端计算：DuckDB不支持窗口函数嵌套，复杂度高

### 决策2：K线图表使用ECharts

**选择**：使用ECharts K线专业组件

**理由**：
- 项目已引入ECharts依赖
- ECharts K线图功能完善（缩放、十字光标、多图联动）
- 中文文档丰富，社区活跃

**替代方案**：
- TradingView Lightweight Charts：轻量但功能有限
- AnyChart：商业授权，成本高

### 决策3：MarketAgent架构

**选择**：继承LangGraphAgent基类，使用Tool调用模式

**理由**：
- 与现有Agent架构一致（ScreenerAgent）
- Tool模式便于添加新能力
- 自动获得Langfuse追踪支持

**架构图**：
```
用户查询
    │
    ▼
┌─────────────┐
│ MarketAgent │
│ (LangGraph) │
└──────┬──────┘
       │ 调用Tools
       ▼
┌──────────────────────────────────────────┐
│                 Tools                     │
├────────────┬───────────┬────────────────┤
│ get_kline  │calc_inds  │ analyze_trend  │
└─────┬──────┴─────┬─────┴───────┬────────┘
      │            │             │
      ▼            ▼             ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Plugin   │ │indicators│ │   LLM    │
│ Services │ │   .py    │ │  Client  │
└──────────┘ └──────────┘ └──────────┘
```

### 决策4：指标参数配置

**选择**：前端配置指标参数，后端校验并计算

**理由**：
- 用户可能需要调整参数（如MA周期）
- 后端校验确保参数合法
- 默认参数内置，简化常用场景

**数据流**：
```
前端选择指标 → 可选配置参数 → POST /indicators → 后端校验 → 计算 → 返回
```

## Risks / Trade-offs

### 风险1：指标计算性能
- **风险**：大量指标同时计算可能导致响应慢
- **缓解**：
  - 限制单次最多5个指标
  - 使用numpy向量化计算
  - 考虑Redis缓存热门股票指标

### 风险2：AI分析幻觉
- **风险**：LLM可能生成不准确的投资建议
- **缓解**：
  - 提供结构化数据给LLM，减少幻觉
  - 添加风险提示免责声明
  - 使用Langfuse监控分析质量

### 风险3：前端图表复杂度
- **风险**：多指标叠加可能导致图表混乱
- **缓解**：
  - 主图/副图分离（K线+MA在主图，MACD/RSI在副图）
  - 限制同时显示的指标数量
  - 提供预设配置（简洁/标准/专业）

## Data Models

### 技术指标请求
```python
class IndicatorRequest(BaseModel):
    code: str                     # 股票代码
    indicators: List[str]         # 指标列表 ["MA", "MACD"]
    period: int = 60              # 计算周期（天）
    params: Optional[Dict] = None # 指标参数 {"MA": {"periods": [5,10,20]}}
```

### 技术指标响应
```python
class IndicatorResponse(BaseModel):
    code: str
    name: str
    indicators: Dict[str, List[IndicatorPoint]]
    # 示例: {"MA5": [{"date": "2024-01-15", "value": 100.5}, ...]}
```

### AI分析响应
```python
class TrendAnalysisResponse(BaseModel):
    code: str
    name: str
    trend: str           # "上涨趋势" / "下跌趋势" / "震荡"
    support: float       # 支撑位
    resistance: float    # 压力位
    signals: List[str]   # 技术信号 ["MACD金叉", "RSI超买"]
    summary: str         # AI分析摘要
    disclaimer: str      # 风险提示
```

## Migration Plan

1. **Phase 1**：后端指标服务（Task 1.x）
   - 创建indicators.py
   - 增强service.py使用Plugin
   - 无破坏性变更

2. **Phase 2**：API增强（Task 2.x）
   - 增强现有/indicators端点（兼容）
   - 新增/overview, /analysis端点
   - 无破坏性变更

3. **Phase 3**：前端增强（Task 4-6.x）
   - 增强KLineChart组件
   - 新增子组件
   - 无破坏性变更

4. **Rollback**：
   - 所有变更均为增量添加，可独立回滚
   - 旧API保持兼容

## Open Questions

1. ~~是否需要支持分钟K线？~~ 
   - 决定：当前仅支持日K，后续根据需求扩展

2. ~~指标计算是否需要缓存？~~
   - 决定：初版不缓存，性能瓶颈时再加Redis缓存

3. AI分析的触发频率限制？
   - 待定：需与产品确认是否需要限流
