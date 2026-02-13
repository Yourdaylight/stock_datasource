# Tasks: add-hk-smart-analysis

## Task 1: 扩展 MarketAgent 支持港股 [agents/market_agent.py]

**目标**: 修改 MarketAgent 的系统提示词，使其能正确处理港股代码并给出港股技术分析。

- [x] 更新 `MARKET_ANALYSIS_SYSTEM_PROMPT`，加入港股代码格式（00700.HK 等）
- [x] 加入港股常用代码参考（腾讯、阿里、美团等）
- [x] 说明港股与 A 股的差异（涨跌幅无限制、T+0 交易等）
- [x] 加入港股技术分析框架说明
- [x] 更新 `_normalize_stock_code` 支持 HK 代码格式
- [x] 更新 AgentConfig description 包含港股

**验证**: ✅ 在智能对话中输入"分析 00700.HK 的技术指标"，MarketAgent 正确调用 calculate_indicators / get_kline，返回包含 MACD/RSI/KDJ 的完整港股技术分析。

## Task 2: 扩展 tools.py 工具函数支持港股 [agents/tools.py]

**目标**: 让 DeepAgent/ChatAgent 使用的工具函数能处理港股代码。

- [x] `get_stock_info`: 检测 `.HK` 后缀，查询 `ods_hk_daily` + `ods_hk_basic`
- [x] `get_stock_kline`: 检测 `.HK` 后缀，查询 `ods_hk_daily`
- [x] `calculate_technical_indicators`: 检测 `.HK` 后缀，查询 `ods_hk_daily`
- [x] `get_stock_valuation`: 检测 `.HK` 后缀时，调用 HKFinancialReportService 获取财务指标
- [x] 添加辅助函数 `_is_hk_stock(ts_code)` 统一判断
- [x] 添加 HK 辅助函数: `_get_hk_stock_info`, `_get_hk_stock_kline`, `_calculate_hk_technical_indicators`, `_get_hk_stock_valuation`

**验证**: ✅ 工具函数正确路由港股代码到 ods_hk_daily 表查询。

## Task 3: 增强 Orchestrator 港股多 Agent 编排 [agents/orchestrator.py]

**目标**: 当用户查询涉及港股时，自动组合 MarketAgent + HKReportAgent 进行综合分析。

- [x] `_build_multi_agent_plan`: 检测港股代码时组合 `MarketAgent` + `HKReportAgent`
- [x] 确保 `CONCURRENT_AGENT_GROUPS` 中已包含 `{"MarketAgent", "HKReportAgent"}`（已有）
- [x] `_build_agent_query`: 为港股的 MarketAgent 和 HKReportAgent 生成合适的查询
- [x] 更新意图分类中的港股相关提示（LLM提示词加入港股路由规则）
- [x] 增强: 当 primary 是 HKReportAgent 但用户同时要求技术分析时，自动组合 MarketAgent
- [x] 增强: `_build_multi_agent_plan` 接受 query 参数，通过关键词检测自动组合 Agent

**依赖**: Task 1（MarketAgent 需先支持港股）

**验证**: ✅ 输入"全面分析腾讯 00700.HK 的技术面和财务情况"，OrchestratorAgent 自动组合 MarketAgent + HKReportAgent 并发执行 (`"sub_agents": ["MarketAgent", "HKReportAgent"]`)，返回技术分析 + 财报分析的综合结果。

## Task 4: 端到端验证

**目标**: 确保整个链路正确工作。

- [x] 测试场景 1: "分析 00700.HK 的技术指标" → MarketAgent 调用 calculate_indicators/get_kline，返回 MACD(-11.66)/RSI(21.84)/KDJ 等完整技术分析
- [x] 测试场景 2: "00700.HK 财报分析" → HKReportAgent 调用 get_hk_comprehensive_financial_analysis + get_hk_full_financial_statements，仅财报不触发 MarketAgent
- [x] 测试场景 3: "全面分析腾讯 00700.HK 的技术面和财务情况" → MarketAgent + HKReportAgent 并发，返回技术分析+财报综合结果
- [x] 测试场景 4: "分析 600519.SH 的技术指标和财务情况" → MarketAgent + ReportAgent（A股），不触发 HKReportAgent
- [x] 确认 A 股原有功能不受影响

**测试脚本**: `scripts/test_hk_smart_analysis.sh` — 可复用的 curl 测试脚本，包含 5 个测试场景和可直接复制的 curl 命令。
