"""Agent registrations — DEPRECATED.

Agent configurations are now stored in ClickHouse (agent_configs table)
and managed via the /api/agents/ REST API + Agent管理 UI.

This file is kept as a no-op stub so that existing call sites
(e.g. wechat_bridge) don't break.
"""

import logging

logger = logging.getLogger(__name__)

_registered = False


def register_all_agents() -> int:
    """No-op. Agent configs now live in the database.

    Previously this function registered 17 hardcoded AgentDescriptors.
    Now all agent definitions are in ClickHouse `agent_configs` table
    (user_id='system' for built-in agents).

    Safe to call multiple times; always returns 0.
    """
    global _registered
    if _registered:
        return 0
    _registered = True
    logger.info(
        "agent_registrations: skipped (agents now managed via database). "
        "Use /api/agents/ or Agent管理 UI."
    )
    return 0
