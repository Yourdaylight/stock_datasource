"""Memory Agent for user context management using LangGraph/DeepAgents."""

from typing import Dict, Any, List, Callable, Literal
import logging

from .base_agent import LangGraphAgent, AgentConfig

logger = logging.getLogger(__name__)

# 内存存储（生产环境应使用数据库）
_memory_store: Dict[str, Dict] = {}


def save_user_preference(
    key: str,
    value: str,
    category: str = "style"
) -> str:
    """保存用户偏好设置。
    
    Args:
        key: 偏好键名，如 risk_level, favorite_industries
        value: 偏好值
        category: 偏好类别 - risk(风险偏好), industry(行业偏好), 
                  style(投资风格), notification(通知设置)
    
    Returns:
        保存结果消息
    """
    if "preferences" not in _memory_store:
        _memory_store["preferences"] = {}
    
    _memory_store["preferences"][key] = {
        "value": value,
        "category": category,
    }
    
    return f"已保存偏好设置: {key} = {value} (类别: {category})"


def get_user_preference(key: str) -> str:
    """获取用户偏好设置。
    
    Args:
        key: 偏好键名
    
    Returns:
        偏好值或未找到提示
    """
    prefs = _memory_store.get("preferences", {})
    if key in prefs:
        return f"{key} = {prefs[key]['value']}"
    return f"未找到偏好设置: {key}"


def manage_watchlist(
    action: str,
    code: str = "",
    group: str = "default"
) -> str:
    """管理用户自选股。
    
    Args:
        action: 操作类型 - add(添加), remove(删除), list(列出), clear(清空)
        code: 股票代码（add/remove时需要）
        group: 自选股分组名称
    
    Returns:
        操作结果消息
    """
    if "watchlist" not in _memory_store:
        _memory_store["watchlist"] = {}
    
    if group not in _memory_store["watchlist"]:
        _memory_store["watchlist"][group] = []
    
    watchlist = _memory_store["watchlist"][group]
    
    if action == "add":
        if code and code not in watchlist:
            watchlist.append(code)
            return f"已将 {code} 添加到自选股分组 [{group}]"
        return f"{code} 已在自选股中"
    
    elif action == "remove":
        if code in watchlist:
            watchlist.remove(code)
            return f"已将 {code} 从自选股分组 [{group}] 移除"
        return f"{code} 不在自选股中"
    
    elif action == "list":
        if watchlist:
            return f"自选股分组 [{group}]: {', '.join(watchlist)}"
        return f"自选股分组 [{group}] 为空"
    
    elif action == "clear":
        _memory_store["watchlist"][group] = []
        return f"已清空自选股分组 [{group}]"
    
    return f"未知操作: {action}"


def get_memory_summary() -> str:
    """获取用户记忆摘要。
    
    Returns:
        用户偏好和自选股的摘要信息
    """
    lines = ["## 用户记忆摘要\n"]
    
    # 偏好设置
    prefs = _memory_store.get("preferences", {})
    if prefs:
        lines.append("### 偏好设置")
        for key, val in prefs.items():
            lines.append(f"- {key}: {val['value']}")
        lines.append("")
    else:
        lines.append("### 偏好设置\n暂无设置\n")
    
    # 自选股
    watchlists = _memory_store.get("watchlist", {})
    if watchlists:
        lines.append("### 自选股")
        for group, stocks in watchlists.items():
            if stocks:
                lines.append(f"- [{group}]: {', '.join(stocks)}")
        lines.append("")
    else:
        lines.append("### 自选股\n暂无自选股\n")
    
    return "\n".join(lines)


class MemoryAgent(LangGraphAgent):
    """Memory Agent for managing user context and preferences using DeepAgents.
    
    Handles:
    - User preference storage
    - Watchlist management
    - Memory summary
    """
    
    def __init__(self):
        config = AgentConfig(
            name="MemoryAgent",
            description="负责用户记忆管理，包括偏好设置、自选股管理等"
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return memory management tools."""
        return [
            save_user_preference,
            get_user_preference,
            manage_watchlist,
            get_memory_summary,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for memory management."""
        return """你是用户记忆管理助手，帮助用户管理投资偏好和自选股。

## 可用工具
- save_user_preference: 保存用户偏好（风险偏好、行业偏好等）
- get_user_preference: 获取用户偏好
- manage_watchlist: 管理自选股（添加/删除/列出/清空）
- get_memory_summary: 获取用户记忆摘要

## 偏好类别
- risk: 风险偏好（保守/稳健/激进）
- industry: 关注行业（科技/消费/金融等）
- style: 投资风格（价值/成长/趋势等）
- notification: 通知设置

## 自选股操作
- add: 添加股票到自选
- remove: 从自选移除
- list: 列出自选股
- clear: 清空自选股

## 工作原则
- 准确理解用户意图
- 确认操作后执行
- 给出操作结果反馈
"""
