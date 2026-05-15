"""Workflow agent — DEPRECATED.

Replaced by the Agent Orchestration system:
- Agent configs: /api/agents/ (ClickHouse agent_configs table)
- Pipeline orchestration: /api/orchestrations/ (orchestration_engine.py)

This stub is kept so chat_agent.py imports don't break.
"""

import logging

logger = logging.getLogger(__name__)


class WorkflowAgent:
    """Deprecated stub. Use OrchestrationEngine instead."""

    def __init__(self, *args, **kwargs):
        logger.warning("WorkflowAgent is deprecated. Use Agent Orchestration (/orchestration) instead.")

    async def execute(self, *args, **kwargs):
        return {"content": "[此功能已迁移到Agent编排系统，请使用新的编排页面]"}


def create_workflow_agent(workflow=None):
    """Deprecated stub."""
    logger.warning("create_workflow_agent is deprecated. Use OrchestrationEngine.")
    return WorkflowAgent()
