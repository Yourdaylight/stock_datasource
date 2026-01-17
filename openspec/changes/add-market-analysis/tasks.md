# Tasks: M02行情分析模块实现任务

## 数据访问原则

**重要**：所有数据获取应优先调用 `plugins/` 目录下的 Service 接口，避免直接写 SQL 查询。

可用的 Plugin Services：
- `TuShareDailyService` - A股日线行情
- `TuShareIndexDailyService` - 指数日线数据
- `TuShareAdjFactorService` - 复权因子
- `TuShareStockBasicService` - 股票基础信息

## 1. 后端技术指标服务

- [x] 1.1 创建 `src/stock_datasource/modules/market/indicators.py` 技术指标计算模块
  - calculate_ma() 移动平均线
  - calculate_ema() 指数移动平均
  - calculate_macd() MACD指标
  - calculate_rsi() RSI指标
  - calculate_kdj() KDJ指标（重构现有实现）
  - calculate_boll() 布林带
  - calculate_atr() 平均真实波幅
  - calculate_obv() 能量潮
  - calculate_dmi() 趋向指标
  - calculate_cci() 顺势指标
  - detect_signals() 信号检测
  - calculate_support_resistance() 支撑压力位
  - determine_trend() 趋势判断
- [x] 1.2 增强 `schemas.py` 添加技术指标相关数据模型
  - IndicatorType 枚举
  - IndicatorParams 参数模型
  - IndicatorData/IndicatorDataV2 结果模型
  - MarketOverviewResponse 市场概览模型
  - TrendAnalysisResponse AI分析响应模型
  - TechnicalSignal 技术信号模型
- [x] 1.3 增强 `service.py` 使用 Plugin Services 获取数据
  - 注入 TuShareDailyService, TuShareAdjFactorService
  - 重构 get_kline() 使用 plugin service
  - 重构 get_indicators() 调用 indicators.py
  - 新增 get_market_overview() 市场概览
  - 新增 analyze_trend() 趋势分析

## 2. 后端API增强

- [x] 2.1 增强 `router.py` 技术指标端点
  - POST /indicators 支持全部指标类型（兼容旧格式）
  - POST /indicators/v2 新格式带信号检测
- [x] 2.2 新增市场概览API
  - GET /overview 市场概览（涨跌统计、成交额等）
  - GET /hot-sectors 热门板块
- [x] 2.3 新增AI分析API
  - POST /analysis 技术分析
  - GET /analysis/stream SSE流式分析
  - POST /analysis/ai MarketAgent分析
  - POST /pattern 形态识别（占位）

## 3. MarketAgent 开发

- [x] 3.1 创建 `src/stock_datasource/agents/market_agent.py`
  - 继承 LangGraphAgent 基类
  - 定义行情分析系统提示词
  - 注册工具函数
- [x] 3.2 实现 Agent Tools
  - get_kline() K线数据工具
  - calculate_indicators() 指标计算工具
  - analyze_trend() 走势分析工具
  - get_market_overview() 市场概览工具
- [x] 3.3 集成 Langfuse 追踪
  - 通过LangGraphAgent基类自动集成

## 4. 前端K线图表增强

- [x] 4.1 增强 `KLineChart.vue` 使用ECharts K线专业组件
  - 支持蜡烛图 + 成交量
  - 支持叠加MA线、布林带
  - 支持副图显示MACD/RSI/KDJ
  - 支持缩放、十字光标
  - 支持多图联动
- [x] 4.2 创建 `IndicatorPanel.vue` 指标控制面板
  - 指标选择（多选、分组）
  - 预设配置（简洁/标准/专业）
  - 指标说明
- [x] 4.3 优化图表交互
  - 鼠标悬停显示详情
  - 区间选择缩放

## 5. 前端新增组件

- [x] 5.1 创建 `MarketOverview.vue` 市场概览组件
  - 上证指数、深证成指、创业板指等
  - 涨跌家数统计
  - 成交额统计
- [ ] 5.2 创建 `IndexChart.vue` 指数走势图 (TODO: 可选)
  - 支持多指数对比
  - 分时/日K切换
- [x] 5.3 创建 `TrendAnalysis.vue` AI分析展示组件
  - 趋势判断
  - 支撑压力位
  - 技术信号展示
  - 分析摘要
- [ ] 5.4 创建 `HotSectors.vue` 热门板块组件 (TODO: 可选)
  - 板块涨幅榜
  - 板块资金流向

## 6. 前端状态管理与API

- [x] 6.1 增强 `market.ts` store
  - 添加指标数据状态（V2格式）
  - 添加市场概览状态
  - 添加AI分析状态
  - 添加技术信号状态
- [x] 6.2 增强 `market.ts` API
  - 完善指标请求（V2接口）
  - 添加市场概览请求
  - 添加AI分析请求（普通/流式）
- [x] 6.3 增强 `types/common.ts`
  - 添加市场相关类型定义

## 7. 整合与测试

- [x] 7.1 增强 `MarketView.vue` 整合新组件
  - 添加市场概览区域
  - 添加指标面板（可折叠）
  - 添加AI分析Tab页
  - 优化响应式布局
  - 股票价格信息展示
- [ ] 7.2 编写后端单元测试 (TODO: 可选)
  - 指标计算测试
  - API端点测试
- [ ] 7.3 端到端测试 (TODO: 可选)
  - K线加载流程
  - 指标切换流程
  - AI分析流程

## Dependencies

- Task 1.x 是其他任务的基础，需优先完成 ✅
- Task 2.x 依赖 Task 1.x ✅
- Task 3.x 依赖 Task 1.x 和 Task 2.x ✅
- Task 4.x 可与 Task 1-3 并行（使用Mock数据）✅
- Task 5.x 依赖 Task 2.x（需要API）✅
- Task 6.x 依赖 Task 2.x ✅
- Task 7.x 需要所有功能完成后进行 ✅

## Parallelizable Work

- Task 1.x 和 Task 4.x 可并行（前后端分离开发）✅ 已完成
- Task 5.1-5.4 各组件可并行开发 ✅ 核心组件已完成
- Task 2.x 和 Task 3.x 可串行但紧密衔接 ✅ 已完成
