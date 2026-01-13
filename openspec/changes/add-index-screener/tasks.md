# Tasks: 指数选股界面

## 1. Index Agent开发

- [x] 1.1 创建`index_tools.py` - 实现指数分析工具函数（基于schema.json中的实际指标）
  - [x] `get_index_info(ts_code)` - 获取指数基础信息（dim_index_basic）
  - [x] `get_index_constituents(ts_code, trade_date)` - 获取成分股及权重（ods_index_weight）
  - [x] `get_index_factors(ts_code, days)` - 获取最近N日技术因子（ods_idx_factor_pro）
  - [x] `analyze_trend(ts_code)` - 趋势分析（均线MA5/10/20/60/250 + MACD + DMI）
  - [x] `analyze_momentum(ts_code)` - 动量分析（KDJ + RSI6/12/24 + MTM + ROC）
  - [x] `analyze_volatility(ts_code)` - 波动分析（ATR + BOLL + 唐安奇/肯特纳通道）
  - [x] `analyze_volume(ts_code)` - 量能分析（OBV + VR + MFI）
  - [x] `analyze_sentiment(ts_code)` - 情绪分析（PSY + BRAR + CCI + WR）
  - [x] `analyze_concentration(ts_code)` - 集中度分析（CR10 + HHI）
  - [x] `get_comprehensive_analysis(ts_code)` - 综合分析报告（多空评分0-100）
- [x] 1.2 创建`index_agent.py` - 实现IndexAgent类
  - [x] 继承`LangGraphAgent`基类
  - [x] 配置AgentConfig（name、description）
  - [x] 实现`get_tools()`方法，绑定上述工具函数
  - [x] 实现`get_system_prompt()`方法，包含完整分析框架
- [x] 1.3 在`agents/__init__.py`中注册`get_index_agent()`

## 2. 后端模块开发

- [x] 2.1 创建Index模块目录结构 (`src/stock_datasource/modules/index/`)
- [x] 2.2 实现schemas.py - 定义请求/响应模型
- [x] 2.3 实现service.py - 封装业务逻辑，调用插件service
- [x] 2.4 实现router.py - FastAPI路由定义
- [x] 2.5 在modules/__init__.py中注册Index模块
- [x] 2.6 实现AI量化分析接口（调用Index Agent）

## 3. 前端页面开发

- [x] 3.1 创建Index API接口 (`frontend/src/api/index.ts`)
- [x] 3.2 创建Index状态管理 (`frontend/src/stores/index.ts`)
- [x] 3.3 创建指数选股主页面 (`frontend/src/views/index/IndexScreenerView.vue`)
- [x] 3.4 创建指数详情弹窗 (`frontend/src/views/index/components/IndexDetailDialog.vue`)
- [x] 3.5 创建AI分析面板 (`frontend/src/views/index/components/IndexAnalysisPanel.vue`)
- [x] 3.6 添加Index路由到router/index.ts

## 4. 集成测试

- [x] 4.1 验证Index Agent工具函数正常工作
- [x] 4.2 验证Index Agent综合分析功能
- [x] 4.3 验证指数列表API正常返回
- [x] 4.4 验证成分股权重API正常返回
- [x] 4.5 验证技术因子API正常返回
- [x] 4.6 验证AI分析接口正常工作
- [x] 4.7 验证前端页面交互流程

## Dependencies

- Task 1.x（Index Agent）需要先完成，Task 2.6 依赖它
- Task 2.x（后端模块）可以与Task 1.x并行开发部分内容
- Task 3.x（前端）可以与后端并行开发（使用mock数据）
- Task 3.6 依赖 Task 3.3 完成
- Task 4.x 依赖 Task 1.x、Task 2.x、Task 3.x 全部完成
