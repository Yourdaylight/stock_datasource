import pytest

from datetime import datetime

from stock_datasource.agents.config_driven_harness_agent import ConfigDrivenHarnessAgent
from stock_datasource.agents.orchestrator import OrchestratorAgent
from stock_datasource.models.agent_config import AgentConfigResponse, AgentStatus, ModelConfig
from stock_datasource.modules.chat.schemas import SendMessageRequest


def test_send_message_request_accepts_optional_team_fields():
    request = SendMessageRequest(
        session_id="session-1",
        content="分析贵州茅台",
        team_id="team-1",
        team_name="价值投研团队",
    )

    assert request.team_id == "team-1"
    assert request.team_name == "价值投研团队"


def test_send_message_request_team_fields_are_optional():
    request = SendMessageRequest(session_id="session-1", content="分析贵州茅台")

    assert request.team_id is None
    assert request.team_name is None


class TraceOnlyOrchestrator(OrchestratorAgent):
    def _list_available_agents(self):
        return [
            {"name": "ReportAgent", "description": "财报分析"},
            {"name": "MarketAgent", "description": "行情分析"},
        ]

    async def _classify_with_llm(self, query, context=None):
        return "financial_report", "ReportAgent", "用户需要财报和估值分析"


@pytest.mark.asyncio
async def test_orchestrator_emits_normalized_decision_trace():
    orchestrator = TraceOnlyOrchestrator()
    events = []

    async for event in orchestrator.execute_stream(
        "分析贵州茅台", {"team_id": "team-1", "team_name": "价值投研团队"}
    ):
        events.append(event)
        if event.get("debug_type") == "decision_trace":
            break

    trace_events = [event for event in events if event.get("debug_type") == "decision_trace"]
    assert len(trace_events) == 1
    trace = trace_events[0]
    assert trace["agent"] == "OrchestratorAgent"
    assert trace["data"]["stage"] == "orchestrator"
    assert trace["data"]["intent"] == "financial_report"
    assert trace["data"]["selected_agent"] == "ReportAgent"
    assert trace["data"]["selected_team"] == "价值投研团队"
    assert trace["data"]["rationale"] == "用户需要财报和估值分析"
    assert trace["data"]["available_agents"] == ["ReportAgent", "MarketAgent"]


def make_agent_config() -> AgentConfigResponse:
    now = datetime.now()
    return AgentConfigResponse(
        id="agent-1",
        user_id="system",
        name="财报分析师",
        description="负责财报和估值判断",
        avatar="",
        system_prompt="分析财报",
        skills=[],
        user_skills=[],
        model_config_data=ModelConfig(),
        tags=[],
        is_public=True,
        status=AgentStatus.active,
        version=1,
        created_at=now,
        updated_at=now,
    )


def test_config_driven_agent_builds_normalized_decision_trace_event():
    agent = ConfigDrivenHarnessAgent(make_agent_config())

    event = agent._make_agent_decision_trace_event(
        context={"team_id": "team-1"},
        tool_names=["get_financial_report", "get_stock_valuation"],
    )

    assert event["type"] == "debug"
    assert event["debug_type"] == "decision_trace"
    assert event["agent"] == "财报分析师"
    assert event["data"]["stage"] == "team_agent"
    assert event["data"]["title"] == "财报分析师"
    assert event["data"]["agent"] == "财报分析师"
    assert event["data"]["role"] == "负责财报和估值判断"
    assert event["data"]["direction"] == "neutral"
    assert event["data"]["key_points"] == ["可用工具 2 个"]


def test_orchestrator_keyword_fallback_routes_market_decline_query():
    orchestrator = OrchestratorAgent()
    agents = [
        {"name": "OverviewAgent", "description": "市场概览Agent"},
        {"name": "ChatAgent", "description": "通用对话助手"},
    ]

    result = orchestrator._classify_with_rules("分析今日下跌的原因", agents)

    assert result == (
        "market_overview",
        "OverviewAgent",
        "根据关键词匹配到市场概览分析",
    )


def test_orchestrator_builds_local_market_overview_response():
    orchestrator = OrchestratorAgent()

    response = orchestrator._build_local_market_overview_response("## A股市场概况\n- 下跌家数: 3000")

    assert "## A股市场概况" in response
    assert "下跌家数: 3000" in response
    assert "可能原因" in response


def test_orchestrator_builds_team_summary_decision_trace_event():
    orchestrator = OrchestratorAgent()

    event = orchestrator._make_team_summary_trace_event(
        context={"team_id": "team-1", "team_name": "价值投研团队"},
        agent_name="财报分析师",
    )

    assert event["type"] == "debug"
    assert event["debug_type"] == "decision_trace"
    assert event["agent"] == "OrchestratorAgent"
    assert event["data"]["stage"] == "team_summary"
    assert event["data"]["title"] == "团队汇总"
    assert event["data"]["selected_team"] == "价值投研团队"
    assert event["data"]["selected_agent"] == "财报分析师"
    assert event["data"]["rationale"] == "已完成团队模式分析，最终结论见回复内容"
    assert "signal" not in event["data"]
