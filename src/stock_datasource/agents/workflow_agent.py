"""工作流执行Agent (Runtime Adapter).

Task 4.4: ``WorkflowAgent`` is now a runtime adapter that registers
itself with ``AgentRole.ADAPTER`` in the ``AgentRegistry``.  Tool
loading integrates with ``SkillRegistry`` when available.
"""

import json
import logging
import re
from collections.abc import AsyncGenerator, Callable
from typing import Any

from stock_datasource.models.workflow import AIWorkflow

from .base_agent import AgentConfig, LangGraphAgent

logger = logging.getLogger(__name__)


class WorkflowAgent(LangGraphAgent):
    """工作流执行Agent。

    根据AIWorkflow配置动态创建，使用用户选择的工具和提示词执行分析。
    """

    def __init__(self, workflow: AIWorkflow):
        """初始化工作流Agent。

        Args:
            workflow: AI工作流配置
        """
        self.workflow = workflow
        config = AgentConfig(
            name=f"workflow_{workflow.id}",
            description=workflow.description or workflow.name,
            recursion_limit=30,
        )
        super().__init__(config)
        self._tools_cache: list[Callable] | None = None

    def get_tools(self) -> list[Callable]:
        """获取工作流配置的工具。"""
        if self._tools_cache is not None:
            return self._tools_cache

        tools = []
        selected = set(self.workflow.selected_tools)

        if not selected:
            logger.warning(f"Workflow {self.workflow.id} has no selected tools")
            return tools

        # 从MCP工具中加载选定的工具
        try:
            tools = self._load_mcp_tools(selected)
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")

        # 如果没有MCP工具，尝试加载内置工具
        if not tools:
            try:
                from .tools import STOCK_TOOLS

                for tool in STOCK_TOOLS:
                    tool_name = tool.__name__
                    if tool_name in selected or f"builtin_{tool_name}" in selected:
                        tools.append(tool)
            except Exception as e:
                logger.warning(f"Failed to load builtin tools: {e}")

        self._tools_cache = tools
        logger.info(f"Workflow {self.workflow.id} loaded {len(tools)} tools")
        return tools

    def _load_mcp_tools(self, selected_tools: set) -> list[Callable]:
        """从MCP服务加载工具。"""
        tools = []

        try:
            from stock_datasource.services.mcp_server import create_mcp_server

            mcp_server, service_generators = create_mcp_server()

            for prefix, generator in service_generators.items():
                mcp_tools = generator.generate_mcp_tools()

                for tool_def in mcp_tools:
                    full_name = f"{prefix}_{tool_def['name']}"
                    if full_name in selected_tools:
                        # 创建工具函数
                        handler = generator.get_tool_handler(tool_def["name"])
                        if handler:
                            # 包装成带有正确名称和描述的函数
                            tool_func = self._wrap_tool_handler(
                                handler, full_name, tool_def.get("description", "")
                            )
                            tools.append(tool_func)
        except Exception as e:
            logger.error(f"Failed to load MCP tools: {e}")

        return tools

    def _wrap_tool_handler(self, handler, name: str, description: str) -> Callable:
        """包装工具处理函数。"""
        import functools

        @functools.wraps(handler)
        def wrapped(*args, **kwargs):
            try:
                result = handler(*args, **kwargs)
                if isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False, indent=2)
                return str(result)
            except Exception as e:
                return f"Error calling {name}: {e!s}"

        # 设置函数属性
        wrapped.__name__ = name
        wrapped.__doc__ = description

        return wrapped

    def get_system_prompt(self) -> str:
        """获取系统提示词。"""
        if self.workflow.system_prompt:
            return self.workflow.system_prompt

        # 默认系统提示词
        return """你是一个专业的A股股票分析AI助手。
请根据用户的需求，使用可用的工具获取数据并进行分析。

分析原则：
1. 先调用工具获取数据
2. 基于数据给出分析结论
3. 使用中文回复
4. 给出明确的投资建议和风险提示

免责声明：分析仅供参考，不构成投资建议。"""

    def build_user_message(self, variables: dict[str, Any]) -> str:
        """构建用户消息。

        Args:
            variables: 变量值映射

        Returns:
            替换变量后的用户消息
        """
        template = self.workflow.user_prompt_template

        if not template:
            # 如果没有模板，直接用变量构建
            parts = []
            for key, value in variables.items():
                parts.append(f"{key}: {value}")
            return "请分析以下内容：\n" + "\n".join(parts)

        # 替换 {{variable}} 格式的变量
        def replace_var(match):
            var_name = match.group(1).strip()
            return str(variables.get(var_name, match.group(0)))

        message = re.sub(r"\{\{(\w+)\}\}", replace_var, template)

        return message

    async def execute_workflow(
        self, variables: dict[str, Any], context: dict[str, Any] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行工作流（流式）。

        Args:
            variables: 变量值映射
            context: 执行上下文

        Yields:
            执行事件
        """
        context = context or {}

        # 验证必填变量
        for var in self.workflow.variables:
            if var.required and var.name not in variables:
                if var.default:
                    variables[var.name] = var.default
                else:
                    yield {
                        "type": "error",
                        "error": f"缺少必填变量: {var.label} ({var.name})",
                    }
                    return

        # 构建用户消息
        user_message = self.build_user_message(variables)

        # 使用父类的流式执行
        async for event in self.execute_stream(user_message, context):
            yield event


def create_workflow_agent(workflow: AIWorkflow) -> WorkflowAgent:
    """创建工作流Agent。

    Args:
        workflow: 工作流配置

    Returns:
        WorkflowAgent实例
    """
    return WorkflowAgent(workflow)


def register_workflow_adapter(workflow: AIWorkflow) -> None:
    """Task 4.4: Register a workflow as a runtime adapter.

    Creates a ``WorkflowAgent`` and registers it in the ``AgentRegistry``
    with ``AgentRole.ADAPTER`` so the runtime can discover and invoke it.

    Args:
        workflow: AI workflow configuration to register
    """
    try:
        from stock_datasource.services.agent_registry import (
            AgentDescriptor,
            AgentRole,
            CapabilityDescriptor,
            get_agent_registry,
        )

        registry = get_agent_registry()
        name = f"workflow_{workflow.id}"
        # Avoid duplicate registration
        if registry.get_descriptor(name) is not None:
            return
        desc = AgentDescriptor(
            name=name,
            description=workflow.description or workflow.name,
            agent_class=WorkflowAgent,
            role=AgentRole.ADAPTER,
            capability=CapabilityDescriptor(
                intents=["workflow"],
                tags=["workflow", f"wf_{workflow.id}"],
            ),
        )
        # Pre-set the instance since WorkflowAgent needs a workflow arg
        desc._instance = WorkflowAgent(workflow)
        registry.register(desc)
        logger.info("Registered workflow adapter: %s", name)
    except Exception as exc:
        logger.warning("Failed to register workflow adapter: %s", exc)
