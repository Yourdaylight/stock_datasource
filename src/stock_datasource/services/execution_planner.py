"""Execution Planner: Agent routing configuration and metadata.

With LangGraph Supervisor handling the actual orchestration logic
(routing, handoff, state management), this module is simplified to:

1. **Configuration data** – concurrent agent groups, handoff maps
2. **Metadata models** – ExecutionMode, NodeStatus for observability
3. **Utility functions** – agent expansion logic used by the supervisor prompt

The heavy lifting (parallel execution, sequential handoff, state flow)
is now done by LangGraph natively via ``create_supervisor`` + ``Command``.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums (kept for observability / event metadata)
# ---------------------------------------------------------------------------

class ExecutionMode(str, Enum):
    """Supported execution modes (for metadata / logging)."""
    ROUTE_ONLY = "route_only"
    PARALLEL_AGGREGATE = "parallel_aggregate"
    SEQUENTIAL_HANDOFF = "sequential_handoff"
    WORKFLOW_DRIVEN = "workflow_driven"
    DISCUSSION_ARENA = "discussion_arena"
    SUPERVISOR = "supervisor"  # New: LangGraph Supervisor mode


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


# ---------------------------------------------------------------------------
# Concurrency & handoff configuration
# ---------------------------------------------------------------------------

# Groups of agents that are safe to run concurrently
CONCURRENT_AGENT_GROUPS: List[Set[str]] = [
    {"MarketAgent", "ReportAgent"},
    {"IndexAgent", "EtfAgent"},
    {"OverviewAgent", "TopListAgent"},
    {"MarketAgent", "HKReportAgent"},
    {"KnowledgeAgent", "MarketAgent"},
    {"KnowledgeAgent", "ReportAgent"},
]

# Agent → possible handoff targets
AGENT_HANDOFF_MAP: Dict[str, List[str]] = {
    "MarketAgent": ["ReportAgent", "HKReportAgent", "BacktestAgent"],
    "ScreenerAgent": ["MarketAgent", "ReportAgent"],
    "ReportAgent": ["BacktestAgent", "MarketAgent", "HKReportAgent"],
    "HKReportAgent": ["MarketAgent", "ReportAgent"],
    "OverviewAgent": ["MarketAgent", "IndexAgent"],
}


# ---------------------------------------------------------------------------
# Utility: Agent expansion (used by supervisor prompt building)
# ---------------------------------------------------------------------------

def expand_agent_list(
    primary: Optional[str],
    stock_codes: List[str],
    query: str,
    available: Set[str],
) -> List[str]:
    """Expand a primary agent into a (possibly multi-agent) list.

    This logic is used to inform the Supervisor's prompt about which
    agents are likely needed, but the Supervisor LLM makes the final
    routing decision.
    """
    if not primary:
        return []

    plan = [primary]
    hk_codes = [c for c in stock_codes if c.upper().endswith(".HK")]
    a_codes = [c for c in stock_codes if not c.upper().endswith(".HK")]

    query_lower = query.lower()
    tech_keywords = {
        "技术", "技术面", "技术指标", "k线", "kline", "走势",
        "macd", "rsi", "kdj", "均线", "趋势",
    }
    wants_tech = any(kw in query_lower for kw in tech_keywords)

    if stock_codes and primary == "MarketAgent":
        if hk_codes and "HKReportAgent" in available:
            plan.append("HKReportAgent")
        if a_codes and "ReportAgent" in available:
            plan.append("ReportAgent")

    if stock_codes and primary == "HKReportAgent" and wants_tech:
        if "MarketAgent" in available and "MarketAgent" not in plan:
            plan.insert(0, "MarketAgent")

    if stock_codes and primary == "ReportAgent" and wants_tech:
        if "MarketAgent" in available and "MarketAgent" not in plan:
            plan.insert(0, "MarketAgent")

    return plan


def can_run_concurrently(agents: List[str]) -> bool:
    """Check if agents can run concurrently."""
    agent_set = set(agents)
    return any(agent_set.issubset(group) for group in CONCURRENT_AGENT_GROUPS)


def get_handoff_targets(agent_name: str) -> List[str]:
    """Get possible handoff targets for an agent."""
    return AGENT_HANDOFF_MAP.get(agent_name, [])


# ---------------------------------------------------------------------------
# Singleton accessor (kept for backward compatibility)
# ---------------------------------------------------------------------------

class ExecutionPlanner:
    """Lightweight planner providing config data and agent expansion.

    The actual execution logic is handled by LangGraph Supervisor.
    This class primarily provides configuration and utility methods
    for backward compatibility and observability.
    """

    def __init__(
        self,
        concurrent_groups: Optional[List[Set[str]]] = None,
        handoff_map: Optional[Dict[str, List[str]]] = None,
    ):
        self.concurrent_groups = concurrent_groups or CONCURRENT_AGENT_GROUPS
        self.handoff_map = handoff_map or AGENT_HANDOFF_MAP

    def expand_agents(
        self,
        primary: Optional[str],
        stock_codes: List[str] = None,
        query: str = "",
        available_agents: Set[str] = None,
    ) -> List[str]:
        return expand_agent_list(
            primary, stock_codes or [], query, available_agents or set()
        )

    def can_run_concurrently(self, agents: List[str]) -> bool:
        return can_run_concurrently(agents)

    def get_handoff_targets(self, agent_name: str) -> List[str]:
        return get_handoff_targets(agent_name)


_planner: Optional[ExecutionPlanner] = None


def get_execution_planner() -> ExecutionPlanner:
    global _planner
    if _planner is None:
        _planner = ExecutionPlanner()
    return _planner
