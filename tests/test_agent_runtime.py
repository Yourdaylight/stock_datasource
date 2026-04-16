"""Tests for Agent Registry, Execution Planner, and Agent Runtime.

Covers:
- AgentRegistry: registration, discovery, instance lifecycle
- ExecutionPlanner: config data and agent expansion
- AgentRuntime: feature flag, SSE adapter, supervisor build
"""

import os
import time
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class FakeAgentConfig:
    def __init__(self, name, description=""):
        self.name = name
        self.description = description


class FakeLangGraphAgent:
    COMMON_OUTPUT_RULES = "\n## Test output rules"

    def __init__(self, name="FakeAgent", description="Fake"):
        self.config = FakeAgentConfig(name, description)

    def get_tools(self):
        return []

    def get_system_prompt(self):
        return "You are a fake agent."


# ===========================================================================
# AgentRegistry Tests
# ===========================================================================


class TestAgentRegistry:
    def _make_registry(self):
        from stock_datasource.services.agent_registry import AgentRegistry

        return AgentRegistry()

    def _make_descriptor(self, name="TestAgent", enabled=True, role=None, intents=None):
        from stock_datasource.services.agent_registry import (
            AgentDescriptor,
            AgentRole,
            CapabilityDescriptor,
        )

        return AgentDescriptor(
            name=name,
            description=f"Description of {name}",
            agent_class=type(
                name,
                (FakeLangGraphAgent,),
                {"__init__": lambda self: FakeLangGraphAgent.__init__(self, name)},
            ),
            role=role or AgentRole.AGENT,
            capability=CapabilityDescriptor(intents=intents or []),
            enabled=enabled,
        )

    def test_register_and_list(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("AgentA"))
        reg.register(self._make_descriptor("AgentB"))
        assert reg.count == 2
        assert "AgentA" in reg.names
        assert len(reg.list_available()) == 2

    def test_register_overwrite(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("AgentA"))
        d2 = self._make_descriptor("AgentA")
        d2.description = "Updated"
        reg.register(d2)
        assert reg.count == 1
        assert reg.get_descriptor("AgentA").description == "Updated"

    def test_unregister(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("AgentA"))
        assert reg.unregister("AgentA") is True
        assert reg.unregister("AgentA") is False
        assert reg.count == 0

    def test_enabled_filter(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("Enabled", enabled=True))
        reg.register(self._make_descriptor("Disabled", enabled=False))
        assert len(reg.list_descriptors(enabled_only=True)) == 1
        assert len(reg.list_descriptors(enabled_only=False)) == 2

    def test_role_filter(self):
        from stock_datasource.services.agent_registry import AgentRole

        reg = self._make_registry()
        reg.register(self._make_descriptor("A", role=AgentRole.AGENT))
        reg.register(self._make_descriptor("B", role=AgentRole.SUB_AGENT))
        reg.register(self._make_descriptor("C", role=AgentRole.ADAPTER))
        assert len(reg.list_descriptors(role=AgentRole.AGENT)) == 1

    def test_find_by_intent(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("MarketAgent", intents=["market_analysis"]))
        reg.register(self._make_descriptor("ReportAgent", intents=["financial_report"]))
        found = reg.find_by_intent("market_analysis")
        assert len(found) == 1
        assert found[0].name == "MarketAgent"
        assert len(reg.find_by_intent("nonexistent")) == 0

    def test_get_agent_lazy_instantiation(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("LazyAgent"))
        a1 = reg.get_agent("LazyAgent")
        assert a1 is not None
        a2 = reg.get_agent("LazyAgent")
        assert a2 is a1

    def test_get_agent_disabled(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("Disabled", enabled=False))
        assert reg.get_agent("Disabled") is None

    def test_get_agent_unknown(self):
        reg = self._make_registry()
        assert reg.get_agent("NonExistent") is None

    def test_reset_instance(self):
        reg = self._make_registry()
        reg.register(self._make_descriptor("R"))
        a1 = reg.get_agent("R")
        reg.reset_instance("R")
        a2 = reg.get_agent("R")
        assert a1 is not a2

    def test_priority_ordering(self):
        reg = self._make_registry()
        d1 = self._make_descriptor("Lo")
        d1.priority = 1
        d2 = self._make_descriptor("Hi")
        d2.priority = 10
        reg.register(d1)
        reg.register(d2)
        assert reg.list_descriptors()[0].name == "Hi"

    def test_register_many(self):
        reg = self._make_registry()
        reg.register_many([self._make_descriptor(f"A{i}") for i in range(5)])
        assert reg.count == 5


# ===========================================================================
# ExecutionPlanner Tests
# ===========================================================================


class TestExecutionPlanner:
    def _make_planner(self):
        from stock_datasource.services.execution_planner import ExecutionPlanner

        return ExecutionPlanner()

    def test_expand_single_agent(self):
        p = self._make_planner()
        assert p.expand_agents(
            primary="MarketAgent", available_agents={"MarketAgent"}
        ) == ["MarketAgent"]

    def test_expand_none(self):
        p = self._make_planner()
        assert p.expand_agents(primary=None) == []

    def test_expand_market_with_a_shares(self):
        p = self._make_planner()
        agents = p.expand_agents(
            primary="MarketAgent",
            stock_codes=["600519.SH"],
            query="分析600519",
            available_agents={"MarketAgent", "ReportAgent", "HKReportAgent"},
        )
        assert "MarketAgent" in agents and "ReportAgent" in agents

    def test_expand_market_with_hk(self):
        p = self._make_planner()
        agents = p.expand_agents(
            primary="MarketAgent",
            stock_codes=["00700.HK"],
            available_agents={"MarketAgent", "HKReportAgent"},
        )
        assert "HKReportAgent" in agents

    def test_reverse_expansion_hk_tech(self):
        p = self._make_planner()
        agents = p.expand_agents(
            primary="HKReportAgent",
            stock_codes=["00700.HK"],
            query="腾讯技术面",
            available_agents={"MarketAgent", "HKReportAgent"},
        )
        assert "MarketAgent" in agents

    def test_reverse_expansion_report_tech(self):
        p = self._make_planner()
        agents = p.expand_agents(
            primary="ReportAgent",
            stock_codes=["600519.SH"],
            query="茅台技术走势",
            available_agents={"MarketAgent", "ReportAgent"},
        )
        assert "MarketAgent" in agents

    def test_concurrent_check(self):
        p = self._make_planner()
        assert p.can_run_concurrently(["MarketAgent", "ReportAgent"]) is True
        assert p.can_run_concurrently(["MarketAgent", "ScreenerAgent"]) is False

    def test_handoff_targets(self):
        p = self._make_planner()
        assert "ReportAgent" in p.get_handoff_targets("MarketAgent")
        assert p.get_handoff_targets("UnknownAgent") == []


class TestEnums:
    def test_execution_mode_values(self):
        from stock_datasource.services.execution_planner import ExecutionMode

        assert ExecutionMode.ROUTE_ONLY.value == "route_only"
        assert ExecutionMode.SUPERVISOR.value == "supervisor"

    def test_node_status_values(self):
        from stock_datasource.services.execution_planner import NodeStatus

        assert NodeStatus.PENDING.value == "pending"
        assert NodeStatus.TIMED_OUT.value == "timed_out"


# ===========================================================================
# AgentRuntime Tests
# ===========================================================================


class TestAgentRuntime:
    def test_feature_flag_default_off(self):
        from stock_datasource.services.agent_runtime import is_runtime_enabled

        os.environ.pop("AGENT_RUNTIME_ENABLED", None)
        assert is_runtime_enabled() is False

    def test_feature_flag_on(self):
        from stock_datasource.services.agent_runtime import is_runtime_enabled

        os.environ["AGENT_RUNTIME_ENABLED"] = "true"
        try:
            assert is_runtime_enabled() is True
        finally:
            del os.environ["AGENT_RUNTIME_ENABLED"]

    def test_feature_flag_variants(self):
        from stock_datasource.services.agent_runtime import is_runtime_enabled

        for val in ("1", "yes", "True", "TRUE"):
            os.environ["AGENT_RUNTIME_ENABLED"] = val
            assert is_runtime_enabled() is True, f"Expected True for {val}"
        for val in ("false", "0", "no", ""):
            os.environ["AGENT_RUNTIME_ENABLED"] = val
            assert is_runtime_enabled() is False, f"Expected False for {val}"
        os.environ.pop("AGENT_RUNTIME_ENABLED", None)

    def test_sse_adapter_content_stream(self):
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        # Simulate on_chat_model_stream with a mock chunk
        chunk = MagicMock()
        chunk.content = "Hello world"
        event = {"event": "on_chat_model_stream", "data": {"chunk": chunk}}
        sse = adapt_langgraph_event_to_sse(event)
        assert sse is not None
        assert sse["type"] == "content"
        assert sse["content"] == "Hello world"

    def test_sse_adapter_tool_start(self):
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        event = {
            "event": "on_tool_start",
            "name": "get_stock_data",
            "data": {"input": {"code": "600519"}},
            "tags": ["MarketAgent"],
        }
        sse = adapt_langgraph_event_to_sse(event)
        assert sse["type"] == "tool"
        assert sse["tool"] == "get_stock_data"
        assert sse["args"]["code"] == "600519"

    def test_sse_adapter_tool_end(self):
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        event = {
            "event": "on_tool_end",
            "name": "get_stock_data",
            "data": {"output": "result data"},
            "tags": ["MarketAgent"],
        }
        sse = adapt_langgraph_event_to_sse(event)
        assert sse["type"] == "debug"
        assert sse["debug_type"] == "tool_result"

    def test_sse_adapter_skip_internal(self):
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        for etype in ("on_chain_start", "on_chain_end", "on_chat_model_start"):
            event = {"event": etype, "data": {}, "tags": []}
            assert adapt_langgraph_event_to_sse(event) is None

    def test_sse_adapter_empty_chunk(self):
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        chunk = MagicMock()
        chunk.content = ""
        event = {"event": "on_chat_model_stream", "data": {"chunk": chunk}}
        assert adapt_langgraph_event_to_sse(event) is None

    def test_sse_adapter_list_content(self):
        """Handle thinking model content (list of blocks)."""
        from stock_datasource.services.agent_runtime import adapt_langgraph_event_to_sse

        chunk = MagicMock()
        chunk.content = [
            {"type": "thinking", "thinking": "reasoning..."},
            {"type": "text", "text": "actual answer"},
        ]
        event = {"event": "on_chat_model_stream", "data": {"chunk": chunk}}
        sse = adapt_langgraph_event_to_sse(event)
        assert sse is not None
        assert sse["type"] == "content"
        assert sse["content"] == "actual answer"

    def test_runtime_init(self):
        """AgentRuntime can be created with an empty registry."""
        from stock_datasource.services.agent_registry import AgentRegistry
        from stock_datasource.services.agent_runtime import AgentRuntime

        reg = AgentRegistry()
        rt = AgentRuntime(registry=reg)
        assert rt.registry is reg
        assert rt._supervisor is None

    def test_runtime_reset(self):
        from stock_datasource.services.agent_registry import AgentRegistry
        from stock_datasource.services.agent_runtime import AgentRuntime

        rt = AgentRuntime(registry=AgentRegistry())
        rt._sub_agents["test"] = "dummy"
        rt.reset()
        assert rt._supervisor is None
        assert len(rt._sub_agents) == 0

    def test_runtime_agent_names_empty(self):
        from stock_datasource.services.agent_registry import AgentRegistry
        from stock_datasource.services.agent_runtime import AgentRuntime

        rt = AgentRuntime(registry=AgentRegistry())
        assert rt.agent_names == set()

    def test_supervisor_prompt_generation(self):
        """Test that supervisor prompt includes agent descriptions."""
        from stock_datasource.services.agent_registry import (
            AgentDescriptor,
            AgentRegistry,
            CapabilityDescriptor,
        )
        from stock_datasource.services.agent_runtime import AgentRuntime

        reg = AgentRegistry()
        reg.register(
            AgentDescriptor(
                name="MarketAgent",
                description="A股行情分析",
                agent_class=FakeLangGraphAgent,
                capability=CapabilityDescriptor(markets=["A", "HK"]),
            )
        )
        rt = AgentRuntime(registry=reg)
        prompt = rt._get_supervisor_prompt()
        assert "MarketAgent" in prompt
        assert "A股行情分析" in prompt
        assert "A, HK" in prompt


# ===========================================================================
# SessionMemoryService Tests
# ===========================================================================


class TestSessionMemoryService:
    def _make_service(self):
        from stock_datasource.services.session_memory_service import (
            SessionMemoryService,
        )

        return SessionMemoryService()

    def test_session_lifecycle(self):
        svc = self._make_service()
        sid = svc.make_session_id("TestAgent", "user1")
        svc.touch_session(sid, "user1")
        assert svc.active_session_count == 1
        svc.clear_session(sid)
        assert svc.active_session_count == 0

    def test_add_and_get_history(self):
        svc = self._make_service()
        svc.add_message("s1", "user", "Hello")
        svc.add_message("s1", "assistant", "Hi")
        h = svc.get_history("s1")
        assert len(h) == 2
        assert h[0]["role"] == "user"

    def test_history_max_messages(self):
        svc = self._make_service()
        for i in range(40):
            svc.add_message("s1", "user", f"msg {i}", max_messages=10)
        h = svc.get_history("s1")
        assert len(h) <= 10

    def test_scoped_history(self):
        svc = self._make_service()
        for i in range(20):
            svc.add_message("s1", "user", f"msg {i}")
        h = svc.get_scoped_history("s1", max_messages=3)
        assert len(h) == 3

    def test_cache_ttl(self):
        svc = self._make_service()
        svc.set_cache("s1", "key", "val", ttl=1)
        assert svc.get_cache("s1", "key") == "val"
        time.sleep(1.1)
        assert svc.get_cache("s1", "key") is None

    def test_preferences(self):
        svc = self._make_service()
        svc.save_preference("u1", "theme", "dark")
        assert svc.get_preference("u1", "theme") == "dark"
        prefs = svc.list_preferences("u1")
        assert prefs["theme"] == "dark"

    def test_watchlist(self):
        svc = self._make_service()
        assert svc.add_to_watchlist("u1", "600519.SH") is True
        assert svc.add_to_watchlist("u1", "600519.SH") is False
        assert svc.get_watchlist("u1") == ["600519.SH"]
        assert svc.remove_from_watchlist("u1", "600519.SH") is True
        assert svc.get_watchlist("u1") == []

    def test_stats_counters(self):
        """Task 5.2: Verify observability counters."""
        svc = self._make_service()
        svc.record_stat("custom_counter", 5)
        assert svc._stats["custom_counter"] == 5
        svc.record_stat("custom_counter", 3)
        assert svc._stats["custom_counter"] == 8

    def test_stats_property(self):
        """Task 5.2: Verify stats snapshot."""
        svc = self._make_service()
        svc.touch_session("s1")
        svc.set_cache("s1", "k1", "v1")
        stats = svc.stats
        assert stats["active_sessions"] == 1
        assert stats["total_cached_keys"] == 1
        assert "cache_hits" in stats

    def test_user_isolation(self):
        """Task 2.3: Verify user isolation for preferences and watchlists."""
        svc = self._make_service()
        svc.save_preference("u1", "theme", "dark")
        svc.save_preference("u2", "theme", "light")
        assert svc.get_preference("u1", "theme") == "dark"
        assert svc.get_preference("u2", "theme") == "light"
        svc.add_to_watchlist("u1", "600519.SH")
        svc.add_to_watchlist("u2", "000001.SZ")
        assert svc.get_watchlist("u1") == ["600519.SH"]
        assert svc.get_watchlist("u2") == ["000001.SZ"]


# ===========================================================================
# SubAgentEnvelope Tests (Task 4.3)
# ===========================================================================


class TestSubAgentEnvelope:
    def test_envelope_creation(self):
        from stock_datasource.services.session_memory_service import SubAgentEnvelope

        env = SubAgentEnvelope(
            agent_name="MarketAgent", session_id="s1", query="分析600519"
        )
        assert env.agent_name == "MarketAgent"
        assert env.success is True
        assert env.response == ""

    def test_envelope_fill_response(self):
        from stock_datasource.services.session_memory_service import SubAgentEnvelope

        env = SubAgentEnvelope(agent_name="Test", session_id="s1")
        env.response = "Analysis complete"
        env.success = True
        env.metadata = {"duration_ms": 100}
        assert env.response == "Analysis complete"
        assert env.metadata["duration_ms"] == 100

    def test_envelope_defaults(self):
        from stock_datasource.services.session_memory_service import SubAgentEnvelope

        env = SubAgentEnvelope(agent_name="A", session_id="s")
        assert env.user_id == "default"
        assert env.scoped_history == []
        assert env.shared_state_keys == []
        assert env.tool_calls == []


# ===========================================================================
# AgentRuntime Stats Tests (Task 5.2)
# ===========================================================================


class TestAgentRuntimeStats:
    def test_runtime_stats_initial(self):
        from stock_datasource.services.agent_registry import AgentRegistry
        from stock_datasource.services.agent_runtime import AgentRuntime

        rt = AgentRuntime(registry=AgentRegistry())
        stats = rt.stats
        assert stats["total_invocations"] == 0
        assert stats["concurrent_failures"] == 0
        assert stats["failure_rate"] == 0.0
        assert stats["cold_start_ms"] is None

    def test_runtime_stats_after_reset(self):
        from stock_datasource.services.agent_registry import AgentRegistry
        from stock_datasource.services.agent_runtime import AgentRuntime

        rt = AgentRuntime(registry=AgentRegistry())
        rt._cold_start_ms = 500.0
        rt.reset()
        assert rt.stats["cold_start_ms"] is None


# ===========================================================================
# SkillRegistry Tests
# ===========================================================================


class TestSkillRegistry:
    def _make_registry(self):
        from stock_datasource.services.skill_registry import SkillRegistry

        return SkillRegistry()

    def test_register_and_list(self):
        from stock_datasource.services.skill_registry import SkillDescriptor

        reg = self._make_registry()
        reg.register(SkillDescriptor(name="s1", category="market", source="builtin"))
        reg.register(SkillDescriptor(name="s2", category="report", source="mcp"))
        assert reg.count == 2
        assert "s1" in reg.names

    def test_find_by_trigger(self):
        from stock_datasource.services.skill_registry import SkillDescriptor

        reg = self._make_registry()
        reg.register(SkillDescriptor(name="s1", triggers=["stock_query"]))
        found = reg.find_by_trigger("stock_query")
        assert len(found) == 1

    def test_catalog(self):
        from stock_datasource.services.skill_registry import SkillDescriptor

        reg = self._make_registry()
        reg.register(SkillDescriptor(name="s1", description="test", category="c"))
        cat = reg.to_catalog()
        assert len(cat) == 1
        assert cat[0]["name"] == "s1"


# ===========================================================================
# Singletons
# ===========================================================================


class TestSingletons:
    def test_agent_registry_singleton(self):
        from stock_datasource.services.agent_registry import get_agent_registry

        assert get_agent_registry() is get_agent_registry()

    def test_execution_planner_singleton(self):
        from stock_datasource.services.execution_planner import get_execution_planner

        assert get_execution_planner() is get_execution_planner()

    def test_agent_runtime_singleton(self):
        from stock_datasource.services.agent_runtime import get_agent_runtime

        assert get_agent_runtime() is get_agent_runtime()

    def test_session_memory_singleton(self):
        from stock_datasource.services.session_memory_service import (
            get_session_memory_service,
        )

        assert get_session_memory_service() is get_session_memory_service()

    def test_skill_registry_singleton(self):
        from stock_datasource.services.skill_registry import get_skill_registry

        assert get_skill_registry() is get_skill_registry()
