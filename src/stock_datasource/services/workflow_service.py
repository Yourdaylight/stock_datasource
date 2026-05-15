"""AI工作流服务 — DEPRECATED.

已被 Agent 编排系统替代:
- Agent配置: services/agent_config_service.py
- Pipeline编排: services/orchestration_service.py + orchestration_engine.py
- 前端: /orchestration (Vue Flow DAG编辑器)

保留空壳以免 chat_agent.py 等引用报错。
"""

import logging

logger = logging.getLogger(__name__)


class WorkflowService:
    """Deprecated. Use OrchestrationService instead."""

    def __init__(self):
        self._templates = []

    def get_workflow(self, workflow_id: str):
        return None

    def list_workflows(self, user_id: str = None):
        return []

    def get_templates(self):
        return []

    def get_available_tools(self):
        return []


_workflow_service: WorkflowService | None = None


def get_workflow_service() -> WorkflowService:
    global _workflow_service
    if _workflow_service is None:
        _workflow_service = WorkflowService()
    return _workflow_service
