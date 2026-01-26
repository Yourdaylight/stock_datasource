# Change: 添加系统日志查看功能

## Why

当前系统存在以下痛点：
1. 日志分散在多个文件中（backend.log, worker.log, server.log 等），没有统一的管理界面
2. 出现错误时，管理员需要登录服务器查看日志文件，操作复杂
3. 日志内容量大，手动分析效率低
4. 已有 AI 能力但未应用到日志分析场景

需要为管理员提供集中的日志查看界面，并利用 AI 进行智能分析。

## What Changes

### 1. 后端日志查询 API
新增日志查询和管理功能：
- 读取并解析 `logs/` 目录下的日志文件（backend.log, worker.log, application.log）
- 支持按级别过滤（INFO, WARNING, ERROR）
- 支持按时间范围过滤
- 支持按关键词搜索
- 支持分页查询（避免一次加载大量日志）
- 管理员权限校验（使用现有的 `is_admin` 字段）

### 2. 前端日志展示界面
新增系统日志页面：
- 表格形式展示日志（时间、级别、模块、消息）
- 颜色区分日志级别（INFO-蓝色，WARNING-黄色，ERROR-红色）
- 支持过滤（级别、时间范围、关键词）
- 支持手动刷新
- 支持导出日志为文件

### 3. AI 日志分析功能
集成 AI 分析能力：
- 用户选择错误日志或时间范围
- 发送到 AI Agent 分析错误原因
- 返回可能的原因和修复方案
- 显示分析历史

### 4. 日志归档机制
日志管理优化：
- 自动压缩超过 7 天的旧日志
- 按日期归档（例如 `logs/archive/2026-01/`）
- 限制日志文件大小（单文件最大 50MB，自动滚动）

## Impact

- Affected specs: `system-logs-viewer` (new)
- Affected code:
  - `src/stock_datasource/modules/system_logs/` (新增模块：router, service, schemas)
  - `src/stock_datasource/modules/system_logs/` (新增日志解析器：log_parser.py)
  - `src/stock_datasource/agents/` (扩展：log_analyzer_agent.py 或复用现有 agent)
  - `frontend/src/views/SystemLogs.vue` (新增日志页面)
  - `frontend/src/api/systemLogs.ts` (新增日志 API)
  - `frontend/src/components/LogTable.vue` (新增日志表格组件)
  - `frontend/src/components/LogFilters.vue` (新增过滤组件)
  - `frontend/src/components/LogAnalysis.vue` (新增 AI 分析组件)
  - `src/stock_datasource/services/http_server.py` (注册新路由)
  - `cli.py` (新增日志归档命令：`python cli.py logs archive`）
- File system:
  - `logs/archive/` (归档目录)
  - `logs/.index` (日志索引文件，加速查询)
- Database: 无需修改（日志从文件系统读取，不存 DB）

## Trade-offs

### 方案 A：日志存储在文件系统（推荐）
**优点**：
- 实现简单，无需修改数据库 schema
- 日志可直接查看，无需通过 API
- 存储成本低

**缺点**：
- 查询性能不如数据库索引
- 分布式部署时日志分散

### 方案 B：日志存储在数据库
**优点**：
- 查询性能高，支持复杂过滤
- 分布式部署集中管理

**缺点**：
- 需要修改数据库 schema，增加存储成本
- 日志量大时可能影响主业务性能
- 实现复杂度高（需要异步写入）

**决策**：采用方案 A（文件系统），理由：
1. 当前已有日志文件系统，改动最小
2. 管理员场景下查询频率不高
3. 后续可按需迁移到数据库（如使用 ELK 方案）

## Open Questions

1. 日志保留策略是否需要可配置？（默认 30 天）
2. AI 分析是否需要支持多条错误批量分析？（初始支持单条/单时段）
3. 是否需要支持日志下载？（是，导出功能）

## Dependencies

- 依赖 `add-user-scoped-features` 中的 `is_admin` 权限
- 依赖现有的日志文件结构
- 依赖 AI Agent 能力（复用 `base_agent`）
