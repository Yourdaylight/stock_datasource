# Design: add-hk-smart-analysis

## Architecture Overview

当前智能对话系统的 Agent 编排架构如下：

```
用户查询 → OrchestratorAgent
              │
              ├── LLM 分类意图 → 选择 Agent
              │
              ├── MarketAgent (A股技术分析)    ← 需扩展支持港股
              ├── ReportAgent (A股财报分析)
              ├── HKReportAgent (港股财报分析) ← 已完整实现
              ├── ChatAgent (通用对话)
              ├── ScreenerAgent (智能选股)
              ├── BacktestAgent (策略回测)
              └── ...其他 Agent
```

### 核心改动点

#### 1. MarketAgent 系统提示词扩展

MarketAgent 的工具链（`get_kline` → `MarketService.get_kline` → `_get_hk_kline`）已经支持港股，但系统提示词仅描述 A 股。需要扩展提示词加入港股代码格式和分析场景。

```
变更前: "你是一个专业的A股技术分析师"
变更后: "你是一个专业的股票技术分析师，支持A股和港股分析"
```

#### 2. tools.py 港股数据路由

当前 `tools.py` 的工具函数直接查询 `ods_daily`（A 股表），需要加入市场类型检测：

```python
def get_stock_info(ts_code: str) -> str:
    if ts_code.upper().endswith('.HK'):
        return _get_hk_stock_info(ts_code)  # 查询 ods_hk_daily + ods_hk_basic
    # 原有 A 股逻辑
```

复用已有的 `detect_market_type` 函数进行统一路由。

#### 3. Orchestrator 港股多 Agent 编排

```python
# 当前逻辑
if stock_codes and primary_agent == "MarketAgent" and "ReportAgent" in agents:
    plan.append("ReportAgent")  # A股: MarketAgent + ReportAgent

# 新增逻辑
if has_hk_codes and primary_agent == "MarketAgent" and "HKReportAgent" in agents:
    plan.append("HKReportAgent")  # 港股: MarketAgent + HKReportAgent
```

### 数据流

```
用户: "分析腾讯 00700.HK 的技术面和财务情况"
  │
  └→ OrchestratorAgent
       ├── 意图分类: market_analysis
       ├── 提取股票代码: ["00700.HK"]
       ├── 检测到港股代码 → 构建多 Agent 计划
       │
       ├── MarketAgent (并发)
       │   ├── get_kline("00700.HK") → MarketService → ods_hk_daily
       │   ├── calculate_indicators("00700.HK") → 技术指标计算
       │   └── analyze_trend("00700.HK") → 趋势分析
       │
       ├── HKReportAgent (并发)
       │   ├── get_hk_comprehensive_financial_analysis("00700.HK")
       │   └── get_hk_financial_indicators("00700.HK")
       │
       └→ 合并结果 → 流式返回给用户
```

### 决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 技术指标计算逻辑 | 复用现有 `indicators.py` | 技术指标算法与市场无关，只需要 OHLCV 数据 |
| MarketAgent vs 新建 HKMarketAgent | 扩展 MarketAgent | MarketService 已统一支持，无需新建独立 Agent |
| tools.py 修改方式 | 路由模式（检测代码后缀） | 最小改动，向后兼容 |
