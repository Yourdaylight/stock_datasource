"""Orchestrator Agent for routing and coordinating multiple LangGraph agents.

Uses LangGraph to create a multi-agent workflow that routes user requests
to the appropriate specialized agent.

Features:
- Plan-to-do thinking: Shows the execution plan before routing
- ReAct mode: Progressive reasoning when using MCP fallback
- Streaming events: Real-time thinking/tool/content updates
- Concurrent agent execution: Parallel execution of independent agents
- Agent handoff: Transfer control between agents with shared context
- Shared cache: Redis-based data sharing between agents
"""

import re
import json
import logging
import importlib
import inspect
import os
import pkgutil
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple

from .base_agent import (
    LangGraphAgent,
    AgentResult,
    compress_tool_result,
    get_langchain_model,
    get_langfuse_handler,
)
from stock_datasource.services.mcp_client import MCPClient
from stock_datasource.services.agent_cache import get_agent_cache, AgentSharedCache

logger = logging.getLogger(__name__)


AGENT_MODULE_SUFFIX = "_agent"
AGENT_EXCLUDE_CLASS_NAMES = {"OrchestratorAgent", "StockDeepAgent"}

# Agents that can run concurrently (independent, no data dependencies)
CONCURRENT_AGENT_GROUPS = [
    # Market + Report can run together for comprehensive stock analysis
    {"MarketAgent", "ReportAgent"},
    # Index + ETF can run together for market overview
    {"IndexAgent", "EtfAgent"},
    # Overview + TopList for market trends
    {"OverviewAgent", "TopListAgent"},
]

# Agent handoff configurations: agent_from -> [possible handoff targets]
AGENT_HANDOFF_MAP = {
    "MarketAgent": ["ReportAgent", "BacktestAgent"],  # After market analysis, can do financials or backtest
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],  # After screening, can analyze individual stocks
    "ReportAgent": ["BacktestAgent", "MarketAgent"],  # After financial analysis, can backtest or check market
    "OverviewAgent": ["MarketAgent", "IndexAgent"],  # After overview, can drill down
}


class OrchestratorAgent:
    """Orchestrator for routing requests to specialized LangGraph agents.
    
    This orchestrator:
    1. Uses LLM to analyze intent and create execution plan
    2. Extracts stock codes from the query
    3. Routes to the appropriate specialized agent
    4. Falls back to MCP tools with ReAct reasoning when no agent matches
    """
    
    def __init__(self):
        self._agents: Dict[str, LangGraphAgent] = {}
        self._agent_classes: Dict[str, type] = {}
        self._agent_descriptions: Dict[str, str] = {}
        self._discovered = False
        self._cache: AgentSharedCache = get_agent_cache()
    
    def _discover_agents(self) -> None:
        if self._discovered:
            return
        try:
            import stock_datasource.agents as agents_pkg
            for module_info in pkgutil.iter_modules(agents_pkg.__path__, agents_pkg.__name__ + "."):
                module_name = module_info.name
                if not module_name.endswith(AGENT_MODULE_SUFFIX):
                    continue
                try:
                    module = importlib.import_module(module_name)
                except Exception as e:
                    logger.debug(f"Failed to import {module_name}: {e}")
                    continue
                for _, obj in inspect.getmembers(module, inspect.isclass):
                    if not issubclass(obj, LangGraphAgent) or obj is LangGraphAgent:
                        continue
                    if obj.__name__ in AGENT_EXCLUDE_CLASS_NAMES:
                        continue
                    if not obj.__module__.startswith("stock_datasource.agents"):
                        continue
                    try:
                        instance = obj()
                    except Exception as e:
                        logger.debug(f"Skip agent {obj.__name__}: {e}")
                        continue
                    name = instance.config.name
                    self._agent_classes[name] = obj
                    self._agent_descriptions[name] = instance.config.description
        finally:
            self._discovered = True

    def _list_available_agents(self) -> List[Dict[str, str]]:
        self._discover_agents()
        return [
            {"name": name, "description": desc}
            for name, desc in self._agent_descriptions.items()
        ]

    def _get_agent(self, agent_name: str) -> Optional[LangGraphAgent]:
        """Get or create an agent by name."""
        self._discover_agents()
        agent_cls = self._agent_classes.get(agent_name)
        if not agent_cls:
            return None
        if agent_name not in self._agents:
            self._agents[agent_name] = agent_cls()
        return self._agents[agent_name]
    
    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.S)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return {}
        return {}

    async def _classify_with_llm(self, query: str) -> Tuple[str, Optional[str], str]:
        """Classify user intent and select appropriate agent.
        
        Returns:
            Tuple of (intent, agent_name, rationale)
        """
        self._discover_agents()
        agents = self._list_available_agents()
        if not agents:
            return "unknown", None, "没有可用的Agent"
        system_prompt = (
            "你是一个智能协调Agent。你的任务是：\n"
            "1. 理解用户的意图\n"
            "2. 从提供的Agent列表中选择最合适的agent_name\n"
            "3. 给出简短的推理说明\n\n"
            "仅输出JSON，格式: {\"intent\": string, \"agent_name\": string, \"rationale\": string}。\n"
            "如果没有匹配的Agent，请将agent_name设为空字符串。\n\n"
            "intent的可选值: market_analysis, stock_screening, financial_report, portfolio_management, "
            "strategy_backtest, index_analysis, etf_analysis, market_overview, news_analysis, general_chat"
        )
        user_prompt = (
            f"User query: {query}\n\n"
            f"可用Agents: {json.dumps(agents, ensure_ascii=False)}"
        )
        try:
            model = get_langchain_model()
            callbacks = []
            handler = get_langfuse_handler()
            if handler:
                callbacks.append(handler)
            response = await model.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                config={"callbacks": callbacks} if callbacks else None,
            )
            content = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_json_from_text(content)
            intent = parsed.get("intent") or "unknown"
            agent_name = parsed.get("agent_name") or ""
            rationale = parsed.get("rationale") or ""
            if agent_name not in self._agent_classes:
                agent_name = None
            return intent, agent_name, rationale
        except Exception as e:
            logger.warning(f"LLM classify failed: {e}")
            fallback_agent = "ChatAgent" if "ChatAgent" in self._agent_classes else None
            return ("general_chat" if fallback_agent else "unknown"), fallback_agent, "使用默认处理"
    
    def _extract_stock_codes(self, query: str) -> List[str]:
        """Extract stock codes from query."""
        codes = []
        
        # Pattern: 600519.SH or 000001.SZ
        pattern1 = r'(\d{6}\.[A-Za-z]{2})'
        matches = re.findall(pattern1, query)
        codes.extend([m.upper() for m in matches])
        
        # Pattern: 6-digit code
        pattern2 = r'(?<!\d)(\d{6})(?!\d)'
        matches = re.findall(pattern2, query)
        for code in matches:
            if code.startswith('6'):
                codes.append(f"{code}.SH")
            elif code.startswith(('0', '3')):
                codes.append(f"{code}.SZ")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)
        
        return unique_codes

    def _build_multi_agent_plan(self, primary_agent: Optional[str], stock_codes: List[str]) -> List[str]:
        """Build execution plan with optional concurrent agents.
        
        Args:
            primary_agent: The main agent to handle the request
            stock_codes: Extracted stock codes from query
            
        Returns:
            List of agent names to execute (in order, concurrent ones grouped)
        """
        self._discover_agents()
        if not primary_agent:
            return []
        plan = [primary_agent]
        
        # Check if we can add concurrent agents for richer analysis
        if stock_codes and primary_agent == "MarketAgent" and "ReportAgent" in self._agent_classes:
            if "ReportAgent" not in plan:
                plan.append("ReportAgent")
        
        return plan

    def _can_run_concurrently(self, agents: List[str]) -> bool:
        """Check if agents can run concurrently.
        
        Args:
            agents: List of agent names
            
        Returns:
            True if all agents in the list can run concurrently
        """
        agent_set = set(agents)
        for concurrent_group in CONCURRENT_AGENT_GROUPS:
            if agent_set.issubset(concurrent_group):
                return True
        return False

    def _get_handoff_targets(self, agent_name: str) -> List[str]:
        """Get possible handoff targets for an agent.
        
        Args:
            agent_name: Source agent name
            
        Returns:
            List of possible target agent names
        """
        return AGENT_HANDOFF_MAP.get(agent_name, [])

    def _build_agent_query(self, agent_name: str, query: str, stock_codes: List[str]) -> str:
        """Build query for a specific agent.
        
        Args:
            agent_name: Target agent name
            query: Original user query
            stock_codes: Extracted stock codes
            
        Returns:
            Query string tailored for the agent
        """
        if agent_name == "ReportAgent" and stock_codes:
            return f"请对{stock_codes[0]}进行财务分析"
        return query

    def _share_data_to_next_agent(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str,
        data: Dict[str, Any]
    ) -> bool:
        """Share data from one agent to another via cache.
        
        Args:
            session_id: Session ID
            from_agent: Source agent name
            to_agent: Target agent name
            data: Data to share
            
        Returns:
            True if successful
        """
        return self._cache.share_data_between_agents(session_id, from_agent, to_agent, data)

    def _receive_shared_data(
        self,
        session_id: str,
        from_agent: str,
        to_agent: str
    ) -> Optional[Dict[str, Any]]:
        """Receive data shared from another agent.
        
        Args:
            session_id: Session ID
            from_agent: Source agent name
            to_agent: Target agent name
            
        Returns:
            Shared data or None
        """
        return self._cache.receive_shared_data(session_id, from_agent, to_agent)

    def _cache_stock_data(self, ts_code: str, data_type: str, data: Any) -> bool:
        """Cache stock data for sharing between agents.
        
        Args:
            ts_code: Stock code
            data_type: Type of data (info, daily, etc.)
            data: Data to cache
            
        Returns:
            True if successful
        """
        if data_type == "info":
            return self._cache.cache_stock_info(ts_code, data)
        elif data_type == "daily":
            # For daily data, we need start/end dates
            return False
        elif data_type == "financial":
            # For financial, we need period
            return False
        return False

    def _get_cached_stock_data(self, ts_code: str, data_type: str) -> Optional[Any]:
        """Get cached stock data.
        
        Args:
            ts_code: Stock code
            data_type: Type of data
            
        Returns:
            Cached data or None
        """
        if data_type == "info":
            return self._cache.get_stock_info(ts_code)
        elif data_type == "realtime":
            return self._cache.get_stock_realtime(ts_code)
        return None

    def _parse_tool_call_from_query(self, query: str) -> Tuple[Optional[str], Dict[str, Any]]:
        if not query:
            return None, {}
        stripped = query.strip()
        json_payload = None
        if stripped.startswith("{") and stripped.endswith("}"):
            json_payload = stripped
        else:
            match = re.search(r"\{.*\}", query, re.S)
            if match:
                json_payload = match.group(0)
        if not json_payload:
            return None, {}
        try:
            data = json.loads(json_payload)
        except Exception:
            return None, {}
        tool_name = data.get("tool") or data.get("name") or data.get("tool_name")
        args = data.get("args") or data.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        return tool_name, args

    def _normalize_tool(self, tool: Any) -> Tuple[str, str, Dict[str, Any]]:
        if isinstance(tool, dict):
            name = tool.get("name", "")
            desc = tool.get("description", "")
            schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        else:
            name = getattr(tool, "name", "")
            desc = getattr(tool, "description", "")
            schema = getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}
        return name, desc or "", schema or {}

    def _score_tool(self, query: str, name: str, desc: str) -> int:
        query_lower = query.lower()
        tokens = set(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", f"{name} {desc}".lower()))
        return sum(1 for t in tokens if t and t in query_lower)

    def _select_mcp_tool(self, query: str, tools: List[Any]) -> Tuple[Optional[str], Dict[str, Any]]:
        best_score = 0
        best_tool = None
        best_schema: Dict[str, Any] = {}
        for tool in tools:
            name, desc, schema = self._normalize_tool(tool)
            if not name:
                continue
            score = self._score_tool(query, name, desc)
            if score > best_score:
                best_score = score
                best_tool = name
                best_schema = schema
        if best_score == 0:
            return None, {}
        return best_tool, best_schema

    async def _execute_with_mcp(
        self,
        query: str,
        context: Dict[str, Any],
        intent: str,
        stock_codes: List[str],
    ) -> AgentResult:
        client = MCPClient(server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp"))
        await client.connect()
        tool_calls = []
        try:
            tools = await client.list_tools()
            tool_name, tool_args = self._parse_tool_call_from_query(query)
            tool_schema = {}
            if tool_name:
                for tool in tools:
                    name, _, schema = self._normalize_tool(tool)
                    if name == tool_name:
                        tool_schema = schema
                        break
            else:
                tool_name, tool_schema = self._select_mcp_tool(query, tools)
            if not tool_name:
                return AgentResult(
                    response="未找到可用的MCP工具，请提供明确的工具名称或参数。",
                    success=False,
                    metadata={
                        "agent": "MCPFallback",
                        "routed_by": "OrchestratorAgent",
                        "intent": intent,
                        "stock_codes": stock_codes,
                        "available_agents": self._list_available_agents(),
                    },
                )
            required = tool_schema.get("required", []) if isinstance(tool_schema, dict) else []
            if required and not all(k in tool_args for k in required):
                return AgentResult(
                    response=f"缺少必要参数: {required}",
                    success=False,
                    metadata={
                        "agent": "MCPFallback",
                        "routed_by": "OrchestratorAgent",
                        "intent": intent,
                        "stock_codes": stock_codes,
                        "tool": tool_name,
                        "available_agents": self._list_available_agents(),
                    },
                )
            result = await client.call_tool(tool_name, **tool_args)
            tool_calls.append({"name": tool_name, "args": tool_args})
            return AgentResult(
                response=str(compress_tool_result(result)),
                success=True,
                metadata={
                    "agent": "MCPFallback",
                    "routed_by": "OrchestratorAgent",
                    "intent": intent,
                    "stock_codes": stock_codes,
                },
                tool_calls=tool_calls,
            )
        finally:
            await client.disconnect()

    async def _execute_with_mcp_stream(
        self,
        query: str,
        context: Dict[str, Any],
        intent: str,
        stock_codes: List[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        client = MCPClient(server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp"))
        tool_calls = []
        try:
            await client.connect()
            yield {
                "type": "thinking",
                "agent": "MCPFallback",
                "status": "尝试使用MCP工具",
                "intent": intent,
                "stock_codes": stock_codes,
            }
            tools = await client.list_tools()
            tool_name, tool_args = self._parse_tool_call_from_query(query)
            tool_schema = {}
            if tool_name:
                for tool in tools:
                    name, _, schema = self._normalize_tool(tool)
                    if name == tool_name:
                        tool_schema = schema
                        break
            else:
                tool_name, tool_schema = self._select_mcp_tool(query, tools)
            if not tool_name:
                yield {
                    "type": "error",
                    "error": "未找到可用的MCP工具，请提供明确的工具名称或参数。",
                }
                return
            required = tool_schema.get("required", []) if isinstance(tool_schema, dict) else []
            if required and not all(k in tool_args for k in required):
                yield {
                    "type": "error",
                    "error": f"缺少必要参数: {required}",
                }
                return
            yield {
                "type": "tool",
                "tool": tool_name,
                "args": tool_args,
            }
            result = await client.call_tool(tool_name, **tool_args)
            tool_calls.append({"name": tool_name, "args": tool_args})
            yield {
                "type": "content",
                "content": str(compress_tool_result(result)),
            }
            yield {
                "type": "done",
                "metadata": {
                    "agent": "MCPFallback",
                    "intent": intent,
                    "stock_codes": stock_codes,
                    "tool_calls": tool_calls,
                    "routed_by": "OrchestratorAgent",
                },
            }
        except Exception as e:
            logger.error(f"MCP fallback failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }
        finally:
            await client.disconnect()

    async def _execute_with_mcp_react_stream(
        self,
        query: str,
        context: Dict[str, Any],
        intent: str,
        stock_codes: List[str],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute MCP tools using ReAct (Reasoning + Acting) pattern.
        
        This method progressively reasons about the query and selects appropriate
        MCP tools, showing the thinking process to the user.
        """
        client = MCPClient(server_url=os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp"))
        tool_calls = []
        react_steps = []
        
        try:
            await client.connect()
            
            # Step 1: List available tools
            yield {
                "type": "thinking",
                "agent": "MCPFallback",
                "status": "🔍 正在分析可用工具...",
                "intent": intent,
                "stock_codes": stock_codes,
            }
            
            tools = await client.list_tools()
            tool_summaries = []
            for tool in tools[:20]:  # Limit to first 20 tools for context
                name, desc, _ = self._normalize_tool(tool)
                if name:
                    tool_summaries.append(f"- {name}: {desc[:100]}")
            
            # Step 2: Use LLM to reason about which tool to use (ReAct Thought)
            yield {
                "type": "thinking",
                "agent": "MCPFallback",
                "status": "💭 正在推理最佳处理方案...",
                "intent": intent,
                "stock_codes": stock_codes,
            }
            
            react_prompt = f"""你是一个使用ReAct模式的智能助手。你需要逐步思考并选择合适的工具。

用户问题: {query}

可用工具:
{chr(10).join(tool_summaries[:15])}

请使用以下格式回答:
Thought: [你的思考过程]
Action: [选择的工具名称]
Action Input: [工具参数，JSON格式]

如果无法找到合适的工具，请回答:
Thought: [说明为什么没有合适的工具]
Action: none
Action Input: {{}}
"""
            
            try:
                model = get_langchain_model()
                callbacks = []
                handler = get_langfuse_handler()
                if handler:
                    callbacks.append(handler)
                
                response = await model.ainvoke(
                    [{"role": "user", "content": react_prompt}],
                    config={"callbacks": callbacks} if callbacks else None,
                )
                
                react_response = response.content if hasattr(response, "content") else str(response)
                
                # Parse ReAct response
                thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|$)", react_response, re.S)
                action_match = re.search(r"Action:\s*(\S+)", react_response)
                input_match = re.search(r"Action Input:\s*(\{.*?\})", react_response, re.S)
                
                thought = thought_match.group(1).strip() if thought_match else ""
                action = action_match.group(1).strip() if action_match else ""
                action_input = {}
                
                if input_match:
                    try:
                        action_input = json.loads(input_match.group(1))
                    except:
                        pass
                
                # Step 3: Show the thought process
                if thought:
                    react_steps.append({"thought": thought, "action": action})
                    yield {
                        "type": "thinking",
                        "agent": "MCPFallback",
                        "status": f"💡 {thought[:100]}..." if len(thought) > 100 else f"💡 {thought}",
                        "intent": intent,
                        "stock_codes": stock_codes,
                    }
                
                # Step 4: Execute the action
                if action and action.lower() != "none":
                    # Find the tool
                    tool_name = None
                    tool_schema = {}
                    for tool in tools:
                        name, _, schema = self._normalize_tool(tool)
                        if name.lower() == action.lower() or action.lower() in name.lower():
                            tool_name = name
                            tool_schema = schema
                            break
                    
                    if tool_name:
                        yield {
                            "type": "tool",
                            "tool": tool_name,
                            "args": action_input,
                            "agent": "MCPFallback",
                            "status": f"⚡ 执行: {tool_name}",
                        }
                        
                        # Execute the tool
                        result = await client.call_tool(tool_name, **action_input)
                        tool_calls.append({"name": tool_name, "args": action_input})
                        
                        # Use LLM to summarize the result
                        compressed = compress_tool_result(result)
                        
                        summary_prompt = f"""用户问题: {query}

工具 {tool_name} 返回结果:
{str(compressed)[:2000]}

请用中文简洁地总结上述结果，帮助用户理解。如果结果是数据，请提取关键信息。"""
                        
                        summary_response = await model.ainvoke(
                            [{"role": "user", "content": summary_prompt}],
                            config={"callbacks": callbacks} if callbacks else None,
                        )
                        
                        summary = summary_response.content if hasattr(summary_response, "content") else str(compressed)
                        
                        yield {
                            "type": "content",
                            "content": summary,
                        }
                    else:
                        yield {
                            "type": "content",
                            "content": f"抱歉，找不到名为 '{action}' 的工具。请尝试更具体的描述。",
                        }
                else:
                    # No suitable tool found
                    yield {
                        "type": "content",
                        "content": "抱歉，当前没有找到合适的工具来处理您的请求。请尝试使用以下方式提问：\n"
                                   "- 查询股票行情时请提供股票代码（如：600519）\n"
                                   "- 需要K线数据时请说明时间范围\n"
                                   "- 需要财务数据时请指定具体的财务指标",
                    }
                    
            except Exception as e:
                logger.warning(f"ReAct reasoning failed: {e}")
                # Fallback to simple tool selection
                async for event in self._execute_with_mcp_stream(query, context, intent, stock_codes):
                    yield event
                return
            
            yield {
                "type": "done",
                "metadata": {
                    "agent": "MCPFallback",
                    "intent": intent,
                    "stock_codes": stock_codes,
                    "tool_calls": tool_calls,
                    "react_steps": react_steps,
                    "routed_by": "OrchestratorAgent",
                },
            }
            
        except Exception as e:
            logger.error(f"MCP ReAct fallback failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }
        finally:
            await client.disconnect()
    
    async def execute(self, query: str, context: Dict[str, Any] = None) -> AgentResult:
        """Execute query by routing to appropriate agent.
        
        Args:
            query: User's query
            context: Optional context
            
        Returns:
            AgentResult from the specialized agent
        """
        context = context or {}
        
        # Classify intent + agent via LLM
        intent, agent_name, rationale = await self._classify_with_llm(query)
        
        # Extract stock codes
        stock_codes = self._extract_stock_codes(query)
        
        # Update context
        context["intent"] = intent
        if stock_codes:
            context["stock_codes"] = stock_codes
        
        plan = self._build_multi_agent_plan(agent_name, stock_codes)
        if not plan:
            logger.info(f"No agent available for intent: {intent}, fallback to MCP")
            return await self._execute_with_mcp(query, context, intent, stock_codes)
        
        if len(plan) == 1:
            agent = self._get_agent(plan[0])
            if not agent:
                logger.info(f"No agent available for intent: {intent}, fallback to MCP")
                return await self._execute_with_mcp(query, context, intent, stock_codes)
            logger.info(f"Routing to {plan[0]} for intent: {intent}")
            result = await agent.execute(query, context)
            result.metadata["routed_by"] = "OrchestratorAgent"
            result.metadata["intent"] = intent
            result.metadata["stock_codes"] = stock_codes
            result.metadata["available_agents"] = self._list_available_agents()
            return result
        
        logger.info(f"Routing to multi-agent plan: {plan}")
        tasks = []
        names = []
        for agent_name in plan:
            agent = self._get_agent(agent_name)
            if not agent:
                continue
            agent_query = self._build_agent_query(agent_name, query, stock_codes)
            tasks.append(agent.execute(agent_query, context))
            names.append(agent_name)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        responses = []
        sub_metadata = []
        tool_calls = []
        success = True
        for agent_name, result in zip(names, results):
            if isinstance(result, Exception):
                success = False
                responses.append(f"### {agent_name}\n执行失败: {result}")
                sub_metadata.append({"agent": agent_name, "metadata": {"error": str(result)}})
                continue
            success = success and result.success
            title = self._agent_descriptions.get(agent_name, agent_name)
            responses.append(f"### {title}\n{result.response}")
            sub_metadata.append({"agent": agent_name, "metadata": result.metadata})
            tool_calls.extend(result.tool_calls or [])
        
        return AgentResult(
            response="\n\n".join(responses) if responses else "",
            success=success,
            metadata={
                "agent": "OrchestratorAgent",
                "routed_by": "OrchestratorAgent",
                "intent": intent,
                "stock_codes": stock_codes,
                "sub_agents": plan,
                "sub_agent_metadata": sub_metadata,
                "available_agents": self._list_available_agents(),
            },
            tool_calls=tool_calls,
        )
    
    async def execute_stream(
        self, 
        query: str, 
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute query with streaming response.
        
        Shows Plan-To-Do thinking process before execution.
        
        Args:
            query: User's query
            context: Optional context
            
        Yields:
            Event dicts from the specialized agent
        """
        context = context or {}
        session_id = context.get("session_id", "")
        
        # Try to get cached stock data if available
        if session_id:
            cached_context = self._cache.get_session_data(session_id, "orchestrator_context")
            if cached_context:
                context.update(cached_context)
        
        # Step 1: Emit initial thinking status
        yield {
            "type": "thinking",
            "agent": "OrchestratorAgent",
            "status": "正在理解您的需求...",
            "intent": "",
            "stock_codes": [],
        }
        
        # Classify intent + agent via LLM
        intent, agent_name, rationale = await self._classify_with_llm(query)
        
        # Extract stock codes
        stock_codes = self._extract_stock_codes(query)
        
        # Step 2: Emit plan thinking status with intent and rationale
        yield {
            "type": "thinking",
            "agent": "OrchestratorAgent",
            "status": f"意图分析: {rationale}" if rationale else "正在选择合适的处理方案...",
            "intent": intent,
            "stock_codes": stock_codes,
        }
        
        # Update context
        context["intent"] = intent
        if stock_codes:
            context["stock_codes"] = stock_codes
            
            # Pre-cache stock info for sharing between agents
            if session_id:
                # Cache stock codes for this session
                self._cache.set_session_data(session_id, "current_stock_codes", stock_codes)
                
                # Try to get cached stock info to speed up agents
                for ts_code in stock_codes[:3]:  # Limit to first 3 stocks
                    cached_info = self._cache.get_stock_info(ts_code)
                    if cached_info:
                        context.setdefault("cached_stock_info", {})[ts_code] = cached_info
        
        # Save orchestrator context for future reference
        if session_id:
            self._cache.set_session_data(session_id, "orchestrator_context", {
                "intent": intent,
                "agent_name": agent_name,
                "stock_codes": stock_codes,
            })
        
        plan = self._build_multi_agent_plan(agent_name, stock_codes)
        if not plan:
            logger.info(f"No agent available for intent: {intent}, fallback to MCP")
            # Emit status about using ReAct mode with MCP
            yield {
                "type": "thinking",
                "agent": "MCPFallback",
                "status": "使用ReAct模式逐步分析...",
                "intent": intent,
                "stock_codes": stock_codes,
            }
            async for event in self._execute_with_mcp_react_stream(query, context, intent, stock_codes):
                yield event
            return
        
        if len(plan) == 1:
            agent = self._get_agent(plan[0])
            if not agent:
                logger.info(f"No agent available for intent: {intent}, fallback to MCP")
                async for event in self._execute_with_mcp_stream(query, context, intent, stock_codes):
                    yield event
                return
            logger.info(f"Streaming via {plan[0]} for intent: {intent}")
            has_error = False
            error_msg = ""
            try:
                async for event in agent.execute_stream(query, context):
                    event_type = event.get("type")
                    if event_type == "thinking":
                        event.setdefault("agent", agent.config.name)
                        event["routed_by"] = "OrchestratorAgent"
                        event["intent"] = intent
                        event["stock_codes"] = stock_codes
                    elif event_type == "done":
                        metadata = event.get("metadata", {})
                        metadata["agent"] = metadata.get("agent", agent.config.name)
                        metadata["intent"] = intent
                        metadata["stock_codes"] = stock_codes
                        metadata["routed_by"] = "OrchestratorAgent"
                        metadata["available_agents"] = self._list_available_agents()
                        event["metadata"] = metadata
                    elif event_type == "error":
                        has_error = True
                        error_msg = event.get("error", "Unknown error")
                    yield event
            except Exception as e:
                has_error = True
                error_msg = str(e)
                logger.error(f"Agent {plan[0]} execution failed: {e}")
                # Emit error event
                yield {
                    "type": "error",
                    "error": f"{plan[0]} 执行出错: {error_msg}",
                    "agent": plan[0],
                }
            
            # If agent failed, try to provide a graceful response
            if has_error:
                yield {
                    "type": "content",
                    "content": f"\n\n> ⚠️ {plan[0]} 在处理过程中遇到问题: {error_msg}\n\n我正在尝试其他方式为您解答...",
                }
                # Fallback to MCP ReAct mode
                async for event in self._execute_with_mcp_react_stream(query, context, intent, stock_codes):
                    yield event
            return
        
        logger.info(f"Streaming via multi-agent plan: {plan}")
        tool_calls = []
        sub_metadata = []
        queue: asyncio.Queue = asyncio.Queue()
        active = 0
        heading_sent: Dict[str, bool] = {}

        async def _run_agent(agent_name: str):
            agent = self._get_agent(agent_name)
            if not agent:
                await queue.put((agent_name, {"type": "error", "error": f"Agent not found: {agent_name}"}))
                await queue.put((agent_name, {"type": "content", "content": f"\n> ⚠️ Agent {agent_name} 未找到\n"}))
                await queue.put((agent_name, None))
                return
            agent_query = self._build_agent_query(agent_name, query, stock_codes)
            try:
                async for event in agent.execute_stream(agent_query, context):
                    await queue.put((agent_name, event))
            except Exception as e:
                logger.error(f"Agent {agent_name} failed: {e}")
                await queue.put((agent_name, {"type": "error", "error": str(e)}))
                # Provide a graceful message instead of breaking
                await queue.put((agent_name, {
                    "type": "content", 
                    "content": f"\n> ⚠️ {agent_name} 处理过程中遇到问题: {str(e)[:100]}\n\n请稍后重试或换个问题。\n"
                }))
            finally:
                await queue.put((agent_name, None))

        tasks = []
        for agent_name in plan:
            heading_sent[agent_name] = False
            tasks.append(asyncio.create_task(_run_agent(agent_name)))
            active += 1

        while active > 0:
            agent_name, event = await queue.get()
            if event is None:
                active -= 1
                continue
            event_type = event.get("type")
            if event_type == "thinking":
                event.setdefault("agent", agent_name)
                event["routed_by"] = "OrchestratorAgent"
                event["intent"] = intent
                event["stock_codes"] = stock_codes
                yield event
            elif event_type == "content":
                if not heading_sent.get(agent_name):
                    title = self._agent_descriptions.get(agent_name, agent_name)
                    yield {"type": "content", "content": f"\n\n### {title}\n"}
                    heading_sent[agent_name] = True
                yield event
            elif event_type == "tool":
                event.setdefault("agent", agent_name)
                yield event
            elif event_type == "done":
                metadata = event.get("metadata", {})
                metadata["agent"] = metadata.get("agent", agent_name)
                metadata["intent"] = intent
                metadata["stock_codes"] = stock_codes
                metadata["routed_by"] = "OrchestratorAgent"
                sub_metadata.append({"agent": agent_name, "metadata": metadata})
                tool_calls.extend(metadata.get("tool_calls", []))
            elif event_type == "error":
                yield event
        
        for task in tasks:
            if not task.done():
                task.cancel()

        yield {
            "type": "done",
            "metadata": {
                "agent": "OrchestratorAgent",
                "intent": intent,
                "stock_codes": stock_codes,
                "routed_by": "OrchestratorAgent",
                "sub_agents": plan,
                "sub_agent_metadata": sub_metadata,
                "tool_calls": tool_calls,
                "available_agents": self._list_available_agents(),
            },
        }


# Singleton instance
_orchestrator: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """Get or create the orchestrator agent."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
