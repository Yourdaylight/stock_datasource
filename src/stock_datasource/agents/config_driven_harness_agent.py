"""ConfigDrivenHarnessAgent — A single generic agent that dynamically builds
a harness agent from DB configuration.

Replaces per-agent .py files (harness_market_agent.py, harness_report_agent.py).
Users configure agents via UI:
  - system_prompt: agent's personality and instructions
  - skills: list of tool names → resolved to actual functions via tool_registry
  - model_config_data: model, temperature, max_tokens
  - runtime_config: type (langgraph/claude), MCP servers

The agent reads config from ClickHouse (via agent_config_service) at runtime
and dynamically assembles a create_deep_agent(...) instance.
"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from deepagents import create_deep_agent
from langgraph.store.memory import InMemoryStore

from stock_datasource.models.agent_config import AgentConfigResponse, ModelConfig
from stock_datasource.services.tool_registry import auto_discover_tools, resolve_tools

from .base_agent import (
    AgentConfig,
    LangGraphAgent,
    get_langchain_model,
    get_langfuse_handler,
)

logger = logging.getLogger(__name__)


# Shared store instance (module-level singleton)
_shared_store: InMemoryStore | None = None


def get_shared_store() -> InMemoryStore:
    """Get or create the shared InMemoryStore for all config-driven agents."""
    global _shared_store
    if _shared_store is None:
        _shared_store = InMemoryStore()
    return _shared_store


# Ensure tools are registered on import
_tools_discovered = False


def _ensure_tools_discovered() -> None:
    """Lazy tool discovery — only runs once."""
    global _tools_discovered
    if not _tools_discovered:
        auto_discover_tools()
        _tools_discovered = True


class ConfigDrivenHarnessAgent(LangGraphAgent):
    """A single generic agent class that dynamically builds a harness agent from DB config.

    Instead of writing a separate Python class for each agent, this class:
    1. Reads AgentConfigResponse (from ClickHouse)
    2. Resolves skill names → actual tool functions via tool_registry
    3. Builds a create_deep_agent() instance with the resolved tools + system_prompt
    4. Streams events using the same SSE contract as all other LangGraphAgents

    Usage:
        config = agent_config_service.get_agent_by_name("MyCustomAgent")
        agent = ConfigDrivenHarnessAgent(config)
        async for event in agent.execute_stream(task, context):
            ...
    """

    def __init__(self, agent_config: AgentConfigResponse):
        """Initialize from DB config.

        Args:
            agent_config: The agent configuration loaded from ClickHouse
        """
        _ensure_tools_discovered()

        self._agent_config = agent_config

        # Map DB model config to LangGraphAgent's AgentConfig
        model_cfg = agent_config.model_config_data or ModelConfig()
        base_config = AgentConfig(
            name=agent_config.name or "ConfigDrivenAgent",
            description=agent_config.description or "Config-driven harness agent",
            temperature=model_cfg.temperature,
            max_tokens=model_cfg.max_tokens,
        )
        super().__init__(base_config)
        self._harness_agent = None

    def get_tools(self) -> list[Callable]:
        """Resolve tool names from config to actual callable functions."""
        skill_names = self._agent_config.skills or []
        return resolve_tools(skill_names)

    def get_system_prompt(self) -> str:
        """Return the system prompt from DB config."""
        return self._agent_config.system_prompt or ""

    def _get_model(self):
        """Get LangChain model, respecting config overrides.

        If the DB config specifies a non-default model or temperature,
        creates a dedicated ChatOpenAI instance. Otherwise falls back
        to the shared singleton from get_langchain_model().
        """
        if self._model is None:
            import os

            model_cfg = self._agent_config.model_config_data or ModelConfig()
            default_model = os.getenv("OPENAI_MODEL", "gpt-4")

            # If config specifies non-default model/temperature, create a custom instance
            if model_cfg.model and model_cfg.model != default_model:
                try:
                    from langchain_openai import ChatOpenAI

                    api_key = os.getenv("OPENAI_API_KEY")
                    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
                    self._model = ChatOpenAI(
                        model=model_cfg.model,
                        api_key=api_key,
                        base_url=base_url,
                        temperature=model_cfg.temperature,
                        max_tokens=model_cfg.max_tokens if model_cfg.max_tokens > 0 else None,
                    )
                    logger.info(
                        "ConfigDrivenHarnessAgent '%s' using custom model: %s (temp=%s)",
                        self.config.name,
                        model_cfg.model,
                        model_cfg.temperature,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to create custom model for '%s', falling back: %s",
                        self.config.name,
                        e,
                    )
                    self._model = get_langchain_model()
            else:
                self._model = get_langchain_model()
        return self._model

    def _init_harness_agent(self):
        """Initialize the deep agent with full harness middleware stack."""
        if self._harness_agent is not None:
            return self._harness_agent

        model = self._get_model()
        tools = self.get_tools()
        system_prompt = self.get_system_prompt() + self.COMMON_OUTPUT_RULES
        store = get_shared_store()

        # Create the harness-enabled agent
        self._harness_agent = create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=False,
            store=store,
            name=self.config.name,
        )

        logger.info(
            "ConfigDrivenHarnessAgent '%s' initialized "
            "(tools=%d, checkpointer=False, store=InMemoryStore)",
            self.config.name,
            len(tools),
        )
        return self._harness_agent

    def _make_agent_decision_trace_event(
        self, context: dict[str, Any], tool_names: list[str]
    ) -> dict[str, Any]:
        """Create a normalized, safe decision trace for this Agent."""
        return self._make_debug_event(
            "decision_trace",
            {
                "stage": "team_agent" if context.get("team_id") else "agent",
                "title": self.config.name,
                "agent": self.config.name,
                "role": self.config.description,
                "rationale": "已接收任务并开始基于配置技能分析",
                "key_points": [f"可用工具 {len(tool_names)} 个"],
                "direction": "neutral",
                "confidence": None,
            },
        )

    async def execute_stream(
        self, task: str, context: dict[str, Any] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Execute task with streaming, emitting the standard SSE event format.

        Emits:
        - thinking events (with agent name, status)
        - content events (streamed text chunks)
        - debug events (agent_start, tool_result, agent_end)
        - visualization events (chart data from tools)
        - done event (with metadata)
        - error event (on failure)
        """
        context = context or {}

        user_id = context.get("user_id", "default")
        context_key = context.get("context_key", "")
        session_id = context.get("session_id") or self._memory.get_session_id(
            self.config.name, user_id, context_key
        )

        # Clear history if requested
        if context.get("clear_history"):
            self._memory.clear_session(session_id)

        self._memory.cleanup_expired(ttl_seconds=self.config.history_ttl_seconds)

        start_time = time.time()
        tool_calls_seen: list[str] = []
        tool_call_count = 0

        try:
            agent = self._init_harness_agent()

            # Build messages with history (reuse base class logic)
            messages = self._build_messages(task, session_id, context)

            # Save user message to history
            self._memory.add_message(
                session_id, "user", task, max_messages=self.config.max_history_messages
            )

            # Yield initial thinking event
            yield {
                "type": "thinking",
                "agent": self.config.name,
                "status": "分析中...(Harness模式)",
                "session_id": session_id,
            }

            # Emit debug: agent_start
            tool_names = []
            for t in self.get_tools():
                tname = getattr(t, "name", None) or getattr(t, "__name__", "unknown")
                tool_names.append(tname)
            yield self._make_debug_event(
                "agent_start",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "config_driven": True,
                    "input_summary": task[:200] if len(task) > 200 else task,
                    "tools_available": tool_names,
                    "parent_agent": context.get("parent_agent"),
                },
            )
            yield self._make_agent_decision_trace_event(context, tool_names)

            # Build LangGraph config
            config = {
                "recursion_limit": self.config.recursion_limit,
                "configurable": {"thread_id": session_id},
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    "langfuse_tags": [self.config.name, "harness", "config_driven"],
                },
            }

            # Add Langfuse callbacks
            callbacks = self._get_callbacks(
                session_id, user_id=user_id, context=context
            )
            if callbacks:
                config["callbacks"] = callbacks

            full_response = ""

            # Stream using astream_events v2 (same as base class)
            async for event in agent.astream_events(
                {"messages": messages}, config=config, version="v2"
            ):
                event_type = event.get("event", "")

                try:
                    if event_type == "on_tool_start":
                        tool_name = event.get("name", "unknown")
                        tool_calls_seen.append(tool_name)
                        tool_call_count += 1
                        yield {
                            "type": "thinking",
                            "agent": self.config.name,
                            "status": f"正在调用: {tool_name}",
                            "tool": tool_name,
                        }

                    elif event_type == "on_tool_end":
                        tool_name = event.get("name", "unknown")
                        tool_output = event.get("data", {}).get("output", "")
                        tool_input = event.get("data", {}).get("input", {})

                        # Emit debug: tool_result
                        result_str = str(tool_output)
                        result_summary = (
                            result_str[:500] + "..."
                            if len(result_str) > 500
                            else result_str
                        )
                        args_summary = {}
                        if isinstance(tool_input, dict):
                            args_summary = {
                                k: str(v)[:100]
                                for k, v in list(tool_input.items())[:10]
                            }
                        yield self._make_debug_event(
                            "tool_result",
                            {
                                "tool": tool_name,
                                "agent": self.config.name,
                                "args": args_summary,
                                "result_summary": result_summary,
                                "duration_ms": 0,
                            },
                        )

                        # Extract and emit visualization if present
                        viz = self._extract_visualization(tool_output)
                        if viz:
                            yield {
                                "type": "visualization",
                                "visualization": viz,
                                "agent": self.config.name,
                                "tool": tool_name,
                            }

                    elif event_type == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk:
                            content = None
                            if hasattr(chunk, "content") and chunk.content:
                                raw_content = chunk.content
                                if isinstance(raw_content, str):
                                    content = raw_content
                                elif isinstance(raw_content, list):
                                    text_parts = []
                                    for block in raw_content:
                                        if isinstance(block, dict):
                                            if block.get("type") == "text" and block.get("text"):
                                                text_parts.append(block["text"])
                                        elif isinstance(block, str):
                                            text_parts.append(block)
                                    if text_parts:
                                        content = "".join(text_parts)
                            elif isinstance(chunk, dict) and chunk.get("content"):
                                content = chunk["content"]

                            if content and isinstance(content, str):
                                full_response += content
                                yield {
                                    "type": "content",
                                    "content": content,
                                }

                    elif event_type == "on_chain_end":
                        pass  # Already streamed via on_chat_model_stream

                except Exception as e:
                    logger.debug(f"Error processing event {event_type}: {e}")

            # Save assistant response to history
            if full_response:
                response_for_history = full_response
                if len(response_for_history) > 2000:
                    response_for_history = (
                        response_for_history[:2000] + "\n...[内容已截断]"
                    )
                self._memory.add_message(
                    session_id,
                    "assistant",
                    response_for_history,
                    max_messages=self.config.max_history_messages,
                )

            # Emit debug: agent_end
            duration_ms = int((time.time() - start_time) * 1000)
            yield self._make_debug_event(
                "agent_end",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "config_driven": True,
                    "duration_ms": duration_ms,
                    "tool_calls_count": tool_call_count,
                    "success": True,
                },
            )

            # Yield done
            yield {
                "type": "done",
                "metadata": {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "config_driven": True,
                    "tool_calls": tool_calls_seen,
                    "session_id": session_id,
                    "history_length": len(self._memory.get_history(session_id)),
                },
            }

        except Exception as e:
            logger.error(f"{self.config.name} stream execution failed: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            yield self._make_debug_event(
                "agent_end",
                {
                    "agent": self.config.name,
                    "harness_mode": True,
                    "config_driven": True,
                    "duration_ms": duration_ms,
                    "tool_calls_count": tool_call_count,
                    "success": False,
                    "error": str(e),
                },
            )
            yield {
                "type": "error",
                "error": str(e),
            }


# ---------------------------------------------------------------------------
# Factory: load config from DB and return a ConfigDrivenHarnessAgent
# ---------------------------------------------------------------------------

# Cache of instantiated agents by config name
_agent_cache: dict[str, ConfigDrivenHarnessAgent] = {}


def get_config_driven_agent(agent_name: str) -> ConfigDrivenHarnessAgent | None:
    """Load agent config from DB and return a ConfigDrivenHarnessAgent.

    Uses a simple cache to avoid re-creating agents on every request.

    Args:
        agent_name: The agent name to look up in agent_configs table

    Returns:
        ConfigDrivenHarnessAgent instance, or None if config not found
    """
    if agent_name in _agent_cache:
        return _agent_cache[agent_name]

    try:
        from stock_datasource.services.agent_config_service import get_agent_config_service

        service = get_agent_config_service()

        # Search by name across all agents (system + public)
        agents = service.list_agents(user_id="system", include_public=True)
        config = None
        for a in agents:
            if a.name == agent_name:
                config = a
                break

        if config is None:
            logger.debug("No DB config found for agent '%s'", agent_name)
            return None

        agent = ConfigDrivenHarnessAgent(config)
        _agent_cache[agent_name] = agent
        logger.info(
            "Created ConfigDrivenHarnessAgent for '%s' (skills=%s)",
            agent_name,
            config.skills,
        )
        return agent
    except Exception as e:
        logger.warning("Failed to load config-driven agent '%s': %s", agent_name, e)
        return None


def clear_agent_cache() -> None:
    """Clear the cached agent instances (useful after config updates)."""
    _agent_cache.clear()
