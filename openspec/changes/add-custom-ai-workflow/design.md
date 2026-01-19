# Design: 自定义AI工作流编排系统

## Context

当前系统架构：
- **MCP Server** (`services/mcp_server.py`): 动态发现并注册所有插件的工具，暴露HTTP接口
- **Orchestrator** (`agents/orchestrator.py`): 智能路由用户请求到对应Agent，支持MCP工具调用
- **插件系统** (`plugins/`): 丰富的数据插件（日线、估值、财务、ETF、指数等）
- **现有策略工作台** (`views/StrategyWorkbench.vue`): 策略管理和回测界面

用户需求：
1. 无需编码即可创建自定义分析流程，选择工具组合并编写提示词
2. **通过自然语言描述让AI自动生成工作流配置**

## Goals / Non-Goals

### Goals
- 用户可视化选择MCP工具创建工作流
- 支持自定义系统提示词和用户提示词模板
- 工作流可保存、编辑、复用
- 执行时支持流式输出
- 提供工作流模板供用户参考
- **AI根据用户描述自动生成工作流（工具选择+提示词+变量）**
- **支持用户描述交易策略，AI生成对应分析工作流**

### Non-Goals
- 不支持复杂的条件分支逻辑（v1.0简化版本）
- 不支持定时调度执行
- 不支持多用户协作编辑

## Decisions

### 1. 工作流数据模型

```python
class AIWorkflow(BaseModel):
    id: str                          # 工作流唯一ID
    name: str                        # 工作流名称
    description: str                 # 工作流描述
    system_prompt: str               # 系统提示词（定义AI角色和行为）
    user_prompt_template: str        # 用户提示词模板（支持变量替换）
    selected_tools: List[str]        # 选中的MCP工具名称列表
    variables: List[WorkflowVariable]  # 工作流变量定义
    is_template: bool                # 是否为模板
    created_at: datetime
    updated_at: datetime
    
class WorkflowVariable(BaseModel):
    name: str                        # 变量名（如 stock_code）
    label: str                       # 显示标签
    type: str                        # 类型: string, number, date, stock_code
    required: bool
    default: Optional[str]
```

**Rationale**: 简洁的数据模型，支持提示词模板和工具选择，变量机制允许用户在执行时动态输入参数。

### 2. 工作流执行架构

```
用户输入 -> 变量替换 -> 构建消息 -> DeepAgent执行 -> 流式输出
                                      ↓
                              使用选定的MCP工具
```

**实现方式**:
- 复用现有 `LangGraphAgent` 基类的执行能力
- 创建 `WorkflowAgent` 动态加载用户选择的工具
- 通过 `MCPClient` 调用工具

```python
class WorkflowAgent(LangGraphAgent):
    def __init__(self, workflow: AIWorkflow):
        self.workflow = workflow
        config = AgentConfig(
            name=f"workflow_{workflow.id}",
            description=workflow.description,
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        # 动态加载工作流选择的工具
        return self._load_mcp_tools(self.workflow.selected_tools)
    
    def get_system_prompt(self) -> str:
        return self.workflow.system_prompt
```

### 3. AI工作流生成器

**核心能力**: 用户用自然语言描述交易策略或分析需求，AI自动生成工作流配置。

```python
class WorkflowGeneratorAgent(LangGraphAgent):
    """AI工作流生成器 - 根据用户描述生成工作流配置"""
    
    def __init__(self):
        config = AgentConfig(
            name="workflow_generator",
            description="根据用户描述生成AI工作流配置",
        )
        super().__init__(config)
        self.available_tools = []  # 系统可用的MCP工具列表
    
    def get_system_prompt(self) -> str:
        tools_desc = self._format_tools_description()
        return f"""你是一个AI工作流配置生成器。用户会描述他们想要的股票分析策略或交易方式，
你需要根据描述生成合适的工作流配置。

## 可用的MCP工具
{tools_desc}

## 输出格式
你需要生成以下JSON格式的工作流配置：
{{
    "name": "工作流名称",
    "description": "工作流描述",
    "system_prompt": "系统提示词，定义AI角色和分析方法",
    "user_prompt_template": "用户提示词模板，使用{{{{变量名}}}}表示变量",
    "selected_tools": ["工具1", "工具2"],
    "variables": [
        {{"name": "变量名", "label": "显示标签", "type": "类型", "required": true}}
    ]
}}

## 生成原则
1. 根据用户描述选择最相关的工具
2. system_prompt应清晰定义AI的分析角色和方法论
3. user_prompt_template应包含具体的分析任务和使用变量
4. 变量类型支持: string, number, date, stock_code, stock_list
5. 为常见的交易策略场景提供专业的分析框架
"""

    async def generate_workflow(self, user_description: str) -> AIWorkflow:
        """根据用户描述生成工作流配置"""
        # 调用LLM生成配置
        response = await self.invoke(user_description)
        # 解析JSON配置
        config = self._parse_workflow_config(response)
        return AIWorkflow(**config)
```

**示例交互**:

用户输入：
> "我想要一个能帮我分析价值投资股票的工作流，主要看PE、PB、ROE这些指标，找出被低估的股票"

AI生成的工作流：
```json
{
    "name": "价值投资分析器",
    "description": "基于PE/PB/ROE等估值指标分析股票价值，发现被低估的投资机会",
    "system_prompt": "你是一位专业的价值投资分析师...",
    "user_prompt_template": "请分析股票{{stock_code}}的价值投资潜力...",
    "selected_tools": ["query_stock_valuation", "query_stock_financial", "query_stock_daily"],
    "variables": [
        {"name": "stock_code", "label": "股票代码", "type": "stock_code", "required": true}
    ]
}
```

### 4. 前端界面设计

#### 工作流编辑器布局
```
+-------------------------------------------+
|  工作流名称 [输入框]    [保存] [执行]       |
+-------------------------------------------+
| 工具面板          |  提示词编辑器          |
| +--------------+  |  +------------------+  |
| | [x] 股票日线  |  |  | 系统提示词:      |  |
| | [x] 股票估值  |  |  | [多行文本框]     |  |
| | [ ] ETF数据   |  |  +------------------+  |
| | [ ] 指数数据  |  |  | 用户提示词模板:  |  |
| | ...          |  |  | [多行文本框]     |  |
| +--------------+  |  +------------------+  |
|                   |  | 变量配置:         |  |
|                   |  | + 添加变量        |  |
+-------------------+--+--------------------+
```

#### AI生成工作流对话框
```
+---------------------------------------------+
|  AI智能生成工作流                    [关闭]   |
+---------------------------------------------+
|  描述你想要的分析策略或交易方式:              |
|  +---------------------------------------+  |
|  | 例如：我想要一个能帮我筛选高股息低估值   |  |
|  | 的股票的工作流，关注股息率>3%且PE<20   |  |
|  | 的股票                                 |  |
|  +---------------------------------------+  |
|                                             |
|  [生成中...显示AI思考过程]                   |
|                                             |
|  [取消]                    [生成工作流]      |
+---------------------------------------------+
```

#### 路由结构
- `/workflow` - 工作流列表
- `/workflow/create` - 创建工作流
- `/workflow/:id/edit` - 编辑工作流
- `/workflow/:id/run` - 执行工作流

### 5. API设计

```
GET    /api/workflows              # 获取工作流列表
POST   /api/workflows              # 创建工作流
GET    /api/workflows/:id          # 获取工作流详情
PUT    /api/workflows/:id          # 更新工作流
DELETE /api/workflows/:id          # 删除工作流

GET    /api/workflows/tools        # 获取可用工具列表
POST   /api/workflows/:id/execute  # 执行工作流（流式）
GET    /api/workflows/templates    # 获取工作流模板

# AI生成工作流API
POST   /api/workflows/generate     # AI根据描述生成工作流（流式）
```

#### AI生成工作流API详细设计

**请求**:
```json
POST /api/workflows/generate
{
    "description": "用户描述的分析策略或交易方式",
    "stream": true
}
```

**流式响应** (SSE):
```
event: thinking
data: {"content": "正在分析您的需求..."}

event: thinking
data: {"content": "为您选择合适的数据工具..."}

event: workflow
data: {"workflow": {...完整的工作流配置...}}

event: done
data: {}
```

### 6. 存储方案

**v1.0**: JSON文件存储
- 存储位置: `data/workflows/`
- 文件格式: `{workflow_id}.json`

**Rationale**: 快速实现，后续可迁移到数据库。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| 工具调用耗时长 | 流式输出显示中间状态 |
| 提示词注入风险 | 对用户输入进行基本校验 |
| 工作流过于复杂 | v1.0限制工具数量上限（如10个）|
| AI生成的工作流不符合预期 | 允许用户在生成后手动编辑调整 |
| 用户描述过于模糊 | 引导用户提供更具体的分析需求 |

## Migration Plan

1. 新增功能，无需迁移
2. 提供3-5个预置模板帮助用户上手

## Open Questions

1. 是否需要支持工作流版本管理？（建议v2.0考虑）
2. 是否需要支持工作流分享？（建议v2.0考虑）
3. AI生成工作流时是否需要支持多轮对话优化？（建议v2.0考虑）
