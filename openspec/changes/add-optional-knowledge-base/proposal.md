# Change: Add Optional Knowledge Base Integration via WeKnora

## Why

当前智能对话系统完全依赖工具调用（K线数据、技术指标API等）和 LLM 自身知识进行分析。对于涉及公司基本面、行业研究报告、政策解读、交易规则说明等**文档密集型问题**，系统无法引用真实文档作为依据，回答质量受限于 LLM 训练截止日期和幻觉风险。

引入知识库（RAG）能力可以让用户上传研报、公告、规则文档等，Agent 在分析时检索相关片段并引用，大幅提升回答的准确性和可信度。

关键约束：**知识库 MUST 是完全可选的**。未配置 WeKnora 时，系统行为与当前完全一致；配置后自动启用 RAG 增强。

## What Changes

### 1. WeKnora Python HTTP Client

新建轻量级 Python HTTP Client（`src/stock_datasource/services/weknora_client.py`），封装 WeKnora REST API：
- `knowledge_search(query, kb_ids)` — 调用 `POST /knowledge-search`，返回检索结果
- `list_knowledge_bases()` — 列出可用知识库
- 健康检查（`GET /health` 或类似），用于启动时探测 WeKnora 是否可用
- 所有调用超时可配、失败不阻塞主流程

### 2. 环境变量配置（可选）

在 `.env` 中新增可选配置项：
```
WEKNORA_ENABLED=false           # 总开关，默认关闭
WEKNORA_BASE_URL=http://weknora-backend:8080/api/v1
WEKNORA_API_KEY=sk-xxx
WEKNORA_KB_IDS=kb-001,kb-002    # 默认检索的知识库ID列表（可选）
WEKNORA_TIMEOUT=10              # 请求超时秒数
```

### 3. KnowledgeAgent — 新增知识库检索 Agent

新增 `src/stock_datasource/agents/knowledge_agent.py`，继承 `LangGraphAgent`：
- 工具 `search_knowledge(query)`: 调用 WeKnora `knowledge_search` API 检索知识库
- 工具 `list_knowledge_bases()`: 列出可用知识库供用户参考
- 系统提示：根据检索结果生成带引用来源的回答
- 仅当 `WEKNORA_ENABLED=true` 且 WeKnora 健康时注册

### 4. Orchestrator 集成

修改 `orchestrator.py` 的 Agent 发现与调度逻辑：
- Agent 自动发现（`_discover_agents`）已能自动扫描新 Agent，无需修改发现逻辑
- 修改 `_classify_with_llm` 的意图分类提示词，使 LLM 知道知识库 Agent 可用（当 enabled 时）
- 对于混合查询（如"根据最新研报分析贵州茅台走势"），支持 KnowledgeAgent + MarketAgent 并发执行
- 新增并发分组：`{KnowledgeAgent, MarketAgent}` 和 `{KnowledgeAgent, ReportAgent}`

### 5. Docker Compose 扩展

在 `docker-compose.yml` 中以 `profile: weknora` 方式可选引入 WeKnora 服务，或允许外部部署独立连接：
- WeKnora 服务作为独立 compose 文件 `docker-compose.weknora.yml`
- 后端仅通过环境变量感知 WeKnora，无硬依赖

### 6. 前端知识库管理入口（轻量）

在数据配置页面（`/datamanage/config`）新增"知识库"Tab：
- 显示 WeKnora 连接状态（已连接/未配置/不可达）
- 列出可用知识库（来自 WeKnora API）
- 允许选择默认启用的知识库
- 知识库管理（上传、删除）仍在 WeKnora 原生 Web UI 完成，此处仅做选择

### 7. 未部署 WeKnora 时的引导界面

当 WeKnora 未配置（`WEKNORA_ENABLED=false` 或未设置）时，前端需在两处提供清晰引导：

**a) 数据配置页 - 知识库 Tab：**
- 展示"知识库未配置"空状态引导面板（使用 `<t-result>` 组件）
- 说明知识库功能介绍（RAG 增强分析、研报/公告检索等）
- 提供快速部署步骤卡片（一键 docker-compose 命令、.env 配置示例）
- 提供 WeKnora 官方文档链接和本地 `/data/openresource/WeKnora` 目录提示
- 配置后提供"测试连接"按钮验证可用性

**b) 聊天页 - 知识库功能提示：**
- 在 MessageList 的 welcome-state 功能卡片中，若知识库未启用，展示灰色卡片 + "需部署知识库服务" 提示
- 卡片点击跳转到 `/datamanage/config?tab=knowledge` 配置页

## Impact

- Affected specs: `knowledge-base-integration` (new)
- Modified specs: `chat-orchestration` (新增 KnowledgeAgent 路由规则)
- Affected code:
  - New: `services/weknora_client.py`, `agents/knowledge_agent.py`, `docker-compose.weknora.yml`
  - Modified: `agents/orchestrator.py` (并发分组、意图分类提示词)
  - Frontend: 数据配置页新增知识库 Tab（含未配置引导面板 + 快速部署指引）
  - Frontend: 聊天页 MessageList welcome-state 知识库功能卡片（未启用时灰色引导）
  - New: 后端 `/api/v1/settings/knowledge/status` 端点（返回配置状态 + 快速部署信息）
- Infrastructure: WeKnora 服务（PostgreSQL+pgvector, Go 后端, 文档解析器）为可选部署
