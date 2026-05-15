"""Workflow generator agent — DEPRECATED.

Replaced by Agent Management UI where users directly configure agents
with prompts + skills. No more auto-generation of workflow templates.

This stub is kept so workflow_routes.py imports don't break (routes are disabled).
"""

import logging

logger = logging.getLogger(__name__)


class WorkflowGeneratorAgent:
    """Deprecated stub."""

    async def generate(self, *args, **kwargs):
        return None


def get_workflow_generator():
    """Deprecated stub."""
    return WorkflowGeneratorAgent()
