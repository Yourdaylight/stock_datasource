# Stock DataSource 记忆系统 + 中间链设计文档

> 版本: v1.0 | 日期: 2026-04-12 | 状态: 设计确认，待实现

---

## 一、背景与目标

### 1.1 问题

stock_datasource 当前的记忆系统存在以下不足：
- **无跨会话记忆**：用户关闭后重新访问，系统无法记住风险偏好、关注行业、历史分析结论
- **会话内重复调用**：不同 agent 重复拉取相同数据（如大盘指数），浪费 token 和时间
- **无事实提取**：用户明确表达的偏好（"我偏好低波动股"）无法自动捕获并注入后续对话
- **无交叉验证**：深度研究中多个 agent 结论可能矛盾，无机制检测和提醒
- **摘要机制粗糙**：现有 `_summarize` 按字符数截断，未考虑模型上下文窗口占比

### 1.2 目标

| 优先级 | 能力 | 描述 |
|--------|------|------|
| P0 | 跨会话持久化 | 用户画像、历史分析结论跨会话保留 |
| P0 | 自动事实提取 | 对话中 LLM 自动抽取关键事实，注入后续 system prompt |
| P0 | 会话内上下文增强 | 避免重复工具调用，后续分析引用前面结论 |
| P0 | 交叉验证 | 多 agent 结论互相校验，矛盾时标记提醒 |
| P1 | 智能摘要 | 基于上下文窗口占比触发摘要，保留关键金融数据 |
| P1 | 循环检测 | 检测 agent 重复调用同一工具 |
| P1 | 安全护栏 | 输入/输出安全检查，幻觉检测 |

### 1.3 方案选型

| 维度 | 方案 A: LangGraph Store | 方案 B: 独立 MemoryService |
|------|------------------------|---------------------------|
| 持久层 | LangGraph `BaseStore`（InMemoryStore → SqliteStore） | 自建 JSON 文件存储 |
| 事实提取 | 自建 FactExtractor | 同方案 A |
| 注入方式 | Store 机制 + 节点级别注入 | `_build_messages` 拼入 |
| 中间件 | 嵌入 `execute_stream` 前后 | 独立模块 |
| 与现有架构兼容性 | 深度融合 LangGraph | 零依赖 |
| **选择** | **✅ 选用** | - |

**选择方案 A 的理由**：
1. stock_datasource 已深度依赖 LangGraph（`create_react_agent`、`create_supervisor`、`MemorySaver`）
2. LangGraph Store 支持跨线程共享，天然适合多 agent 间共享记忆
3. `InMemoryStore` 开发调试，生产切 `SqliteStore` 零代码改动
4. 事实注入可在 supervisor 图节点级别完成，不需侵入每个 agent 的 `_build_messages`

---

## 二、整体架构

```
┌─────────────────────────────────────────────────┐
│                 AgentRuntime                     │
│  ┌───────────┐    ┌──────────────────────────┐  │
│  │ Supervisor │───▶│  Middleware Chain (新)    │  │
│  └───────────┘    │  ├─ LoopDetectionMW      │  │
│       │           │  ├─ SummarizationMW       │  │
│       ▼           │  ├─ GuardrailMW           │  │
│  ┌───────────┐    │  ├─ MemoryInjectionMW     │  │
│  │ Sub-Agents│    │  └─ CrossValidationMW     │  │
│  │ (15个)    │    └──────────────────────────┘  │
│  └───────────┘              │                    │
│       │                     ▼                    │
│       │           ┌──────────────────┐          │
│       │           │  Memory Layer    │          │
│       │           │  ├─ LangGraph    │          │
│       │           │  │  Store        │          │
│       │           │  ├─ FactExtractor│          │
│       │           │  └─ UpdateQueue  │          │
│       │           └──────────────────┘          │
│       │                     │                    │
│       ▼                     ▼                    │
│  ┌──────────────────────────────────────────┐   │
│  │  SessionMemoryService (现有,保留)         │   │
│  │  ├─ Hot State (会话级)                    │   │
│  │  └─ Cache (工具缓存)                      │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### 核心设计原则

- **分层**：`SessionMemoryService` 管「热数据」（会话历史+缓存），`LangGraph Store` 管「冷数据」（跨会话事实+用户画像）
- **异步**：事实提取和记忆更新通过 `MemoryUpdateQueue` 异步执行，不阻塞主流程
- **注入点**：`MemoryInjectionMiddleware` 在 supervisor 调度 sub-agent 前注入记忆到 context
- **最小侵入**：不改 `LangGraphAgent` 基类，在 `AgentRuntime` / `OrchestratorAgent` 入口处插入中间件链

---

## 三、Memory Layer 数据模型

### 3.1 LangGraph Store 命名空间设计

```
store 命名空间结构:
├── {user_id}/facts          ← 自动提取的事实
│   ├── item: fact_id_1      {content, category, confidence, created_at, source}
│   ├── item: fact_id_2      ...
│   └── ...
├── {user_id}/profile        ← 用户画像
│   ├── item: risk_preference   {value: "conservative", updated_at: ...}
│   ├── item: focus_sectors     {value: ["新能源","消费"], updated_at: ...}
│   └── item: expertise_level   {value: "intermediate", updated_at: ...}
├── {user_id}/conclusions    ← 历史分析结论
│   ├── item: conv_20260411_1   {query, summary, stocks, timestamp}
│   └── ...
└── {session_id}/shared      ← 会话内跨agent共享数据
    ├── item: MarketAgent_result   {tool_calls, key_findings}
    └── item: ReportAgent_result   {tool_calls, key_findings}
```

### 3.2 Fact 数据结构

```python
@dataclass
class FactItem:
    content: str          # "用户偏好低波动大盘股"
    category: str         # risk_preference | sector_focus | stock_opinion | trading_style | conclusion
    confidence: float     # 0.0 ~ 1.0，LLM 评估
    source: str           # 哪次对话/哪个agent提取的
    created_at: float     # time.time()
    reinforced_at: list   # 每次被reinforcement时追加时间戳
    contradicted_at: list # 每次被correction时追加时间戳
```

### 3.3 关键规则

- **置信度演化**：`confidence` 初始 0.7，每次 reinforced +0.1（上限 1.0），每次 contradicted -0.3
- **注入策略**：Top-K（K=15）by confidence 注入 system prompt，Token 预算为模型窗口的 5%~8%
- **衰减删除**：7 天内无 reinforcement 且 confidence < 0.5 的事实自动衰减删除

### 3.4 ContextSize 模型（参考 deer-flow）

```python
ContextSizeType = Literal["fraction", "tokens", "messages"]

@dataclass
class ContextSize:
    type: ContextSizeType
    value: int | float
    
    # fraction: 基于模型上下文窗口占比（推荐）
    # tokens:   绝对 token 数
    # messages: 消息条数（最弱维度）
```

---

## 四、FactExtractor + 三层信号检测

### 4.1 整体流程

```
用户消息 + Agent回复
        │
        ├──▶ Layer 1: Regex 快速信号（扩展金融场景关键词）
        │    修正信号: "不对","错了","不是这样","数据有误","应该是","我说的是"
        │    强化信号: "对","没错","就是这个","数据准确","分析到位"
        │
        ├──▶ Layer 2: LLM 意图分类（新增，轻量级）
        │    仅在 Regex 未匹配且消息包含疑问/否定词时触发
        │    单独一次 LLM 调用，只判断:
        │    {signal: "correction" | "reinforcement" | "neutral",
        │     target_fact: "关于XX的判断/偏好",
        │     correct_value: "正确的理解是..."}
        │    Token 消耗极小（输入~200 + 输出~50）
        │
        └──▶ Layer 3: FactExtractor 深度提取
             带 correction_hint 标记的完整事实提取
             correction 信号 → confidence ≥ 0.95
             reinforcement 信号 → 现有事实 +0.1
```

### 4.2 为什么用三层而不是纯 Regex

deer-flow 的修正/强化检测是双层机制（Regex 粗筛 + LLM 深度提取），但 Regex 在中文金融场景覆盖面有限：
- "这数据不对吧"、"应该是2024年的数据"、"我说的是市盈率不是市净率" → Regex 可能漏掉
- 三层设计中 Regex 做**快速路径**，LLM 意图分类做**兜底路径**

### 4.3 事实提取 Prompt（金融场景定制）

```
从以下对话中提取关于用户的事实。只提取与投资相关的事实：
- 风险偏好（保守/稳健/激进）
- 行业偏好（看好/看空哪些行业）
- 个股观点（关注/持有/回避哪些股票）
- 交易风格（短线/中线/长线）
- 分析结论（对某只股票的判断）

输出JSON数组: [{"content": "...", "category": "risk|sector|stock|style|conclusion", "confidence": 0.0-1.0}]
如果无可提取事实，返回空数组。
```

### 4.4 LLM 意图分类 Prompt

```
判断用户最新消息是否在修正或强化之前的分析结论。

信号类型:
- correction: 用户指出错误或不准确之处
- reinforcement: 用户确认分析正确
- neutral: 普通对话，无修正/强化意图

输出JSON: {"signal": "correction|reinforcement|neutral", "target_fact": "...", "correct_value": "..."}
```

### 4.5 MemoryUpdateQueue

- **30 秒 debounce**：同一 user_id 30 秒内只触发一次提取
- **后台 `asyncio.create_task`**：不阻塞主流程
- **写入失败自动重试 1 次**，然后跳过（记忆是增强不是关键路径）

---

## 五、Middleware Chain 设计

### 5.1 执行顺序与职责

```
请求进入 Supervisor
        │
        ▼
┌─────────────────────────────────────────────────┐
│  1. LoopDetectionMiddleware                      │
│  检测 agent 循环调用（同一工具连续3次+相同参数）   │
│  → 标记 loop_detected, 打断并注入提示              │
├─────────────────────────────────────────────────┤
│  2. SummarizationMiddleware                      │
│  基于模型上下文窗口占比触发摘要（参考 deer-flow）   │
│  触发条件（OR逻辑）:                               │
│  ├─ fraction: 0.7  (窗口占比70%)                  │
│  ├─ tokens: 6000   (兜底绝对token数)              │
│  └─ messages: 80   (安全兜底)                     │
│  保留策略: fraction 0.3 (保留窗口30%)              │
│  金融定制 summary_prompt 保留关键数字              │
├─────────────────────────────────────────────────┤
│  3. GuardrailMiddleware                          │
│  输入/输出安全检查                                 │
│  ├─ 输入：检测非金融问题 → 拒绝+引导               │
│  └─ 输出：检测幻觉信号（LLM轻量判断，非regex）     │
│     → 标记 warning，附加"请核实"提示               │
├─────────────────────────────────────────────────┤
│  4. MemoryInjectionMiddleware                    │
│  从 LangGraph Store 读取 Top-K facts + profile   │
│  注入 system prompt 的 <memory> 块                │
│  同时写入 session shared 命名空间供跨 agent 共享    │
├─────────────────────────────────────────────────┤
│  5. CrossValidationMiddleware                    │
│  深度研究完成后，对比各 sub-agent 结论              │
│  ├─ 一致 → 放行                                   │
│  ├─ 矛盾 → 注入警告到最终回复                      │
│  └─ 部分覆盖 → 标记可信度差异                      │
└─────────────────────────────────────────────────┘
        │
        ▼
  Sub-Agent 执行
        │
        ▼
  响应返回（经 Middleware 后处理）
```

### 5.2 中间件接口

```python
class BaseMiddleware(ABC):
    @abstractmethod
    async def before(self, context: AgentContext) -> AgentContext:
        """请求前处理，可修改 context"""
    
    @abstractmethod
    async def after(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """响应后处理，可修改 response"""
```

### 5.3 各中间件关键设计点

#### LoopDetectionMiddleware
- P0 中间件，stock_datasource 已有 agent 重复调用工具的问题
- 检测逻辑：同一工具连续 3 次 + 相同参数 → 标记 `loop_detected`

#### SummarizationMiddleware（参考 deer-flow）
- **触发条件用 fraction**（模型窗口占比），不硬编码消息条数
- **保留策略也用 fraction**，确保不同模型下保留比例一致
- **金融定制 summary_prompt**，强调保留关键数字（股价、PE、市值等）
- 使用轻量模型（haiku/mini）生成摘要

```yaml
# 推荐配置
trigger:
  - type: fraction
    value: 0.7
  - type: tokens
    value: 6000
keep:
  type: fraction
  value: 0.3
```

#### GuardrailMiddleware
- 幻觉检测用 LLM 轻量判断，非 regex
- 金融场景：检测无数据源支撑的断言

#### MemoryInjectionMiddleware
- Token 预算用 fraction（模型窗口的 5%-8%），不是固定数字，自适应不同模型
- 共享数据避免重复调用：MarketAgent 已拉过大盘数据，ReportAgent 不再重复拉
- 注入是追加而非替换：`<memory>` 块追加在 system_prompt 末尾

#### CrossValidationMiddleware
- **只在 DeepResearch 触发**（`is_deep_research=True`），普通问答零开销
- severity=high 的矛盾**不自动消解**，必须让用户确认
- LLM 比对用轻量模型（haiku/mini）

---

## 六、MemoryInjectionMiddleware 注入细节

### 6.1 注入流程

```
Supervisor 调度 sub-agent 前
        │
        ▼
1. 从 Store 读取记忆
   ├─ store.search(("{user_id}/facts"), limit=15, sort_by=confidence)
   ├─ store.search(("{user_id}/profile"))
   └─ store.search(("{session_id}/shared"))

2. Token 预算控制
   ├─ 总预算: 模型窗口 × 5% ~ 8%
   ├─ facts: 占 60% 预算
   ├─ profile: 占 20% 预算
   └─ shared: 占 20% 预算

3. 按优先级裁剪
   ├─ confidence > 0.8 的事实优先
   ├─ 最近 7 天的事实优先
   └─ 超出预算的低 confidence 事实丢弃

4. 注入到 context.system_prompt
   追加 <memory> 块
```

### 6.2 注入格式

```
<memory>
## 用户画像
- 风险偏好: 稳健型
- 关注行业: 新能源, 消费
- 交易风格: 中长线

## 已知事实（置信度 ≥ 0.7）
1. [0.95] 用户认为宁德时代估值偏高，等待回调
2. [0.85] 用户偏好市盈率 < 30 的股票
3. [0.80] 用户不看好传统燃油车行业
...

## 本次研究共享数据
- MarketAgent: 已获取大盘指数数据（沪深300微跌0.3%）
- TechAgent: 已完成MACD/RSI技术分析
</memory>
```

### 6.3 after() 钩子

```
Agent 执行完成后
        │
        ▼
1. 将当前 agent 的关键结果写入 shared 命名空间
   store.put(("{session_id}/shared"),
     key="{agent_name}_result",
     value={tool_calls, key_findings, tokens})

2. 触发 FactExtractor 异步任务
   MemoryUpdateQueue.enqueue(
     user_id, session_id, messages, signals)
```

---

## 七、CrossValidationMiddleware 交叉验证

### 7.1 触发条件

仅当 `is_deep_research=True` 且已有 ≥ 2 个 sub-agent 完成时触发。

### 7.2 比对流程

```
1. 收集已完成 agent 的结论
   从 Store 的 {session_id}/shared 读取所有结果

2. LLM 交叉比对（轻量调用，~300 token 输出）
   输入: 各 agent 结论的 JSON
   输出: {
     consistencies: ["均认为大盘短期震荡"],
     contradictions: [{
       agent_a: "MarketAgent",
       agent_b: "TechAgent",
       topic: "宁德时代走势判断",
       view_a: "短期看跌，支撑位210",
       view_b: "短期看涨，突破230概率大",
       severity: "high"
     }],
     partial_overlaps: [{
       topic: "消费板块",
       common: "整体估值合理",
       diff: "MarketAgent看好白酒,TechAgent提示风险"
     }]
   }

3. 根据比对结果处理
   ├─ 一致 → 无操作
   ├─ contradictions.length > 0
   │   → 注入警告到最终回复
   │   → 标记 severity=high 的矛盾需要用户确认
   └─ partial_overlaps
       → 在回复中附加可信度说明
```

### 7.3 矛盾检测 Prompt

```
你是一个金融分析交叉验证专家。对比以下不同分析Agent的结论，检测矛盾和一致之处。

重点关注：
- 对同一股票/行业的方向性判断是否矛盾（看涨 vs 看跌）
- 关键数据点是否冲突（如PE值、营收数据）
- 结论的逻辑前提是否一致

输出JSON:
{
  "consistencies": ["一致的结论"],
  "contradictions": [{"agent_a","agent_b","topic","view_a","view_b","severity":"high|medium|low"}],
  "partial_overlaps": [{"topic","common","diff"}]
}
```

### 7.4 用户端展示格式

```
📊 交叉验证结果：
✅ 一致：大盘短期震荡，沪深300估值合理
⚠️ 分歧：宁德时代走势判断
   - MarketAgent：短期看跌，支撑位210
   - TechAgent：短期看涨，突破230概率大
   → 建议：结合基本面进一步确认
💡 部分一致：消费板块整体估值合理，但白酒观点有分歧
```

---

## 八、代码集成方案

### 8.1 文件改动清单

```
stock_datasource/src/stock_datasource/
├── modules/memory/
│   ├── __init__.py              ← 更新导出
│   ├── router.py                ← 保留现有，新增 API
│   ├── store.py                 ← 【新建】LangGraph Store 封装
│   ├── fact_extractor.py        ← 【新建】FactExtractor + 三层信号检测
│   ├── memory_update_queue.py   ← 【新建】异步更新队列
│   └── models.py                ← 【新建】FactItem, ContextSize 等数据模型
│
├── agents/middlewares/
│   ├── __init__.py              ← 【新建】导出所有中间件
│   ├── base.py                  ← 【新建】BaseMiddleware 接口
│   ├── loop_detection.py        ← 【新建】LoopDetectionMiddleware
│   ├── summarization.py         ← 【新建】SummarizationMiddleware（fraction-based）
│   ├── guardrail.py             ← 【新建】GuardrailMiddleware
│   ├── memory_injection.py      ← 【新建】MemoryInjectionMiddleware
│   └── cross_validation.py      ← 【新建】CrossValidationMiddleware
│
├── services/
│   ├── session_memory_service.py ← 保留不动（热数据层）
│   └── agent_runtime.py          ← 【修改】集成 middleware chain + Store
│
└── agents/
    └── orchestrator.py           ← 【修改】集成 middleware chain
```

### 8.2 AgentRuntime 集成方式

```python
class AgentRuntime:
    def __init__(self, ...):
        ...
        # 新增：初始化 Store 和 Middleware Chain
        self._store = InMemoryStore()  # 开发用，生产切 SqliteStore
        self._middleware_chain = self._build_middleware_chain()
    
    def _build_middleware_chain(self) -> List[BaseMiddleware]:
        return [
            LoopDetectionMiddleware(),
            SummarizationMiddleware(
                trigger=[ContextSize(type="fraction", value=0.7),
                         ContextSize(type="tokens", value=6000)],
                keep=ContextSize(type="fraction", value=0.3),
            ),
            GuardrailMiddleware(),
            MemoryInjectionMiddleware(store=self._store),
            CrossValidationMiddleware(store=self._store),
        ]
    
    async def execute_stream_sse(self, query, context=None):
        context = context or {}
        # 新增：before 中间件
        for mw in self._middleware_chain:
            context = await mw.before(context)
        
        # ... 原有流式逻辑 ...
        
        # 新增：after 中间件
        for mw in reversed(self._middleware_chain):
            response = await mw.after(context, response)
```

### 8.3 Supervisor 编译注入 Store

```python
def _build_supervisor(self):
    ...
    self._supervisor = supervisor.compile(
        checkpointer=self._checkpointer,
        store=self._store,  # 新增：让图内节点也能访问 Store
    )
```

### 8.4 渐进式上线策略

```
Phase 1（第一周）: 核心记忆能力
├─ store.py + models.py + fact_extractor.py
├─ base.py + memory_injection.py（最核心的中间件）
├─ agent_runtime.py 集成
└─ 功能开关: MEMORY_STORE_ENABLED=true

Phase 2（第二周）: 摘要与安全
├─ summarization.py（fraction-based）
├─ loop_detection.py
├─ guardrail.py
└─ 功能开关: MIDDLEWARE_CHAIN_ENABLED=true

Phase 3（第三周）: 交叉验证与完整 API
├─ cross_validation.py
├─ memory_update_queue.py（异步事实提取）
└─ memory/router.py 新增 API（查看/删除事实）
```

### 8.5 依赖升级

```
# requirements.txt 需要升级
langgraph>=0.2.0     # 支持 BaseStore / InMemoryStore
langchain-core>=0.3  # 支持 token counting
```

---

## 九、参考项目对照

| 特性 | deer-flow | stock_datasource (本方案) |
|------|-----------|--------------------------|
| 持久化 | LangChain SummarizationMiddleware | LangGraph Store（InMemory → Sqlite） |
| 摘要触发 | fraction/tokens/messages（OR逻辑） | 同 deer-flow，推荐 fraction |
| 事实提取 | LLM + Regex 粗筛 | 三层信号检测（Regex + LLM意图 + 深度提取） |
| 记忆注入 | Middleware 注入 system prompt | MemoryInjectionMiddleware + `<memory>` 标签 |
| 交叉验证 | 无 | CrossValidationMiddleware（金融场景定制） |
| 循环检测 | 无 | LoopDetectionMiddleware |
| 安全护栏 | Sandbox 审计 | GuardrailMiddleware（幻觉检测） |

---

## 十、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LangGraph Store API 不稳定 | 升级后 breaking change | 封装 `store.py` 隔离 API，升级只改一层 |
| 事实提取 LLM 调用增加成本 | Token 消耗增加 | 使用轻量模型（haiku/mini），30s debounce |
| 中间件链增加延迟 | 请求响应变慢 | 异步执行，记忆写入非阻塞 |
| 幻觉检测误报 | 正确结论被标记 | severity 分级，high 才阻断 |
| 摘要丢失关键数字 | 分析准确性下降 | 金融定制 summary_prompt |
