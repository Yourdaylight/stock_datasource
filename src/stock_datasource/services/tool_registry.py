"""Global tool registry: maps skill/tool names (strings from DB config) to callable functions.

This bridges the gap between the DB-stored agent config (which stores tool names as strings)
and the actual Python callable functions needed by create_deep_agent().

Usage:
    from stock_datasource.services.tool_registry import auto_discover_tools, resolve_tools

    auto_discover_tools()  # Register all known tools
    tools = resolve_tools(["get_stock_info", "calculate_technical_indicators"])
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Registry: name -> callable
TOOL_REGISTRY: dict[str, Callable] = {}


def register_tool(name: str, func: Callable) -> None:
    """Register a single tool by name.

    Args:
        name: Tool name (used in DB config `skills` array)
        func: The actual callable tool function
    """
    TOOL_REGISTRY[name] = func
    logger.debug("Registered tool: %s", name)


def unregister_tool(name: str) -> bool:
    """Remove a tool from the registry.

    Returns:
        True if the tool existed and was removed
    """
    return TOOL_REGISTRY.pop(name, None) is not None


def resolve_tools(skill_names: list[str]) -> list[Callable]:
    """Resolve skill/tool names to actual tool functions.

    Unknown names are logged as warnings and skipped.

    Args:
        skill_names: List of tool names from the DB config

    Returns:
        List of resolved callable tool functions
    """
    tools: list[Callable] = []
    for name in skill_names:
        if name in TOOL_REGISTRY:
            tools.append(TOOL_REGISTRY[name])
        else:
            logger.warning("Tool '%s' not found in registry, skipping", name)
    return tools


def get_registered_tool_names() -> list[str]:
    """Return sorted list of all registered tool names."""
    return sorted(TOOL_REGISTRY.keys())


def auto_discover_tools() -> int:
    """Auto-register all known tools from the agents package.

    Scans:
    - agents/tools.py (core stock tools)
    - agents/market_agent.py (market-specific tools)
    - agents/report_agent.py (financial report tools)
    - agents/news_analyst_agent.py (news tools)

    Returns:
        Number of tools registered
    """
    initial_count = len(TOOL_REGISTRY)

    # 1. Core tools from agents/tools.py
    _register_from_module(
        "stock_datasource.agents.tools",
        names=[
            "get_stock_info",
            "get_stock_kline",
            "get_stock_valuation",
            "calculate_technical_indicators",
            "screen_stocks",
            "get_market_overview",
            "get_stock_profile",
            "get_sector_stocks",
            "get_available_sectors",
        ],
    )

    # 2. Market agent tools (visualization-enabled)
    _register_from_module(
        "stock_datasource.agents.market_agent",
        names=[
            "get_kline",
            "calculate_indicators",
            "analyze_trend",
            # get_market_overview is already in core tools
        ],
    )

    # 3. Report agent tools
    _register_from_module(
        "stock_datasource.agents.report_agent",
        names=[
            "get_comprehensive_financial_analysis",
            "get_peer_comparison_analysis",
            "get_investment_insights",
            "get_income_statement",
            "get_balance_sheet",
            "get_cash_flow",
            "get_forecast",
            "get_express",
            "get_full_financial_statements",
            "get_audit_opinion",
            "get_non_standard_opinions",
        ],
    )

    # 4. News analyst tools
    _register_from_module(
        "stock_datasource.agents.news_analyst_agent",
        names=[
            "get_news_by_stock",
            "get_market_news",
            "analyze_news_sentiment",
            "get_hot_topics",
            "summarize_news",
            "get_stock_signal_summary",
        ],
    )

    registered = len(TOOL_REGISTRY) - initial_count
    logger.info(
        "Tool registry auto-discovery complete: %d new tools registered (total: %d)",
        registered,
        len(TOOL_REGISTRY),
    )
    return registered


def _register_from_module(module_path: str, names: list[str]) -> None:
    """Register specific functions from a module.

    Args:
        module_path: Dotted module path
        names: List of function names to register
    """
    try:
        module = importlib.import_module(module_path)
    except ImportError as e:
        logger.warning("Failed to import module %s: %s", module_path, e)
        return

    for name in names:
        func = getattr(module, name, None)
        if func is not None and callable(func):
            register_tool(name, func)
        else:
            logger.debug(
                "Function '%s' not found or not callable in %s", name, module_path
            )
