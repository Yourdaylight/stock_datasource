# Change: 多Agent对抗策略竞技场 (Multi-Agent Strategy Arena)

## Why

当前的智能策略系统采用单Agent策略生成模式，缺乏多角度验证和持续竞争优化机制。参考真实投研团队的协作模式，需要构建一个多Agent对抗竞争系统：

1. **策略视角单一**: 单个Agent生成的策略缺乏不同视角的验证和质疑
2. **缺乏竞争机制**: 没有策略优胜劣汰的进化机制，无法持续筛选优质策略
3. **思考过程黑盒**: 策略生成过程不透明，用户无法理解决策逻辑
4. **市场适应性弱**: 策略无法根据市场现状动态调整和演进
5. **验证周期缺失**: 缺乏从回测→模拟盘→实盘的递进式验证体系

## What Changes

### 核心架构

- **MultiAgentArena**: 多Agent竞技场管理器，协调N个Agent的策略生成和竞争
- **AgentDiscussionOrchestrator**: Agent讨论协调器，支持辩论、协作、评审多种模式
- **StrategyCompetitionEngine**: 策略竞争引擎，管理回测→模拟盘→实盘的进阶流程
- **ThinkingStreamProcessor**: 思考流处理器，实时输出并持久化Agent思考过程
- **MarketContextAnalyzer**: 市场环境分析器，为Agent提供实时市场现状

### Agent对抗系统

- **StrategyGeneratorAgent**: 策略生成Agent（可配置数量，支持异质化模型）
- **StrategyReviewerAgent**: 策略评审Agent，质疑和验证策略逻辑
- **RiskAnalystAgent**: 风险分析Agent，评估策略风险敞口
- **MarketSentimentAgent**: 市场情绪Agent，结合新闻和情绪指标
- **QuantResearcherAgent**: 量化研究Agent，基于学术研究优化策略

### 讨论机制（符合真实投研团队）

- **辩论模式**: Agent互相质疑和挑战策略逻辑，挖掘潜在风险
- **协作模式**: Agent互相补充和优化策略，综合多方观点
- **评审模式**: 部分Agent生成策略，其他Agent评审打分
- **轮换主导**: Agent轮流主导讨论，确保多元视角

### 竞争淘汰机制

- **回测阶段**: 初始N个Agent策略进入回测验证
- **模拟盘阶段**: 通过回测的策略进入模拟盘实测
- **实盘阶段**: 预留扩展设计，模拟盘优胜者可升级实盘
- **周期淘汰**: 按日/周/月维度评估，综合评分筛选
- **持续竞争**: 淘汰后补充新策略，保持N个Agent持续竞争

### 市场现状结合

- **实时行情数据**: 获取最新股票价格、成交量等
- **技术面分析**: 均线、趋势、形态等技术指标
- **基本面数据**: 财报、估值、行业对比等
- **市场情绪指标**: 资金流向、涨跌比、VIX等

### 思考过程可视化

- **实时流式输出**: 类似聊天的步骤展示
- **结构化思考日志**: 每个Agent的推理链条
- **讨论历史回溯**: 完整记录Agent间的交互
- **持久化存储**: 所有思考过程入库保存

### API接口设计

```
POST   /api/arena/create                     # 创建竞技场
GET    /api/arena/{id}/status                # 获取竞技场状态
POST   /api/arena/{id}/start                 # 启动竞争
GET    /api/arena/{id}/thinking-stream       # SSE 思考流（异步）
POST   /api/arena/{id}/discussion            # 触发讨论轮次
GET    /api/arena/{id}/strategies            # 获取当前策略列表
GET    /api/arena/{id}/leaderboard           # 获取排行榜
POST   /api/arena/{id}/evaluate              # 触发周期评估
GET    /api/arena/{id}/history               # 获取讨论历史
```

### 异步执行设计

- **后台任务队列**: 策略生成、回测、讨论异步执行
- **SSE实时推送**: 思考过程实时流式输出
- **断点续传**: 支持中断后恢复
- **并发控制**: 支持用户切换页面后继续后台执行

## Impact

### 新增能力规范

- **multi-agent-arena**: 多Agent竞技场核心能力
- **strategy-competition**: 策略竞争和淘汰机制
- **agent-discussion**: Agent讨论和协作机制

### 影响的现有规范

- **intelligent-strategy-system**: 扩展为多Agent策略生成
- **chat-orchestration**: 复用编排机制支持多Agent协调

### 影响的代码模块

- `src/stock_datasource/agents/`: 新增Arena相关Agent
- `src/stock_datasource/arena/`: 新增竞技场核心模块
- `src/stock_datasource/services/`: 新增竞争服务
- `frontend/src/views/`: 新增竞技场管理页面
- `frontend/src/components/`: 新增思考流展示组件

### 技术依赖

- **异步任务框架**: Celery / asyncio / APScheduler
- **消息队列**: Redis Streams / RabbitMQ
- **SSE支持**: 服务端推送实时思考流
- **LLM集成**: 支持多模型异质化Agent

### 风险评估

- **高复杂度**: 多Agent协调和竞争机制复杂
- **计算资源**: 并行回测和AI推理需要大量资源
- **状态管理**: 需要精确管理竞技场状态机
- **数据一致性**: 多Agent并发时的数据同步

## 与现有智能策略系统的关系

本提案是 `add-intelligent-strategy-system` 的**增强扩展**，主要差异：

| 特性 | 现有系统 | 多Agent竞技场 |
|------|----------|--------------|
| Agent数量 | 单个 | 可配置N个 |
| 策略生成 | 直接生成 | 讨论后生成 |
| 竞争机制 | 无 | 回测→模拟→实盘 |
| 思考可见 | 部分 | 全程可见+持久化 |
| 异步执行 | 否 | 是 |
| 市场结合 | 有限 | 全面 |
