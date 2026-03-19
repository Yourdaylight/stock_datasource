"""Memory Agent for user context management using LangGraph/DeepAgents.

Task 2.3: Delegates all storage to ``SessionMemoryService`` so that
preferences and watchlists are properly isolated by ``user_id``.
The old module-level ``_memory_store`` is removed.
"""

from typing import Any, Dict, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions (LLM-callable)
# ---------------------------------------------------------------------------
# A ``_user_id`` context variable is injected by the agent before each run
# so that tool functions know *whose* data they are operating on.

_current_user_id: str = "default"


def _svc():
    from stock_datasource.services.session_memory_service import get_session_memory_service
    return get_session_memory_service()


def save_user_preference(key: str, value: str, category: str = "style") -> str:
    """保存用户偏好设置。

    Args:
        key: 偏好键名，如 risk_level, favorite_industries
        value: 偏好值
        category: 偏好类别 - risk(风险偏好), industry(行业偏好),
                  style(投资风格), notification(通知设置)

    Returns:
        保存结果消息
    """
    _svc().save_preference(_current_user_id, key, value, category=category)
    return f"已保存偏好设置: {key} = {value} (类别: {category})"


def get_user_preference(key: str) -> str:
    """获取用户偏好设置。

    Args:
        key: 偏好键名

    Returns:
        偏好值或未找到提示
    """
    val = _svc().get_preference(_current_user_id, key)
    if val is not None:
        return f"{key} = {val}"
    return f"未找到偏好设置: {key}"


def manage_watchlist(action: str, code: str = "", group: str = "default") -> str:
    """管理用户自选股。

    Args:
        action: 操作类型 - add(添加), remove(删除), list(列出), clear(清空)
        code: 股票代码（add/remove时需要）
        group: 自选股分组名称

    Returns:
        操作结果消息
    """
    svc = _svc()
    uid = _current_user_id
    if action == "add":
        if code and svc.add_to_watchlist(uid, code, group):
            return f"已将 {code} 添加到自选股分组 [{group}]"
        return f"{code} 已在自选股中"
    if action == "remove":
        if svc.remove_from_watchlist(uid, code, group):
            return f"已将 {code} 从自选股分组 [{group}] 移除"
        return f"{code} 不在自选股中"
    if action == "list":
        wl = svc.get_watchlist(uid, group)
        if wl:
            return f"自选股分组 [{group}]: {', '.join(wl)}"
        return f"自选股分组 [{group}] 为空"
    if action == "clear":
        # Remove all items one by one
        for c in list(svc.get_watchlist(uid, group)):
            svc.remove_from_watchlist(uid, c, group)
        return f"已清空自选股分组 [{group}]"
    return f"未知操作: {action}"


def get_memory_summary() -> str:
    """获取用户记忆摘要。

    Returns:
        用户偏好和自选股的摘要信息
    """
    svc = _svc()
    uid = _current_user_id
    lines = ["## 用户记忆摘要\n"]

    prefs = svc.list_preferences(uid)
    if prefs:
        lines.append("### 偏好设置")
        for key, val in prefs.items():
            lines.append(f"- {key}: {val}")
        lines.append("")
    else:
        lines.append("### 偏好设置\n暂无设置\n")

    wl = svc.get_watchlist(uid)
    if wl:
        lines.append("### 自选股")
        lines.append(f"- [default]: {', '.join(wl)}")
        lines.append("")
    else:
        lines.append("### 自选股\n暂无自选股\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class MemoryAgent(LangGraphAgent):
    """Memory Agent – manages user preferences and watchlists.

    Before each execution, ``_current_user_id`` is set so that tool
    functions operate on the correct user's data.
    """

    def __init__(self):
        config = AgentConfig(
            name="MemoryAgent",
            description="负责用户记忆管理，包括偏好设置、自选股管理等",
        )
        super().__init__(config)

    def get_tools(self) -> List[Callable]:
        return [save_user_preference, get_user_preference, manage_watchlist, get_memory_summary]

    def get_system_prompt(self) -> str:
        return """你是用户记忆管理助手，帮助用户管理投资偏好和自选股。

## 可用工具
- save_user_preference: 保存用户偏好（风险偏好、行业偏好等）
- get_user_preference: 获取用户偏好
- manage_watchlist: 管理自选股（添加/删除/列出/清空）
- get_memory_summary: 获取用户记忆摘要

## 工作原则
- 准确理解用户意图
- 确认操作后执行
- 给出操作结果反馈
"""

    async def execute(self, task, context=None):
        global _current_user_id
        _current_user_id = (context or {}).get("user_id", "default")
        return await super().execute(task, context)

    async def execute_stream(self, task, context=None):
        global _current_user_id
        _current_user_id = (context or {}).get("user_id", "default")
        async for event in super().execute_stream(task, context):
            yield event
