"""Chat Agent for A-share stock conversations using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable
import logging
import json

from .base_agent import LangGraphAgent, AgentConfig
from .tools import get_market_overview, get_stock_info

logger = logging.getLogger(__name__)


# A股知识工具
def get_astock_knowledge() -> str:
    """获取A股基础知识。
    
    Returns:
        A股交易规则、涨跌停限制、主要指数等基础知识。
    """
    return """## A股基础知识

### 交易时间
- 开盘集合竞价: 9:15-9:25
- 连续竞价: 9:30-11:30, 13:00-15:00
- 收盘集合竞价: 14:57-15:00

### 涨跌停限制
- 主板: 10%
- 创业板/科创板: 20%
- ST股票: 5%
- 北交所: 30%

### 交易规则
- T+1交易制度
- 最小交易单位: 100股（1手）
- 科创板/创业板: 最小200股

### 主要指数
- 上证指数: 上海证券交易所综合指数
- 深证成指: 深圳证券交易所成分指数
- 创业板指: 创业板市场指数
- 科创50: 科创板50指数
- 沪深300: 沪深两市300只大盘股
- 中证500: 中盘股指数
"""


def get_platform_help() -> str:
    """获取平台使用帮助。
    
    Returns:
        AI智能选股平台的功能介绍和使用指南。
    """
    return """**AI智能选股平台使用指南**

📊 **行情分析**
- 输入"分析 + 股票名称/代码"查看技术分析
- 例如："分析贵州茅台"或"分析600519"

🔍 **智能选股**
- 描述您的选股条件，AI会帮您筛选
- 例如："找出市盈率低于20的股票"

📈 **财报研读**
- 输入"财报 + 股票名称"查看财务分析
- 例如："贵州茅台财报分析"

💼 **持仓管理**
- 在"持仓管理"页面添加和管理您的模拟持仓

📉 **策略回测**
- 在"策略回测"页面测试各种交易策略

🔄 **AI工作流**
- 输入"执行工作流 + 工作流名称"运行自定义工作流
- 输入"查看我的工作流"列出可用工作流

如需更多帮助，请随时提问！
"""


def list_user_workflows() -> str:
    """列出用户可用的AI工作流。
    
    Returns:
        用户创建的工作流列表和预置模板列表。
    """
    try:
        from stock_datasource.services.workflow_service import get_workflow_service
        
        service = get_workflow_service()
        workflows = service.list_workflows(include_templates=True)
        
        if not workflows:
            return "暂无可用的工作流。您可以在【AI工作流】页面创建新的工作流。"
        
        # 分类显示
        templates = [w for w in workflows if w.is_template]
        user_workflows = [w for w in workflows if not w.is_template]
        
        result = "## 可用的AI工作流\n\n"
        
        if user_workflows:
            result += "### 我的工作流\n"
            for w in user_workflows:
                vars_str = ", ".join([f"{v.label}" for v in w.variables]) if w.variables else "无"
                result += f"- **{w.name}**（ID: {w.id}）\n"
                result += f"  - 描述: {w.description or '无'}\n"
                result += f"  - 变量: {vars_str}\n"
            result += "\n"
        
        if templates:
            result += "### 预置模板\n"
            for w in templates:
                vars_str = ", ".join([f"{v.label}" for v in w.variables]) if w.variables else "无"
                result += f"- **{w.name}**（ID: {w.id}）\n"
                result += f"  - 描述: {w.description or '无'}\n"
                result += f"  - 变量: {vars_str}\n"
        
        result += "\n💡 使用方法：调用 execute_workflow 工具，传入工作流ID和变量值即可执行。"
        
        return result
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}")
        return f"获取工作流列表失败: {str(e)}"


def execute_workflow(workflow_id: str, variables: str = "{}") -> str:
    """执行指定的AI工作流。
    
    Args:
        workflow_id: 工作流ID，如 template_single_stock 或自定义工作流ID
        variables: JSON格式的变量值，如 {"stock_code": "600519.SH"}
    
    Returns:
        工作流执行结果
    """
    try:
        from stock_datasource.services.workflow_service import get_workflow_service
        from stock_datasource.agents.workflow_agent import create_workflow_agent
        import asyncio
        
        # 解析变量
        try:
            vars_dict = json.loads(variables) if isinstance(variables, str) else variables
        except json.JSONDecodeError:
            return f"变量格式错误，请使用JSON格式，如: {{\"stock_code\": \"600519.SH\"}}"
        
        # 获取工作流
        service = get_workflow_service()
        workflow = service.get_workflow(workflow_id)
        
        if not workflow:
            return f"未找到工作流: {workflow_id}。请使用 list_user_workflows 查看可用工作流。"
        
        # 验证必填变量
        for var in workflow.variables:
            if var.required and var.name not in vars_dict:
                if var.default:
                    vars_dict[var.name] = var.default
                else:
                    return f"缺少必填变量: {var.label} ({var.name})"
        
        # 创建工作流Agent并执行
        agent = create_workflow_agent(workflow)
        
        # 同步执行（收集所有结果）
        async def run_workflow():
            content_parts = []
            async for event in agent.execute_workflow(vars_dict):
                event_type = event.get("type")
                if event_type == "content":
                    content_parts.append(event.get("content", ""))
                elif event_type == "error":
                    return f"执行错误: {event.get('error', '未知错误')}"
            return "".join(content_parts)
        
        # 运行异步任务
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(run_workflow())
        
        if not result:
            return f"工作流 {workflow.name} 执行完成，但未返回结果。"
        
        return f"## {workflow.name} 执行结果\n\n{result}"
        
    except Exception as e:
        logger.error(f"Failed to execute workflow {workflow_id}: {e}")
        return f"执行工作流失败: {str(e)}"


def find_workflow_by_name(name: str) -> str:
    """根据名称查找工作流。
    
    Args:
        name: 工作流名称（支持模糊匹配）
    
    Returns:
        匹配的工作流信息
    """
    try:
        from stock_datasource.services.workflow_service import get_workflow_service
        
        service = get_workflow_service()
        workflows = service.list_workflows(include_templates=True)
        
        # 模糊匹配
        matches = []
        name_lower = name.lower()
        for w in workflows:
            if name_lower in w.name.lower() or (w.description and name_lower in w.description.lower()):
                matches.append(w)
        
        if not matches:
            return f"未找到包含 '{name}' 的工作流。请使用 list_user_workflows 查看所有可用工作流。"
        
        result = f"## 找到 {len(matches)} 个匹配的工作流\n\n"
        for w in matches:
            vars_info = []
            for v in w.variables:
                req = "必填" if v.required else "选填"
                vars_info.append(f"{v.label}({v.name}, {req})")
            
            result += f"### {w.name}\n"
            result += f"- **ID**: `{w.id}`\n"
            result += f"- **描述**: {w.description or '无'}\n"
            result += f"- **变量**: {', '.join(vars_info) if vars_info else '无'}\n"
            result += f"- **类型**: {'预置模板' if w.is_template else '自定义工作流'}\n\n"
        
        return result
    except Exception as e:
        logger.error(f"Failed to find workflow: {e}")
        return f"查找工作流失败: {str(e)}"


class ChatAgent(LangGraphAgent):
    """Chat Agent for handling A-share stock conversations using DeepAgents.
    
    Handles:
    - General greetings and small talk
    - Questions about the platform
    - A-share market general questions
    - AI Workflow execution and management
    - Fallback for unrecognized intents
    """
    
    def __init__(self):
        config = AgentConfig(
            name="ChatAgent",
            description="负责处理A股相关的一般性对话和问答，以及AI工作流的调用"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return chat tools."""
        return [
            get_astock_knowledge,
            get_platform_help,
            get_market_overview,
            get_stock_info,
            # 工作流相关工具
            list_user_workflows,
            execute_workflow,
            find_workflow_by_name,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for chat agent."""
        return """你是一个专业的A股投资助手，专注于中国A股市场的问答和分析。

## 可用工具
- get_astock_knowledge: 获取A股基础知识（交易规则、涨跌停等）
- get_platform_help: 获取平台使用帮助
- get_market_overview: 获取市场整体情况
- get_stock_info: 获取股票信息

### AI工作流工具（重要！）
- list_user_workflows: 列出用户的所有工作流和预置模板
- find_workflow_by_name: 根据名称查找工作流
- execute_workflow: 执行指定的AI工作流

## 你的职责
1. 回答用户关于A股市场的各种问题
2. 提供平台使用帮助
3. 解答股票投资基础知识
4. **管理和执行AI工作流**
5. 引导用户使用合适的功能

## AI工作流调用指南
当用户提到以下内容时，应该使用工作流功能：
- "执行工作流"、"运行工作流" → 调用 execute_workflow
- "查看工作流"、"我的工作流"、"工作流列表" → 调用 list_user_workflows
- "单股分析"、"股票对比"、"价值投资" → 查找并执行相应模板
- "分析XXX股票用YYY工作流" → 找到工作流并执行

执行工作流示例：
1. 用户说"用单股分析工作流分析茅台"
2. 调用 execute_workflow(workflow_id="template_single_stock", variables='{"stock_code": "600519.SH"}')

## 回答原则
1. 专注于A股市场，不涉及其他市场
2. 回答要专业、准确、简洁
3. 涉及投资建议时，提醒风险
4. 如果问题超出能力范围，引导用户使用其他功能

## 常见问题快速回答
- 问候语：友好回应并介绍功能
- 帮助：调用 get_platform_help
- A股规则：调用 get_astock_knowledge
- 工作流相关：调用相应的工作流工具

## 免责声明
分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""
