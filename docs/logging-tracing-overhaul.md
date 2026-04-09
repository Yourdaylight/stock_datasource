# 日志模块 & 请求追踪模块修复方案

> 基于代码审查发现的 10 个缺陷，制定统一修复方案。
> 核心约束：结构化日志存 ClickHouse，日志文件达到 **100MB** 后批量写入。

---

## 一、整体架构

```
HTTP Request
     │
     ▼
[RequestID Middleware]  ─── 生成 X-Request-ID，注入 contextvars
     │
     ▼
[Loguru 统一日志体系]  ─── 所有日志自动携带 request_id / user_id
     │
     ├── stdout（控制台，带颜色）
     ├── stock_datasource.log（文本，rotation=100MB）
     ├── stock_datasource.jsonl（结构化 JSONL，rotation=100MB）
     └── errors.log（仅 ERROR）

[100MB 阈值触发器]
     │  当 .jsonl 文件被 rotation 切割后
     ▼
[ClickHouse 批量导入]  ─── 解析已切割的 .jsonl 文件，INSERT 到 system_structured_logs 表
     │
     ▼
[归档/删除已导入文件]
```

---

## 二、缺陷清单与优先级

| 优先级 | 缺陷编号 | 描述 | 严重程度 |
|--------|---------|------|---------|
| **P0** | #1 | 完全缺失 Request ID / Correlation ID | 严重 |
| **P0** | #2 | 日志格式不含请求上下文（request_id / user_id） | 严重 |
| **P1** | #3 | 双轨日志体系不一致（loguru vs logging.getLogger 混用） | 严重 |
| **P1** | #4 | Langfuse trace 与 HTTP 请求脱节 | 中等 |
| **P1** | #5 | task_worker 进程脱离 Loguru 体系 | 中等 |
| **P2** | #6 | 日志查询全量扫描（每次分页 = 全量解析两次） | 中等 |
| **P2** | #7 | flush_langfuse 未在 shutdown 中调用 | 轻微 |
| **P2** | #8 | 缺少结构化日志 / 结构化追踪 | 中等 |
| **P3** | #9 | setup_logging 在 import 时自动执行 | 轻微 |
| **P3** | #10 | metrics 模块只覆盖 realtime_kline | 轻微 |

---

## 三、具体修改清单

### 模块 1：Request ID 中间件 + contextvars 上下文 【修复 #1, #2】

**新建** `src/stock_datasource/utils/request_context.py`

```python
"""Request-scoped context variables for log correlation."""

import uuid
from contextvars import ContextVar

# 请求级别上下文
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")


def generate_request_id() -> str:
    """Generate a short unique request ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]
```

**修改** `src/stock_datasource/services/http_server.py` 的 `log_requests` middleware：

```python
@app.middleware("http")
async def log_requests(request, call_next):
    from datetime import datetime
    from stock_datasource.utils.logger import logger as loguru_logger
    from stock_datasource.utils.request_context import (
        request_id_var, user_id_var, generate_request_id
    )

    # 1. 生成或读取 Request ID
    req_id = request.headers.get("X-Request-ID") or generate_request_id()
    token_rid = request_id_var.set(req_id)

    # 2. 尝试从 JWT / session 中提取 user_id
    uid = "-"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            import jwt
            payload = jwt.decode(auth_header[7:], options={"verify_signature": False})
            uid = str(payload.get("user_id") or payload.get("sub") or "-")
        except Exception:
            pass
    token_uid = user_id_var.set(uid)

    start_time = datetime.now()

    # 3. 使用 loguru contextualize 让本次请求所有日志自动带上 request_id
    with loguru_logger.contextualize(request_id=req_id, user_id=uid):
        response = await call_next(request)

    process_time = (datetime.now() - start_time).total_seconds()

    # 4. 回写响应头
    response.headers["X-Request-ID"] = req_id

    loguru_logger.bind(request_id=req_id, user_id=uid).info(
        f'{request.client.host}:{request.client.port} - '
        f'"{request.method} {request.url.path}" '
        f'{response.status_code} - {process_time:.3f}s'
    )

    # 5. 恢复 context
    request_id_var.reset(token_rid)
    user_id_var.reset(token_uid)

    return response
```

---

### 模块 2：统一 Loguru 日志体系 【修复 #2, #3, #8, #9】

**修改** `src/stock_datasource/utils/logger.py`

#### 2.1 日志格式升级

```python
# 文本日志格式（含 request_id 和 user_id）
TEXT_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | "
    "{extra[request_id]} | {extra[user_id]} | "
    "{name}:{function}:{line} - {message}"
)

# 控制台格式（带颜色）
CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
```

#### 2.2 新增 JSONL 结构化 sink

```python
from stock_datasource.utils.log_sink_clickhouse import on_rotation

def setup_logging():
    loguru_logger.remove()
    
    # 配置 extra 默认值
    loguru_logger.configure(extra={"request_id": "-", "user_id": "-"})

    # 1. 控制台输出
    loguru_logger.add(
        sys.stdout,
        format=CONSOLE_FORMAT,
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # 2. 文本日志文件（rotation=100MB）
    loguru_logger.add(
        settings.LOGS_DIR / "stock_datasource.log",
        format=TEXT_FORMAT,
        level=settings.LOG_LEVEL,
        rotation=getattr(settings, "LOG_ROTATION_SIZE", "100 MB"),
        retention="30 days",
        compression="zip",
    )

    # 3. 结构化 JSONL（rotation=100MB，rotation 后触发 ClickHouse 导入）
    loguru_logger.add(
        settings.LOGS_DIR / "stock_datasource.jsonl",
        serialize=True,                    # 自动输出 JSON
        rotation=getattr(settings, "LOG_ROTATION_SIZE", "100 MB"),
        retention="7 days",
        compression=None,                  # 不压缩，方便解析导入
        rotation_callback=on_rotation,     # rotation 后回调
    )

    # 4. 错误日志
    loguru_logger.add(
        settings.LOGS_DIR / "errors.log",
        format=TEXT_FORMAT,
        level="ERROR",
        rotation=getattr(settings, "LOG_ROTATION_SIZE", "100 MB"),
        retention="30 days",
        compression="zip",
    )

    # 拦截标准库 logging → loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("urllib3", "requests", "clickhouse_driver", "uvicorn"):
        logging.getLogger(name).setLevel(logging.WARNING)

    return loguru_logger
```

#### 2.3 启动时补扫未导入文件

在 `setup_logging()` 末尾调用：

```python
from stock_datasource.utils.log_sink_clickhouse import import_pending_files
import_pending_files(settings.LOGS_DIR)
```

---

### 模块 3：ClickHouse 结构化日志表 + 批量导入 【修复 #6, #8 核心】

**新建** `src/stock_datasource/utils/log_sink_clickhouse.py`

#### 3.1 ClickHouse 建表 DDL

```sql
CREATE TABLE IF NOT EXISTS system_structured_logs (
    timestamp   DateTime64(3),
    level       LowCardinality(String),
    request_id  String         DEFAULT '-',
    user_id     String         DEFAULT '-',
    module      String         DEFAULT 'unknown',
    function    String         DEFAULT '',
    line        UInt32         DEFAULT 0,
    message     String,
    exception   String         DEFAULT '',
    extra       String         DEFAULT '{}'
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (timestamp, level, module)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192
```

#### 3.2 批量导入逻辑

```python
"""JSONL → ClickHouse batch importer, triggered on log file rotation."""

import json
import logging
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Dict

_import_lock = threading.Lock()
_logger = logging.getLogger("log_sink_clickhouse")

CREATE_TABLE_SQL = """...(上述 DDL)..."""

BATCH_SIZE = 5000  # 每批次 INSERT 行数


def on_rotation(filepath: str, _):
    """Loguru rotation 回调 — 在后台线程中导入被切割的旧文件到 ClickHouse."""
    thread = threading.Thread(
        target=_import_file,
        args=(Path(filepath),),
        daemon=True,
    )
    thread.start()


def import_pending_files(logs_dir: Path):
    """启动时补扫：导入所有 .jsonl.N 历史文件."""
    for f in sorted(logs_dir.glob("stock_datasource.jsonl.*")):
        if f.suffix not in (".zip", ".gz"):
            thread = threading.Thread(target=_import_file, args=(f,), daemon=True)
            thread.start()


def _import_file(filepath: Path):
    """读取 JSONL 文件，批量 INSERT 到 ClickHouse，完成后删除."""
    if not filepath.exists():
        return
    
    with _import_lock:
        try:
            from stock_datasource.models.database import db_client
            
            # 确保表存在
            db_client.execute(CREATE_TABLE_SQL)
            
            batch: List[Dict] = []
            imported = 0
            
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        batch.append(_transform_record(record))
                    except json.JSONDecodeError:
                        continue
                    
                    if len(batch) >= BATCH_SIZE:
                        _flush_batch(db_client, batch)
                        imported += len(batch)
                        batch.clear()
            
            # 剩余不足一批的
            if batch:
                _flush_batch(db_client, batch)
                imported += len(batch)
            
            _logger.info(f"Imported {imported} log records from {filepath.name}")
            
            # 导入成功，删除源文件
            filepath.unlink(missing_ok=True)
            
        except Exception as e:
            _logger.warning(f"ClickHouse log import failed for {filepath.name}: {e}")
            # 不删除文件，下次启动会重试


def _transform_record(record: dict) -> dict:
    """将 loguru serialize 的 JSON 转换为 ClickHouse 行格式."""
    text = record.get("text", "")
    rec = record.get("record", {})
    
    ts_str = rec.get("time", {}).get("repr", "")
    try:
        ts = datetime.fromisoformat(ts_str[:26])  # 截断到微秒
    except Exception:
        ts = datetime.now()
    
    extra = rec.get("extra", {})
    exception = rec.get("exception", None)
    exc_str = ""
    if exception and isinstance(exception, dict):
        exc_str = exception.get("type", "") + ": " + exception.get("value", "")
    
    return {
        "timestamp": ts,
        "level": str(rec.get("level", {}).get("name", "INFO")),
        "request_id": str(extra.get("request_id", "-")),
        "user_id": str(extra.get("user_id", "-")),
        "module": str(rec.get("name", "unknown")),
        "function": str(rec.get("function", "")),
        "line": int(rec.get("line", 0)),
        "message": str(rec.get("message", "")),
        "exception": exc_str,
        "extra": json.dumps({k: str(v) for k, v in extra.items()
                            if k not in ("request_id", "user_id")}),
    }


def _flush_batch(db_client, batch: List[Dict]):
    """批量 INSERT 到 ClickHouse."""
    import pandas as pd
    df = pd.DataFrame(batch)
    db_client.insert_dataframe("system_structured_logs", df)
```

#### 3.3 100MB 阈值批量导入流程图

```
[Loguru 写日志] → stock_datasource.jsonl（持续追加）
                        │
                  达到 100MB
                        │
              [Loguru rotation]
                        │
           旧文件重命名为 .jsonl.1
                        │
         [on_rotation 回调触发]
                        │
     [后台线程] 读取 .jsonl.1
                        │
     逐行解析 → 每 5000 条批量 INSERT
                        │
          INSERT INTO system_structured_logs
                        │
               导入完成 → 删除 .jsonl.1
```

---

### 模块 4：task_worker 接入统一日志 【修复 #5】

**修改** `src/stock_datasource/services/task_worker.py`

**删除** 第 35-43 行的独立日志配置：

```python
# 删除这段 ↓
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | ...",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("task_worker")
```

**替换为**：

```python
from stock_datasource.utils.logger import logger  # noqa: E402
```

这样 worker 进程的日志将：
- 走 Loguru 统一格式
- 输出到同一组日志文件（含 JSONL）
- 自动参与 100MB rotation → ClickHouse 导入流程

---

### 模块 5：Langfuse trace 与 HTTP 请求关联 【修复 #4, #7】

#### 5.1 关联 request_id

**修改** `src/stock_datasource/agents/base_agent.py` 的 `get_langfuse_handler()`：

```python
def get_langfuse_handler(user_id=None, session_id=None, ...):
    # ...现有逻辑...
    
    # 新增：从 contextvars 获取 request_id，注入到 Langfuse metadata
    try:
        from stock_datasource.utils.request_context import request_id_var
        req_id = request_id_var.get("-")
        if handler and req_id != "-":
            # Langfuse 3.x：通过 metadata 传递
            handler.trace_name = trace_name or f"req-{req_id}"
    except Exception:
        pass
    
    return handler
```

#### 5.2 shutdown 时 flush Langfuse

**修改** `src/stock_datasource/services/http_server.py` 的 lifespan shutdown 部分（第 387-412 行之后追加）：

```python
# Flush Langfuse events before shutdown
try:
    from stock_datasource.llm.client import flush_langfuse
    flush_langfuse()
except Exception as e:
    logger.warning(f"Langfuse flush failed: {e}")
```

---

### 模块 6：system_logs 查询优先走 ClickHouse 【修复 #6】

**修改** `src/stock_datasource/modules/system_logs/service.py`

`get_logs()` 新增 ClickHouse 查询路径：

```python
def get_logs(self, filters: LogFilter) -> LogListResponse:
    """优先从 ClickHouse 查询，失败时回退到文件解析."""
    try:
        return self._get_logs_from_clickhouse(filters)
    except Exception as e:
        logger.warning(f"ClickHouse log query failed, fallback to file: {e}")
        return self._get_logs_from_files(filters)


def _get_logs_from_clickhouse(self, filters: LogFilter) -> LogListResponse:
    from stock_datasource.models.database import db_client
    
    conditions = ["1=1"]
    params = {}
    
    if filters.level:
        conditions.append("level = %(level)s")
        params["level"] = filters.level.upper()
    if filters.start_time:
        conditions.append("timestamp >= %(start_time)s")
        params["start_time"] = filters.start_time
    if filters.end_time:
        conditions.append("timestamp <= %(end_time)s")
        params["end_time"] = filters.end_time
    if filters.keyword:
        conditions.append("message LIKE %(keyword)s")
        params["keyword"] = f"%{filters.keyword}%"
    
    where = " AND ".join(conditions)
    offset = (filters.page - 1) * filters.page_size
    
    # 分页查询（一次 SQL 搞定，不需要全量扫描）
    count_sql = f"SELECT count() FROM system_structured_logs WHERE {where}"
    total = db_client.execute(count_sql, params)[0][0]
    
    data_sql = f"""
        SELECT timestamp, level, request_id, user_id, module, function, line, message
        FROM system_structured_logs
        WHERE {where}
        ORDER BY timestamp DESC
        LIMIT {filters.page_size} OFFSET {offset}
    """
    rows = db_client.execute(data_sql, params)
    
    log_entries = [
        LogEntry(
            timestamp=row[0], level=row[1], module=row[4],
            message=row[7], raw_line=f"[{row[2]}] {row[7]}"
        )
        for row in rows
    ]
    
    return LogListResponse(
        logs=log_entries, total=int(total),
        page=filters.page, page_size=filters.page_size
    )
```

**修改** `src/stock_datasource/modules/system_logs/schemas.py`

LogEntry 增加可选的 request_id 字段：

```python
class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    module: str
    message: str
    raw_line: str
    request_id: Optional[str] = Field(None, description="Request correlation ID")
    user_id: Optional[str] = Field(None, description="User ID from JWT")
```

---

### 模块 7：Settings 配置补充

**修改** `src/stock_datasource/config/settings.py`

```python
class Settings(BaseSettings):
    # ...existing fields...

    # Logging — 日志轮转与 ClickHouse 导入
    LOG_ROTATION_SIZE: str = Field(default="100 MB", description="日志文件轮转大小阈值")
    LOG_CH_SINK_ENABLED: bool = Field(default=True, description="是否启用 ClickHouse 日志导入")
    LOG_CH_SINK_BATCH_SIZE: int = Field(default=5000, description="ClickHouse 日志导入批次大小")
    LOG_RETENTION_DAYS: int = Field(default=90, description="ClickHouse 日志保留天数")
```

---

## 四、文件变更汇总

| 文件 | 操作 | 修复缺陷 |
|------|------|---------|
| `src/stock_datasource/utils/request_context.py` | **新建** | #1 |
| `src/stock_datasource/utils/log_sink_clickhouse.py` | **新建** | #6, #8 |
| `src/stock_datasource/utils/logger.py` | **修改** | #2, #3, #8, #9 |
| `src/stock_datasource/config/settings.py` | **修改** | 配置支撑 |
| `src/stock_datasource/services/http_server.py` | **修改** | #1, #2, #7 |
| `src/stock_datasource/services/task_worker.py` | **修改** | #5 |
| `src/stock_datasource/agents/base_agent.py` | **修改** | #4 |
| `src/stock_datasource/modules/system_logs/service.py` | **修改** | #6 |
| `src/stock_datasource/modules/system_logs/schemas.py` | **修改** | #8 |

---

## 五、实施顺序

| 步骤 | 模块 | 预估工作量 | 依赖 |
|------|------|-----------|------|
| 1 | Settings 配置补充（模块 7） | 小 | 无 |
| 2 | Request ID contextvars（模块 1） | 小 | 无 |
| 3 | 统一 Loguru 日志格式 + JSONL sink（模块 2） | 中 | 步骤 1 |
| 4 | ClickHouse 建表 + 批量导入器（模块 3） | 中 | 步骤 3 |
| 5 | Request ID middleware 接入（模块 1 HTTP 部分） | 小 | 步骤 2, 3 |
| 6 | task_worker 接入统一日志（模块 4） | 小 | 步骤 3 |
| 7 | Langfuse 关联 + shutdown flush（模块 5） | 小 | 步骤 2 |
| 8 | system_logs 查询走 ClickHouse（模块 6） | 中 | 步骤 4 |

---

## 六、注意事项

1. **向后兼容**：文本日志格式变更后，`log_parser.py` 的正则需要同步更新以匹配新格式（含 request_id 字段）
2. **ClickHouse 不可用时的降级**：所有 ClickHouse 写入/查询均需 try-except 保护，不影响主流程
3. **Worker 进程日志**：multiprocessing 的子进程需要重新初始化 loguru（fork 后 handler 会丢失），在 `run_worker()` 入口重调 `setup_logging()`
4. **JSONL 文件不压缩**：rotation 产生的 `.jsonl.N` 文件保持原始 JSON 格式，方便后台线程直接解析导入
5. **TTL 自动清理**：ClickHouse 表设置 90 天 TTL，过期数据自动删除，无需手动清理
6. **并发安全**：`_import_lock` 确保同一时间只有一个导入线程在工作，避免重复导入
