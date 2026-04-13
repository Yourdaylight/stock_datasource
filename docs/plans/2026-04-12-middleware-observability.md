# Middleware 可观测性改造 Implementation Plan（精简版）

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让中间件关键事件可观测——结构化日志 + middleware_trace_id 关联，消除"零日志"黑洞。

**原则:** 只记运维必须看但看不到的事件，渐进增强，不堆 Stats/Langfuse/Span。

---

## 现状缺口

| 缺口 | 影响 |
|------|------|
| 中间件 before/after 没有日志 | 执行过程对运维不可见，无法排查"为什么记忆没注入" |
| 无 middleware_trace_id | 无法将中间件事件与 HTTP request_id 关联 |
| 循环检测/幻觉警告无日志 | 关键风控事件无记录 |
| system_logs 不识别中间件事件类型 | 前端无法按中间件类型筛选 |

**不做的事（延后）：**
- ❌ FactExtractor / MemoryUpdateQueue 日志（无当前痛点）
- ❌ 统计指标 counter（无看板消费方）
- ❌ Langfuse Span 嵌套（日志管道已够用，等链路稳定后再加）

---

## Task 1: contextvars + logger + runtime 注入 middleware_trace_id

**Files:**
- Modify: `src/stock_datasource/utils/request_context.py`
- Modify: `src/stock_datasource/utils/logger.py`
- Modify: `src/stock_datasource/services/agent_runtime.py`

### Step 1: request_context.py 新增 middleware_trace_id

```python
import uuid

middleware_trace_id_var: ContextVar[str] = ContextVar("middleware_trace_id", default="-")

def get_middleware_trace_id() -> str:
    return middleware_trace_id_var.get("-")

def generate_middleware_trace_id() -> str:
    return uuid.uuid4().hex[:12]
```

更新 `patch_context`：
```python
record["extra"].setdefault("middleware_trace_id", get_middleware_trace_id())
```

更新 `set_request_context` / `reset_request_context`：加入 middleware_trace_id 的 set/reset。

### Step 2: logger.py 格式模板更新

- `_CONSOLE_FMT` / `_TEXT_FMT`：在 user_id 后加入 `{extra[middleware_trace_id]}`
- `_jsonl_sink`：entry dict 加入 `"middleware_trace_id": record["extra"].get("middleware_trace_id", "-")`

### Step 3: agent_runtime.py 设置 middleware_trace_id

在 `execute_stream_sse` 中间件执行前：
```python
from stock_datasource.utils.request_context import generate_middleware_trace_id, middleware_trace_id_var

mw_trace_id = generate_middleware_trace_id()
middleware_trace_id_var.set(mw_trace_id)
```

在 done 事件 metadata 中包含：
```python
"middleware_trace_id": mw_trace_id,
"middleware_trace": mw_context.middleware_trace if mw_context else [],
```

在 finally 中 reset：`middleware_trace_id_var.set("-")`

### Step 4: 验证

```bash
cd /data/openresource/stock_datasource && python3 -c "
from stock_datasource.utils.request_context import generate_middleware_trace_id, middleware_trace_id_var, get_middleware_trace_id
mid = generate_middleware_trace_id()
middleware_trace_id_var.set(mid)
assert get_middleware_trace_id() == mid
print('OK: middleware_trace_id works')
"
```

---

## Task 2: BaseMiddleware before/after 结构化日志

**Files:**
- Modify: `src/stock_datasource/agents/middlewares/base.py`
- Modify: `src/stock_datasource/services/agent_runtime.py`（调用入口替换）

### Step 1: BaseMiddleware 添加日志包装器

在 `BaseMiddleware` 中：

```python
from stock_datasource.utils.logger import get_logger

class BaseMiddleware(ABC):
    def __init__(self):
        self._log = get_logger(f"middleware.{self.__class__.__name__}")

    async def before_with_logging(self, context: AgentContext) -> AgentContext:
        """Wrapper: structured log around before()."""
        if not self.enabled:
            return context
        t0 = time.time()
        self._log.info("middleware.before.start", middleware=self.name, session_id=context.session_id)
        try:
            result = await self.before(context)
            ms = round((time.time() - t0) * 1000, 1)
            self._log.info("middleware.before.done", middleware=self.name, duration_ms=ms)
            return result
        except Exception as e:
            self._log.error("middleware.before.failed", middleware=self.name, error=str(e))
            raise

    async def after_with_logging(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Wrapper: structured log around after()."""
        if not self.enabled:
            return response
        t0 = time.time()
        self._log.info("middleware.after.start", middleware=self.name, session_id=context.session_id)
        try:
            result = await self.after(context, response)
            ms = round((time.time() - t0) * 1000, 1)
            self._log.info("middleware.after.done", middleware=self.name, duration_ms=ms)
            return result
        except Exception as e:
            self._log.error("middleware.after.failed", middleware=self.name, error=str(e))
            raise
```

### Step 2: agent_runtime.py 替换调用

在 `execute_stream_sse` 中：
- `mw.before(context)` → `mw.before_with_logging(context)`
- `mw.after(context, response)` → `mw.after_with_logging(context, response)`

### Step 3: 验证

启动服务，发一条请求，检查日志中出现 `middleware.before.start` / `middleware.before.done` / `middleware.after.start` / `middleware.after.done` 且携带 `middleware_trace_id`。

---

## Task 3: 关键风控中间件增加 WARNING 事件

**Files:**
- Modify: `src/stock_datasource/agents/middlewares/loop_detection.py`
- Modify: `src/stock_datasource/agents/middlewares/guardrail.py`

**原则：** 只在触发风控动作时记 WARNING，正常运行不记额外日志（before_with_logging 已覆盖）。

### Step 1: LoopDetectionMiddleware — 循环检测触发

在检测到循环时（before 方法中）：
```python
self._log.warning(
    "middleware.loop_detected",
    tool=loop_tool_name,
    count=loop_count,
    session_id=context.session_id,
)
```

### Step 2: GuardrailMiddleware — 幻觉警告触发

在检测到幻觉时（after 方法中）：
```python
self._log.warning(
    "middleware.hallucination_warning",
    reason=warning_reason[:200],
    session_id=context.session_id,
)
```

在非金融查询拦截时：
```python
self._log.info(
    "middleware.non_financial_query",
    query_preview=context.query[:80],
    session_id=context.session_id,
)
```

### Step 3: 验证

构造循环调用场景，确认日志中出现 `middleware.loop_detected` WARNING。

---

## Task 4: system_logs 适配 middleware_trace_id

**Files:**
- Modify: `src/stock_datasource/modules/system_logs/log_parser.py`
- Modify: `src/stock_datasource/modules/system_logs/schemas.py`
- Modify: `src/stock_datasource/modules/system_logs/service.py`

### Step 1: LogParser 识别 middleware_trace_id 字段

更新日志解析正则，从 6 组扩展为 7 组（时间|级别|module|request_id|user_id|middleware_trace_id|message）。

更新 `_extract_fields` 方法，提取 `middleware_trace_id` 字段。

### Step 2: schemas.py 新增字段

```python
class LogEntry(BaseModel):
    ...
    middleware_trace_id: Optional[str] = Field("-", description="Middleware trace ID")

class LogFilter(BaseModel):
    ...
    middleware_trace_id: Optional[str] = Field(None, max_length=32, description="Filter by middleware trace ID")
```

### Step 3: service.py 查询支持

在 ClickHouse 查询中：
- SELECT 加入 `middleware_trace_id`
- WHERE 支持 `middleware_trace_id` 过滤
- 时间线识别：`middleware.loop_detected` / `middleware.hallucination_warning` 等作为 `event_type='middleware'`

### Step 4: ClickHouse 迁移文件

已创建增量迁移文件 `docker/migrations/002_add_middleware_trace_id.sql`，应用启动时由 `db_migrations.py` 自动执行：

```sql
ALTER TABLE system_structured_logs ADD COLUMN IF NOT EXISTS middleware_trace_id String DEFAULT '-'
```

同时更新了 `docker/migrations/001_create_system_structured_logs.sql` 建表语句，新部署时直接包含该字段。

### Step 5: 验证

通过 system_logs API 查询，确认能按 middleware_trace_id 过滤，时间线中显示 middleware 事件。

---

## 依赖关系

```
Task 1 (contextvars + logger + runtime) ← 必须先完成
        ↓
Task 2 (BaseMiddleware 日志包装) ← 依赖 Task 1 的 trace_id
        ↓
Task 3 (关键风控 WARNING) ← 依赖 Task 2 的 self._log
        ↓
Task 4 (system_logs 适配) ← 依赖 Task 1 的日志格式
```

串行执行，每个 Task 完成后验证再进下一个。

## 延后事项（有需求时再做）

- FactExtractor / MemoryUpdateQueue 提取事件日志
- AgentRuntime 统计指标 counter
- Langfuse Middleware Span 嵌套
- 记忆注入详情日志（facts_count / block_size 等）
