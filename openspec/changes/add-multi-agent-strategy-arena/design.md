## Context

构建多Agent对抗策略竞技场系统，模拟真实投研团队的协作模式。多个AI Agent各自生成交易策略，通过辩论、协作、评审等讨论机制相互质疑和完善，最终产出经过多角度验证的量化策略。策略进入回测→模拟盘→实盘的递进式竞争流程，按日/周/月周期淘汰表现差的策略，保持N个Agent持续竞争。

关键约束：
- Agent数量可配置，支持异质化（不同LLM模型/策略思路）
- 思考讨论过程全程可见，类似聊天界面实时输出
- 所有过程持久化存储，支持历史回溯
- 异步执行，用户可切换页面做其他事情
- 实盘功能预留扩展设计，暂不实现

## Goals / Non-Goals

### Goals
- 构建可配置的多Agent竞技场，支持异质化Agent
- 实现辩论+协作+评审的组合讨论机制，模拟真实投研团队
- 整合实时行情、技术面、基本面、市场情绪等市场现状
- 建立回测→模拟盘的递进式竞争流程（实盘预留）
- 实现按日/周/月周期的综合评分淘汰机制
- 思考过程实时流式输出并持久化
- 全程异步执行，支持后台运行

### Non-Goals
- 实盘交易功能（仅预留接口设计）
- 高频交易策略支持（聚焦日线级别策略）
- 实时风控系统（预留设计）
- 策略代码自动部署到生产环境

## Decisions

### Decision 1: 多Agent架构设计

采用**角色分工+动态协作**的Agent架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    MultiAgentArena                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Generator   │  │ Generator   │  │ Generator   │  ...    │
│  │ Agent 1     │  │ Agent 2     │  │ Agent N     │         │
│  │ (GPT-4)     │  │ (Claude)    │  │ (Local)     │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           AgentDiscussionOrchestrator               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ Debate   │ │ Collab   │ │ Review   │            │   │
│  │  │ Mode     │ │ Mode     │ │ Mode     │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           StrategyCompetitionEngine                 │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ Backtest │→│ Simulated│→│ Live     │            │   │
│  │  │ Stage    │ │ Trading  │ │ (预留)    │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘            │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Rationale**: 
- 异质化Agent可从不同角度生成策略，避免单一视角偏差
- 讨论协调器支持多种模式组合，灵活应对不同场景
- 竞争引擎分层设计，便于后续扩展实盘功能

### Decision 2: 讨论机制设计

采用**三阶段讨论流程**：

```
Phase 1: 独立生成 (Individual Generation)
  └─ 每个Agent独立分析市场，生成初版策略

Phase 2: 交叉讨论 (Cross Discussion)
  ├─ 辩论轮: Agent互相质疑策略的风险点和逻辑漏洞
  ├─ 协作轮: Agent互相补充和优化策略参数
  └─ 评审轮: 专门的Reviewer Agent评分并给出改进建议

Phase 3: 共识形成 (Consensus Building)
  └─ 整合讨论结果，形成最终策略
```

**Rationale**: 模拟真实投研团队工作流程，确保策略经过充分论证

### Decision 3: 竞争评分体系

采用**多维度综合评分**：

| 维度 | 权重 | 指标 |
|------|------|------|
| 收益性 | 30% | 年化收益率、累计收益率 |
| 风险控制 | 30% | 最大回撤、夏普比率、Sortino比率 |
| 稳定性 | 20% | 收益波动率、胜率、盈亏比 |
| 适应性 | 20% | 不同市场环境下表现 |

评分周期：
- **日评**: 更新实时表现，不触发淘汰
- **周评**: 综合周表现，淘汰末位20%
- **月评**: 全面评估，淘汰末位10%

**Rationale**: 平衡收益与风险，避免单一维度导致的策略偏颇

### Decision 4: 思考流实时输出

采用**SSE + 持久化双写**模式：

```
Agent思考 → ThinkingStreamProcessor
             ├─→ SSE推送前端 (实时展示)
             └─→ ClickHouse写入 (持久化)
```

数据模型：
```python
@dataclass
class ThinkingMessage:
    arena_id: str
    agent_id: str
    round_id: str
    message_type: str  # 'thinking' | 'argument' | 'conclusion'
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
```

**Rationale**: 满足实时可见和历史回溯双重需求

### Decision 5: 异步执行架构

采用**Celery + Redis Streams**：

```
                     ┌─────────────┐
                     │   FastAPI   │
                     │   (SSE)     │
                     └──────┬──────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Redis    │  │ Redis    │  │ Celery   │
       │ Streams  │  │ Pub/Sub  │  │ Queue    │
       │(思考流)   │  │(状态通知) │  │(长任务)  │
       └──────────┘  └──────────┘  └──────────┘
              │             │             │
              └─────────────┴─────────────┘
                            ▼
                     ┌──────────┐
                     │  Worker  │
                     │  Pool    │
                     └──────────┘
```

**Rationale**: 
- Redis Streams保证思考消息顺序
- Celery处理长时间运行的回测任务
- 用户可随时断开重连，不影响后台执行

### Decision 6: 市场数据整合

整合四类市场数据：

```python
class MarketContextAnalyzer:
    """市场环境分析器"""
    
    async def get_context(self, symbols: List[str]) -> MarketContext:
        return MarketContext(
            realtime=await self._get_realtime_quotes(symbols),
            technical=await self._get_technical_analysis(symbols),
            fundamental=await self._get_fundamental_data(symbols),
            sentiment=await self._get_market_sentiment()
        )
```

数据来源：
- **实时行情**: 现有DataPlugin获取
- **技术面**: 计算MA、MACD、RSI等指标
- **基本面**: 复用财务数据插件
- **情绪指标**: 复用新闻分析Agent + 北向资金等

**Rationale**: 复用现有数据源，避免重复开发

### Decision 7: 实盘预留设计

预留接口，暂不实现：

```python
class TradingExecutor(ABC):
    """交易执行器抽象接口"""
    
    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """下单"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        pass

class SimulatedExecutor(TradingExecutor):
    """模拟交易执行器 (实现)"""
    pass

class LiveExecutor(TradingExecutor):
    """实盘交易执行器 (预留，暂不实现)"""
    pass
```

**Rationale**: 接口层面预留扩展能力，降低后续实盘接入成本

## Alternatives Considered

### Alternative 1: 单Agent多轮迭代 vs 多Agent并行
- **选择**: 多Agent并行
- **理由**: 多Agent能提供真正不同的视角，而非单Agent的自我强化

### Alternative 2: 固定讨论流程 vs 动态讨论流程
- **选择**: 动态讨论流程（三种模式组合）
- **理由**: 不同策略需要不同程度的论证，固定流程缺乏灵活性

### Alternative 3: 百分比淘汰 vs 绝对分数淘汰
- **选择**: 综合评分后的百分比淘汰（10个以下按固定数量）
- **理由**: 避免大量淘汰导致策略池枯竭

### Alternative 4: 同步执行 vs 异步执行
- **选择**: 异步执行
- **理由**: 多Agent讨论和回测是耗时操作，阻塞会严重影响用户体验

## Risks / Trade-offs

### Risk 1: 多Agent协调复杂度
- **风险**: Agent间消息同步和状态管理复杂
- **缓解**: 采用有限状态机管理竞技场生命周期，严格定义状态转换

### Risk 2: 计算资源消耗
- **风险**: N个Agent并行 + 回测任务消耗大量资源
- **缓解**: 引入任务队列限流，支持配置最大并发数

### Risk 3: 讨论收敛性
- **风险**: Agent讨论可能陷入循环或无法达成共识
- **缓解**: 设置最大讨论轮次，超时强制进入共识阶段

### Risk 4: 思考流存储压力
- **风险**: 大量思考消息可能导致存储膨胀
- **缓解**: 设计TTL策略，定期归档历史数据

### Risk 5: 策略过拟合
- **风险**: 竞争机制可能导致策略过度拟合历史数据
- **缓解**: 引入滚动窗口回测、样本外验证等防过拟合机制

## Migration Plan

### Phase 1: 基础设施 (Week 1-2)
1. 创建arena模块目录结构
2. 实现ThinkingStreamProcessor
3. 搭建Redis Streams和Celery
4. 实现基础状态机

### Phase 2: Agent层 (Week 3-4)
1. 实现StrategyGeneratorAgent
2. 实现ReviewerAgent和RiskAnalystAgent
3. 实现AgentDiscussionOrchestrator
4. 整合MarketContextAnalyzer

### Phase 3: 竞争引擎 (Week 5-6)
1. 实现StrategyCompetitionEngine
2. 实现综合评分系统
3. 实现周期淘汰机制
4. 整合现有回测引擎

### Phase 4: 前端界面 (Week 7-8)
1. 创建Arena管理页面
2. 实现思考流聊天界面
3. 实现排行榜和统计面板
4. 实现历史回溯功能

### Phase 5: 集成优化 (Week 9-10)
1. 端到端测试
2. 性能优化
3. 文档完善
4. 上线准备

## Confirmed Configuration

以下参数已确认：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| Agent数量范围 | 3-10个 | 推荐范围，资源有限时可配置更少 |
| 默认讨论轮次 | 3轮 | 可配置，每种模式各1轮 |
| 淘汰后补充策略 | 生成新Agent + 复活历史优秀Agent | 两种方式均支持，可配置 |
| 模拟盘初始资金 | 10万元 | 虚拟资金，可配置 |
| 模拟盘仓位限制 | 不限 | 无仓位上限限制 |
| 思考流历史保留 | 30天 | 超过30天自动归档 |

### Decision 8: 策略补充机制

淘汰后策略补充采用**混合模式**：

```
淘汰触发 → StrategyReplenisher
             ├─→ 70%: 生成新Agent策略 (保持创新性)
             └─→ 30%: 复活历史优秀Agent (保持稳定性)
```

复活机制：
- 从历史淘汰策略中选择表现最优的策略
- 策略需满足：历史综合评分 > 当前存活策略平均分
- 复活后从回测阶段重新验证

**Rationale**: 平衡策略创新和历史经验复用，避免完全随机导致的不稳定

## Open Questions

所有关键配置已确认，无待定问题。
