## 1. WeKnora Python Client
- [x] 1.1 新建 `services/weknora_client.py`，实现 `WeKnoraClient` 类：`is_healthy()`, `knowledge_search()`, `list_knowledge_bases()`
- [x] 1.2 新增环境变量 `WEKNORA_ENABLED`, `WEKNORA_BASE_URL`, `WEKNORA_API_KEY`, `WEKNORA_KB_IDS`, `WEKNORA_TIMEOUT`，在 `.env.example` 中添加说明
- [x] 1.3 创建 `get_weknora_client()` 单例工厂函数，`WEKNORA_ENABLED=false` 时返回 `None`

## 2. KnowledgeAgent
- [x] 2.1 新建 `agents/knowledge_agent.py`，继承 `LangGraphAgent`，包含 `search_knowledge` 和 `list_knowledge_bases` 工具
- [x] 2.2 编写 KnowledgeAgent 系统提示（要求引用来源、检索为空时明确告知）
- [x] 2.3 KnowledgeAgent 仅在 `get_weknora_client()` 返回非 None 时实例化

## 3. Orchestrator 集成
- [x] 3.1 Orchestrator `_discover_agents` 自动发现 KnowledgeAgent（无需代码改动，验证即可）
- [x] 3.2 在 `CONCURRENT_AGENT_GROUPS` 中新增 `{KnowledgeAgent, MarketAgent}` 和 `{KnowledgeAgent, ReportAgent}` 并发分组
- [x] 3.3 更新 `_classify_with_llm` 的 Agent 描述，使 LLM 知道知识库 Agent 的使用场景

## 4. Docker Compose 可选部署
- [x] 4.1 新建 `docker-compose.weknora.yml`，配置 WeKnora 后端 + PostgreSQL(pgvector) + 文档解析服务
- [x] 4.2 后端 `docker-compose.yml` 中新增 WeKnora 相关的可选环境变量

## 5. 前端知识库配置与引导
- [x] 5.1 在数据配置页（`DataConfigView.vue`）新增"知识库"Tab
- [x] 5.2 实现知识库未配置引导面板（`KnowledgeGuidePanel.vue`）：功能说明 + 快速部署步骤（可复制命令）+ 官方文档链接 + 测试连接按钮
- [x] 5.3 实现知识库已配置管理面板（`KnowledgeConfigPanel.vue`）：连接状态、知识库列表、默认启用选择
- [x] 5.4 后端新增 `/api/v1/settings/knowledge/status` 端点：返回配置状态（not_configured/healthy/unreachable）、快速部署信息
- [x] 5.5 后端新增 `/api/v1/settings/knowledge/test` 端点：手动测试 WeKnora 连接
- [x] 5.6 后端新增 `/api/v1/settings/knowledge/bases` 端点：代理 WeKnora 的知识库列表
- [x] 5.7 聊天页 MessageList welcome-state 新增知识库功能卡片：已启用时正常展示，未启用时灰色样式 + "需部署知识库服务" 提示 + 点击跳转配置页
