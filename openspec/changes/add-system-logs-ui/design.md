# 系统日志查看功能 - 设计文档

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3)                      │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ SystemLogs.vue (主页面)                           │       │
│  │  ├── LogTable.vue (日志表格)                    │       │
│  │  ├── LogFilters.vue (过滤条件)                    │       │
│  │  └── LogAnalysis.vue (AI 分析)                   │       │
│  └──────────────────────────────────────────────┐       │
└───────────────────────────────────┬──────────────────┘       │
                                │ HTTP API (admin auth)       │
                                ▼                           │
┌───────────────────────────────────────────────────────┐       │
│             Backend (FastAPI)                        │       │
│  ┌─────────────────────────────────────────────┐  │       │
│  │ system_logs/router.py                  │  │       │
│  │  GET /api/system_logs (list)           │  │       │
│  │  POST /api/system_logs/analyze (AI)       │  │       │
│  └─────────────────────────────────────────┘  │       │
│  ┌─────────────────────────────────────────────┐  │       │
│  │ system_logs/service.py                │  │       │
│  │  LogFileReader (解析日志文件)            │  │       │
│  │  LogIndexer (构建内存索引)              │  │       │
│  └─────────────────────────────────────────┘  │       │
└─────────────────────────────┬──────────────────┘       │
                            │                           │
                            ▼                           │
┌───────────────────────────────────────────────┐       │
│         File System                        │       │
│  ┌─────────────────────────────────────┐    │       │
│  │ logs/                          │    │       │
│  │   ├── backend.log                │    │       │
│  │   ├── worker.log                 │    │       │
│  │   ├── application.log             │    │       │
│  │   ├── archive/ (旧日志归档)      │    │       │
│  │   └── .index (日志索引)        │    │       │
│  └─────────────────────────────────────┘    │       │
└───────────────────────────────────────┘       │
                                            │
                                            │ (if AI analysis)
                                            ▼
┌───────────────────────────────────────────────┐
│          AI Agent (复用)                  │
│  ┌─────────────────────────────────────┐    │
│  │ log_analyzer_agent.py            │    │
│  │  - 解析错误日志                │    │       │
│  │  - 查询相关代码                │    │       │
│  │  - 生成修复方案                │    │       │
│  └─────────────────────────────────────┘    │       │
└───────────────────────────────────────┘       │
```

## 核心组件设计

### 1. LogFileReader (文件读取器)

**职责**：高效读取和解析日志文件

```python
class LogFileReader:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.cache = {}  # 文件内容缓存

    def read_logs(
        self,
        log_file: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[LogEntry]:
        """读取日志并过滤"""

    def get_log_files(self) -> List[LogFileInfo]:
        """获取所有日志文件及元数据（大小、修改时间）"""
```

**日志格式解析**：
- 支持标准 Python logging 格式（带颜色代码）
- 支持结构化日志（JSON）
- 自动检测时间戳格式

### 2. LogIndexer (索引构建器)

**职责**：构建内存索引加速查询

```python
class LogIndexer:
    def __init__(self):
        self.index = {}  # {level: [indices], keyword: [indices]}

    def build_index(self, logs: List[LogEntry]):
        """构建多级索引"""

    def search(
        self,
        level: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[int]:
        """返回匹配的日志索引"""
```

**索引策略**：
- **级别索引**：按 INFO/WARNING/ERROR 分组
- **时间索引**：按日期分组，支持快速跳转
- **关键词倒排索引**：支持快速全文搜索

### 3. LogArchiver (日志归档器)

**职责**：自动归档旧日志

```python
class LogArchiver:
    def __init__(self, retention_days: int = 30):
        self.retention_days = retention_days
        self.archive_dir = Path("logs/archive")

    def archive_old_logs(self):
        """归档超过保留期的日志"""

    def compress_logs(self, logs: List[Path]):
        """压缩日志文件（gzip）"""
```

**归档策略**：
- 每天凌晨 2 点自动运行（cli.py 定时任务）
- 归档文件命名：`YYYY-MM-DD_backend.log.gz`
- 保留原索引文件到归档目录

### 4. LogAnalyzerAgent (AI 分析)

**职责**：基于错误日志提供智能分析

**输入**：
- 错误日志条目（ERROR 级别）
- 相关上下文（前后 10 行）
- 可选的用户描述

**输出**：
```
{
  "error_type": "DatabaseConnectionError",
  "possible_causes": [
    "ClickHouse 服务未启动",
    "网络连接中断",
    "连接池耗尽"
  ],
  "suggested_fixes": [
    "检查 ClickHouse 容器状态",
    "验证网络配置",
    "增加连接池大小"
  ],
  "confidence": 0.85,
  "related_logs": [
    "2026-01-26 10:00:04 ERROR ... Connection refused",
    "2026-01-26 10:00:05 ERROR ... Timeout"
  ]
}
```

**分析流程**：
1. 提取错误消息的关键词
2. 在代码库中搜索相关错误处理逻辑
3. 查询文档获取常见解决方案
4. 综合生成建议

## 数据流设计

### 查询流程

```
用户选择过滤条件
    │
    ▼
前端发送请求
    │ { level: "ERROR", start: "...", end: "...", keyword: "timeout" }
    │
    ▼
后端 LogFileReader.read_logs()
    │ (按时间、级别、关键词过滤)
    │
    ▼
返回分页日志
    │ { logs: [...], total: 1234, page: 1, page_size: 50 }
    │
    ▼
前端渲染表格
```

### AI 分析流程

```
用户点击"AI 分析"
    │ (选中 ERROR 日志或时间范围)
    ▼
前端发送请求
    │ { log_entries: [...], user_query: "为什么一直超时？" }
    │
    ▼
后端调用 AI Agent
    │ 读取日志 → 搜索代码 → 查询文档
    │
    ▼
AI 返回分析结果
    │ { error_type, causes, fixes, confidence }
    │
    ▼
前端展示结果
    │ + 展开相关代码片段
    │ + 提供修复按钮（打开相关文件）
```

## 性能优化

### 1. 懒加载
- 默认只加载最新 50 条日志
- 用户滚动到底部时才加载更多
- 过滤结果缓存 5 分钟

### 2. 索引优化
- 优先使用内存索引（O(1) 查询）
- 关键词索引限制 10000 个条目（内存限制）
- 大文件才使用 mmap

## 安全设计

### 1. 权限控制
```python
# router.py
from .auth.dependencies import require_admin

@router.get("/api/system_logs", dependencies=[Depends(require_admin)])
async def list_logs(...):
    """仅管理员可访问"""
    pass
```

### 2. 敏感信息脱敏
自动隐藏：
- 密码：`"password": "*****"`
- Token：`"token": "sk-****"`
- 个人信息：`"email": "***@***.com"`

### 3. 操作审计
记录所有日志访问：
- 管理员 ID
- 查询条件
- 访问时间

## 扩展性设计

### 未来可扩展功能
1. **日志导出**：支持 CSV、JSON 格式
2. **日志告警**：规则引擎（如"连续 10 个 ERROR 则通知"）
3. **分布式日志**：接入 ELK/Loki
4. **日志可视化**：生成错误趋势图
5. **多租户**：按客户隔离日志

## 技术选型

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| 日志解析 | Python logging.handlers.RotatingFileHandler | 标准库，支持滚动 |
| AI 分析 | 现有 base_agent + RAG | 复用，无需重构 |
| 前端表格 | Element Plus Table | 项目已使用，样式统一 |
