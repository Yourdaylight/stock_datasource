## 1. 后端基础设施

- [x] 1.1 创建工作流数据模型 `src/stock_datasource/models/workflow.py`
- [x] 1.2 创建工作流服务 `src/stock_datasource/services/workflow_service.py`
- [x] 1.3 创建工作流执行Agent `src/stock_datasource/agents/workflow_agent.py`
- [x] 1.4 创建工作流生成Agent `src/stock_datasource/agents/workflow_generator_agent.py`

## 2. 后端API

- [x] 2.1 创建工作流路由 `src/stock_datasource/api/workflow_routes.py`
- [x] 2.2 集成路由到HTTP Server
- [x] 2.3 实现工具列表API（查询MCP可用工具）
- [x] 2.4 实现AI生成工作流API（流式返回生成结果）

## 3. 前端基础设施

- [x] 3.1 创建工作流API模块 `frontend/src/api/workflow.ts`
- [x] 3.2 创建工作流Store `frontend/src/stores/workflow.ts`
- [x] 3.3 配置路由 `frontend/src/router/index.ts`

## 4. 前端界面

- [x] 4.1 创建工作流列表页 `frontend/src/views/workflow/WorkflowList.vue`
- [x] 4.2 创建工作流编辑器 `frontend/src/views/workflow/WorkflowEditor.vue`
- [x] 4.3 创建工具选择面板组件（集成在编辑器中）
- [x] 4.4 创建提示词编辑器组件（集成在编辑器中）
- [x] 4.5 创建变量配置组件（集成在编辑器中）
- [x] 4.6 创建工作流执行对话框（集成在列表和编辑器中）
- [x] 4.7 创建AI生成工作流对话框组件（集成在列表页中）

## 5. 预置模板

- [x] 5.1 创建"单股分析"模板
- [x] 5.2 创建"股票对比"模板
- [x] 5.3 创建"板块扫描"模板
- [x] 5.4 创建"价值投资筛选"模板
- [x] 5.5 创建"技术面分析"模板
