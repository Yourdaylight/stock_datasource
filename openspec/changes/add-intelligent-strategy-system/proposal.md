# Change: 智能策略系统

## Why

当前项目需要一个完整的智能策略系统，整合策略回测和AI生成能力。参考fin-agent项目的优秀实践，构建一个"策略创建→回测验证→智能优化"的完整闭环系统：

1. **策略管理缺失**: 缺乏统一的策略注册中心和策略基类
2. **回测引擎不完整**: 现有回测功能只是简单示例，缺乏真实的回测计算逻辑
3. **AI能力缺失**: 缺乏基于自然语言的智能策略生成和优化能力
4. **前端界面缺失**: 没有专业的策略管理和回测界面
5. **策略创新有限**: 缺乏基于AI的策略创新和发现机制

## What Changes

### 核心架构
- **StrategyRegistry**: 统一策略注册中心，管理内置策略和AI生成策略
- **IntelligentBacktestEngine**: 智能回测引擎，支持传统回测和AI优化回测
- **AIStrategyGenerator**: AI策略生成器，基于LLM和量化知识库
- **StrategyOptimizer**: 智能策略优化器，多目标优化和自适应调整

### 策略生态系统
- **BaseStrategy**: 统一策略基类，支持传统策略和AI策略
- **内置策略库**: 7个经典策略（MA、MACD、KDJ、RSI、Boll、DualMA、Turtle）
- **AI生成策略**: 基于自然语言描述生成的个性化策略
- **自适应策略**: 根据市场环境自动调整的智能策略

### 前端智能界面
- **StrategyWorkbench**: 策略工作台，统一的策略管理界面
- **AIStrategyWizard**: AI策略创建向导
- **IntelligentBacktestView**: 智能回测界面
- **StrategyOptimizationDashboard**: 策略优化控制台
- **PerformanceAnalytics**: 高级绩效分析面板

### API接口设计
- `GET /api/strategy/list`: 获取所有策略（内置+AI生成）
- `POST /api/strategy/ai-generate`: AI生成策略
- `POST /api/strategy/optimize`: 智能优化策略
- `POST /api/backtest/intelligent-run`: 执行智能回测
- `GET /api/strategy/insights/{id}`: 获取策略AI洞察

### 智能化功能
- **自然语言策略描述**: 用户用自然语言描述策略逻辑
- **智能参数优化**: 基于历史数据的多目标参数优化
- **市场环境适应**: 自动识别市场环境并调整策略
- **个性化推荐**: 基于用户风险偏好的策略推荐
- **策略解释**: AI解释策略逻辑和风险点

## Impact

### 新增能力规范
- **intelligent-strategy-system**: 智能策略系统核心能力
- **ai-strategy-generation**: AI策略生成能力
- **strategy-optimization**: 策略优化能力
- **natural-language-trading**: 自然语言交易能力
- **backtest-visualization**: 回测可视化能力

### 影响的现有规范
- **financial-report-analysis**: 扩展ReportAgent以支持策略分析

### 影响的代码模块
- `src/stock_datasource/agents/`: 重构BacktestAgent，新增AIStrategyAgent
- `src/stock_datasource/services/`: 新增智能策略服务
- `src/stock_datasource/ai/`: 新增AI模块目录
- `frontend/src/views/`: 新增策略管理相关页面
- `frontend/src/components/`: 新增智能策略相关组件

### 技术依赖
- **LLM集成**: 大语言模型API（GPT、Claude等）
- **优化算法**: scipy.optimize、optuna等优化库
- **机器学习**: scikit-learn、pandas等数据科学库
- **可视化**: echarts、d3.js等图表库

### 风险评估
- **高复杂度**: 整合AI和回测功能，技术复杂度较高
- **计算资源**: AI策略生成和优化需要大量计算资源
- **质量控制**: 需要严格的AI策略质量控制和风险管理
- **用户期望**: 需要合理设置用户对AI策略效果的期望