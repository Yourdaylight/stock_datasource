# Proposal: add-hk-smart-analysis

## Why

当前智能对话系统在处理港股分析请求时存在以下缺陷：

1. **MarketAgent 仅支持 A 股**：系统提示词明确写的是"A股技术分析师"，工具函数 (`tools.py`) 中的 `get_stock_info`、`get_stock_kline`、`calculate_technical_indicators` 全部硬编码查询 `ods_daily`，无法处理 `.HK` 代码。
2. **HK 技术分析能力未暴露给 Agent**：虽然 `MarketService` 底层已支持港股 K 线和技术指标计算（通过 `detect_market_type` 路由到 `ods_hk_daily`），但 MarketAgent 的工具函数已经封装好了这些能力，只是系统提示词未覆盖港股场景。
3. **无法组合港股技术分析 + 财报分析**：`OrchestratorAgent` 的 `_build_multi_agent_plan` 仅在 `MarketAgent` + `ReportAgent`（A 股财报）时触发并发执行，港股场景缺少 `MarketAgent` + `HKReportAgent` 的自动组合逻辑。
4. **工具函数不支持港股**：`tools.py` 中的 `get_stock_info`、`get_stock_kline`、`calculate_technical_indicators` 等全部直接查询 `ods_daily`，不支持 `.HK` 代码。

**用户场景**：用户在智能对话中输入"分析腾讯 00700.HK 的技术指标和财务情况"，期望得到综合分析，但当前系统无法提供完整的港股技术+财务分析。

## What Changes

### 1. 扩展 MarketAgent 支持港股技术分析

- 修改 `market_agent.py` 的系统提示词，加入港股代码格式和分析能力说明
- MarketAgent 的工具函数 (`get_kline`, `calculate_indicators`, `analyze_trend`) **已通过 MarketService 支持港股**，无需修改工具代码

### 2. 扩展 tools.py 工具函数支持港股

- `get_stock_info`：检测 `.HK` 后缀，查询 `ods_hk_daily` + `ods_hk_basic`
- `get_stock_kline`：检测 `.HK` 后缀，查询 `ods_hk_daily`
- `calculate_technical_indicators`：检测 `.HK` 后缀，查询 `ods_hk_daily`
- `get_stock_valuation`：检测 `.HK` 后缀时返回提示（港股估值数据结构不同）

### 3. 增强 Orchestrator 的港股联合分析能力

- `_build_multi_agent_plan`：当检测到港股代码时，自动组合 `MarketAgent` + `HKReportAgent` 进行并发分析
- `_build_agent_query`：为港股的 HKReportAgent 生成合适的查询

### 受影响的代码
- `src/stock_datasource/agents/market_agent.py` - 更新系统提示词，加入港股代码格式和分析能力
- `src/stock_datasource/agents/tools.py` - 扩展工具函数支持港股代码
- `src/stock_datasource/agents/orchestrator.py` - 增强港股场景的多 Agent 编排逻辑

### 不受影响的代码
- `src/stock_datasource/modules/market/service.py` - 已支持港股，无需修改
- `src/stock_datasource/modules/market/indicators.py` - 纯计算逻辑，与数据源无关
- `src/stock_datasource/agents/hk_report_agent.py` - 已完整实现港股财报分析
- `src/stock_datasource/agents/chat_agent.py` - 不需要直接处理港股分析

## Risks

1. **数据覆盖**：`ods_hk_daily` 仅有最近一年数据，长周期技术指标（如 MA250）可能数据不足
2. **港股估值数据缺失**：`ods_hk_daily` 无 PE/PB 等估值数据（A 股有 `ods_daily_basic`），但 HKReportAgent 的财务分析可补充此信息
3. **并发编排复杂度**：增加港股多 Agent 并发可能影响响应时间，需监控

## Out of Scope

- 港股实时行情接入
- 港股估值数据表（ods_hk_daily_basic）的新建和数据采集
- 前端界面修改（智能对话界面本身不需要修改，数据通过流式响应返回）
