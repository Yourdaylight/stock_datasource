# Change: 新增自定义AI编排界面

## Why

当前系统已集成MCP工具调用能力，拥有丰富的股票数据查询工具（日线、估值、财务指标、ETF等）。用户希望能够自定义AI分析流程，通过选择内置工具并编写提示词来创建个性化的股票分析工作流，而无需编写代码。这将大大提升平台的灵活性和用户自主分析能力。

同时，为了降低用户的使用门槛，系统还需要支持**AI辅助生成工作流**——用户只需用自然语言描述想要的分析策略或交易方式，AI即可自动生成对应的工作流配置。

## What Changes

1. **后端API**
   - 新增工作流管理API（CRUD操作）
   - 新增工作流执行API（支持流式输出）
   - 新增工具列表查询API（获取可用MCP工具）
   - **新增AI生成工作流API（根据用户描述生成工作流配置）**

2. **前端界面**
   - 新增"AI工作流"菜单入口
   - 工作流编辑器界面（工具选择、提示词编写、参数配置）
   - 工作流列表和管理界面
   - 工作流执行和结果展示界面
   - **新增AI生成工作流对话框（用户输入需求描述，AI生成工作流）**

3. **核心能力**
   - 工作流配置模型（存储用户自定义的工具组合和提示词）
   - 工作流执行引擎（基于现有Orchestrator和MCP集成）
   - **工作流生成器（基于LLM理解用户意图并生成工作流配置）**

## Impact

- Affected specs: 新增 `custom-ai-workflow` 能力
- Affected code:
  - `src/stock_datasource/api/` - 新增工作流路由
  - `src/stock_datasource/services/` - 新增工作流服务和工作流生成服务
  - `src/stock_datasource/agents/` - 新增工作流生成Agent
  - `frontend/src/views/` - 新增工作流视图
  - `frontend/src/api/` - 新增工作流API
  - `frontend/src/stores/` - 新增工作流状态管理
  - `frontend/src/router/` - 新增路由配置
  - `frontend/src/components/` - 新增AI生成工作流对话框组件
