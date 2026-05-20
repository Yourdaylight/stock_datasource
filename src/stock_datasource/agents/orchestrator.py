"""Lightweight orchestrator for config-driven harness agents."""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

from .base_agent import AgentResult, get_langchain_model, get_langfuse_handler
from .config_driven_harness_agent import get_config_driven_agent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Classify chat intent and dispatch to ConfigDrivenHarnessAgent."""

    def _make_debug_event(
        self, debug_type: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "type": "debug",
            "debug_type": debug_type,
            "agent": "OrchestratorAgent",
            "timestamp": time.time(),
            "data": data,
        }

    def _parse_json_from_text(self, text: str) -> dict[str, Any]:
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

    def _list_available_agents(self) -> list[dict[str, str]]:
        try:
            from stock_datasource.services.agent_config_service import (
                get_agent_config_service,
            )

            service = get_agent_config_service()
            configs = service.list_agents(user_id="system", include_public=True)
        except Exception as e:
            logger.warning("Failed to load config-driven agent catalog: %s", e)
            return []

        seen: set[str] = set()
        agents: list[dict[str, str]] = []
        for config in configs:
            if not config.name or config.name in seen:
                continue
            seen.add(config.name)
            agents.append(
                {
                    "name": config.name,
                    "description": config.description or "Config-driven harness agent",
                }
            )
        return agents

    async def _classify_with_llm(
        self, query: str, context: dict[str, Any] | None = None
    ) -> tuple[str, str | None, str]:
        """Classify user intent and select a config-driven agent name."""
        agents = self._list_available_agents()
        if not agents:
            logger.warning("[Orchestrator] No config-driven agents available")
            return "unknown", None, "没有可用的Agent配置"

        system_prompt = (
            "你是一个智能协调Agent。你的任务是：\n"
            "1. 理解用户的意图\n"
            "2. 从提供的Agent列表中选择最合适的agent_name\n"
            "3. 给出简短的推理说明\n\n"
            '仅输出JSON，格式: {"intent": string, "agent_name": string, "rationale": string}。\n'
            "如果没有匹配的Agent，请将agent_name设为空字符串。\n\n"
            "intent的可选值: market_analysis, stock_screening, financial_report, "
            "hk_financial_report, hk_market_analysis, portfolio_management, "
            "strategy_backtest, index_analysis, etf_analysis, market_overview, "
            "news_analysis, knowledge_search, general_chat\n\n"
            "注意：\n"
            "- 如果用户询问港股（代码格式如00700.HK）的技术分析、K线、技术指标，"
            "intent设为market_analysis，agent_name选择最匹配的行情分析Agent\n"
            "- 如果用户询问研报、公告、政策文件、规章制度等文档内容，"
            "intent设为knowledge_search，agent_name选择最匹配的知识检索Agent"
        )
        user_prompt = (
            f"User query: {query}\n\n"
            f"可用Agents: {json.dumps(agents, ensure_ascii=False)}"
        )
        context = context or {}
        user_id = context.get("user_id", "")
        session_id = context.get("session_id", "")

        try:
            model = get_langchain_model()
            callbacks = []
            handler = get_langfuse_handler()
            if handler:
                callbacks.append(handler)

            metadata = {
                "langfuse_user_id": user_id,
                "langfuse_session_id": session_id,
                "langfuse_tags": ["OrchestratorAgent"],
            }
            config = {"callbacks": callbacks, "metadata": metadata} if callbacks else {"metadata": metadata}
            response = await model.ainvoke(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                config=config,
            )
            content = response.content if hasattr(response, "content") else str(response)
            parsed = self._parse_json_from_text(content)
            intent = parsed.get("intent") or "unknown"
            agent_name = parsed.get("agent_name") or ""
            rationale = parsed.get("rationale") or ""

            available_names = {agent["name"] for agent in agents}
            if agent_name not in available_names:
                logger.debug(
                    "[Orchestrator] Agent '%s' not found in config catalog",
                    agent_name,
                )
                agent_name = None
            logger.info(
                "[Orchestrator] Classified: intent=%s, agent=%s, rationale=%s",
                intent,
                agent_name,
                rationale[:50],
            )
            return intent, agent_name, rationale
        except Exception as e:
            logger.warning("[Orchestrator] LLM classify failed: %s", e)
            return "unknown", None, "意图识别失败"

    def _extract_stock_codes(self, query: str) -> list[str]:
        """Extract stock codes from query (supports A-share and HK)."""
        codes = []

        hk_matches = re.findall(r"(\d{5}\.HK)", query, re.IGNORECASE)
        codes.extend([match.upper() for match in hk_matches])

        a_matches = re.findall(r"(\d{6}\.[A-Za-z]{2})", query)
        codes.extend([match.upper() for match in a_matches])

        for code in re.findall(r"(?<!\d)(\d{6})(?!\d)", query):
            if code.startswith("6"):
                codes.append(f"{code}.SH")
            elif code.startswith(("0", "3")):
                codes.append(f"{code}.SZ")

        hk_keywords = ["港股", "港交所", "HK", "香港", "恒生"]
        has_hk_context = any(
            keyword in query.upper() for keyword in [item.upper() for item in hk_keywords]
        )
        if has_hk_context:
            for code in re.findall(r"(?<!\d)(\d{5})(?!\d)", query):
                formatted = f"{code}.HK"
                if formatted not in codes:
                    codes.append(formatted)

        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)
        return unique_codes

    def _error_event(
        self,
        message: str,
        intent: str,
        stock_codes: list[str],
        available_agents: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "type": "error",
            "error": message,
            "metadata": {
                "agent": "OrchestratorAgent",
                "intent": intent,
                "stock_codes": stock_codes,
                "routed_by": "OrchestratorAgent",
                "available_agents": available_agents,
            },
        }

    async def execute(self, query: str, context: dict[str, Any] = None) -> AgentResult:
        """Execute query and collect streaming output into an AgentResult."""
        content_parts: list[str] = []
        metadata: dict[str, Any] = {}
        tool_calls: list[dict[str, Any]] = []
        success = True

        async for event in self.execute_stream(query, context):
            event_type = event.get("type")
            if event_type == "content":
                content_parts.append(event.get("content", ""))
            elif event_type == "tool":
                tool_calls.append(
                    {
                        "name": event.get("tool", ""),
                        "args": event.get("args", {}),
                    }
                )
            elif event_type == "done":
                metadata = event.get("metadata", {})
            elif event_type == "error":
                success = False
                if not content_parts:
                    content_parts.append(event.get("error", ""))
                metadata = event.get("metadata", metadata)

        return AgentResult(
            response="".join(content_parts),
            success=success,
            metadata=metadata,
            tool_calls=tool_calls,
        )

    async def execute_stream(
        self, query: str, context: dict[str, Any] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Classify intent and stream from the selected ConfigDrivenHarnessAgent."""
        context = context or {}
        available_agents = self._list_available_agents()

        yield {
            "type": "thinking",
            "agent": "OrchestratorAgent",
            "status": "正在理解您的需求...",
            "intent": "",
            "stock_codes": [],
        }

        intent, agent_name, rationale = await self._classify_with_llm(query, context)
        stock_codes = self._extract_stock_codes(query)
        context["intent"] = intent
        if stock_codes:
            context["stock_codes"] = stock_codes

        yield self._make_debug_event(
            "classification",
            {
                "intent": intent,
                "selected_agent": agent_name,
                "rationale": rationale,
                "stock_codes": stock_codes,
                "available_agents": [agent["name"] for agent in available_agents],
            },
        )
        yield {
            "type": "thinking",
            "agent": "OrchestratorAgent",
            "status": f"意图分析: {rationale}" if rationale else "正在选择合适的处理方案...",
            "intent": intent,
            "stock_codes": stock_codes,
        }

        if not agent_name:
            error = "未找到匹配的Agent配置"
            yield self._error_event(error, intent, stock_codes, available_agents)
            yield {
                "type": "done",
                "metadata": {
                    "agent": "OrchestratorAgent",
                    "intent": intent,
                    "stock_codes": stock_codes,
                    "routed_by": "OrchestratorAgent",
                    "available_agents": available_agents,
                    "success": False,
                },
            }
            return

        agent = get_config_driven_agent(agent_name)
        if not agent:
            error = f"未找到Agent配置: {agent_name}"
            yield self._error_event(error, intent, stock_codes, available_agents)
            yield {
                "type": "done",
                "metadata": {
                    "agent": "OrchestratorAgent",
                    "intent": intent,
                    "stock_codes": stock_codes,
                    "routed_by": "OrchestratorAgent",
                    "selected_agent": agent_name,
                    "available_agents": available_agents,
                    "success": False,
                },
            }
            return

        yield self._make_debug_event(
            "routing",
            {
                "from_agent": "OrchestratorAgent",
                "to_agent": agent_name,
                "is_parallel": False,
                "plan": [agent_name],
            },
        )

        context["parent_agent"] = "OrchestratorAgent"
        done_seen = False
        try:
            async for event in agent.execute_stream(query, context):
                event_type = event.get("type")
                if event_type == "thinking":
                    event.setdefault("agent", agent.config.name)
                    event["routed_by"] = "OrchestratorAgent"
                    event["intent"] = intent
                    event["stock_codes"] = stock_codes
                elif event_type == "done":
                    done_seen = True
                    metadata = event.get("metadata", {})
                    metadata["agent"] = metadata.get("agent", agent.config.name)
                    metadata["intent"] = intent
                    metadata["stock_codes"] = stock_codes
                    metadata["routed_by"] = "OrchestratorAgent"
                    metadata["available_agents"] = available_agents
                    event["metadata"] = metadata
                yield event
        except Exception as e:
            logger.error("Agent %s execution failed: %s", agent_name, e)
            yield self._error_event(str(e), intent, stock_codes, available_agents)
            done_seen = False

        if not done_seen:
            yield {
                "type": "done",
                "metadata": {
                    "agent": agent_name,
                    "intent": intent,
                    "stock_codes": stock_codes,
                    "routed_by": "OrchestratorAgent",
                    "available_agents": available_agents,
                },
            }


_orchestrator: OrchestratorAgent | None = None


def get_orchestrator() -> OrchestratorAgent:
    """Get or create the orchestrator agent."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
