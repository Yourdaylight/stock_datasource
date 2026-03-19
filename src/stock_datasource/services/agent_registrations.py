"""Explicit agent registrations.

This module registers all known business agents with the AgentRegistry
using rich ``AgentDescriptor`` metadata.  It is called once at startup
(or on first registry access) so the runtime never needs to rely solely
on package scanning.

Import this module to populate the registry:

    from stock_datasource.services.agent_registrations import register_all_agents
    register_all_agents()
"""

from __future__ import annotations

import logging
from typing import List

from .agent_registry import (
    AgentDescriptor,
    AgentRole,
    CapabilityDescriptor,
    get_agent_registry,
)

logger = logging.getLogger(__name__)


def _build_descriptors() -> List[AgentDescriptor]:
    """Build descriptors for all known agents.

    Each descriptor carries intent tags, supported markets, and
    priority so the runtime can make fast routing decisions without
    LLM classification when possible.

    Lazy imports are used so that registration itself doesn't force
    heavy module loads until the agent is actually instantiated.
    """
    descriptors: List[AgentDescriptor] = []

    # --- Chat (general) --------------------------------------------------
    try:
        from stock_datasource.agents.chat_agent import ChatAgent
        descriptors.append(AgentDescriptor(
            name="ChatAgent",
            description="通用对话助手，处理一般性问答",
            agent_class=ChatAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["general_chat"],
                tags=["chat", "general"],
            ),
            priority=0,
        ))
    except ImportError:
        logger.debug("ChatAgent not available")

    # --- Market Agent (A-share + HK tech analysis) -----------------------
    try:
        from stock_datasource.agents.market_agent import MarketAgent
        descriptors.append(AgentDescriptor(
            name="MarketAgent",
            description="A股和港股行情分析Agent，提供K线、技术指标、趋势分析等",
            agent_class=MarketAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["market_analysis", "hk_market_analysis"],
                markets=["A", "HK"],
                tags=["market", "technical", "kline"],
            ),
            priority=10,
        ))
    except ImportError:
        logger.debug("MarketAgent not available")

    # --- Screener Agent ---------------------------------------------------
    try:
        from stock_datasource.agents.screener_agent import ScreenerAgent
        descriptors.append(AgentDescriptor(
            name="ScreenerAgent",
            description="股票筛选Agent，支持多维度条件筛选",
            agent_class=ScreenerAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["stock_screening"],
                markets=["A"],
                tags=["screener", "filter"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("ScreenerAgent not available")

    # --- Report Agent (A-share fundamentals) ------------------------------
    try:
        from stock_datasource.agents.report_agent import ReportAgent
        descriptors.append(AgentDescriptor(
            name="ReportAgent",
            description="A股财务报表分析Agent",
            agent_class=ReportAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["financial_report"],
                markets=["A"],
                tags=["report", "financial", "fundamental"],
            ),
            priority=8,
        ))
    except ImportError:
        logger.debug("ReportAgent not available")

    # --- HK Report Agent --------------------------------------------------
    try:
        from stock_datasource.agents.hk_report_agent import HKReportAgent
        descriptors.append(AgentDescriptor(
            name="HKReportAgent",
            description="港股财务报表分析Agent",
            agent_class=HKReportAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["hk_financial_report"],
                markets=["HK"],
                tags=["report", "financial", "hk"],
            ),
            priority=8,
        ))
    except ImportError:
        logger.debug("HKReportAgent not available")

    # --- Portfolio Agent --------------------------------------------------
    try:
        from stock_datasource.agents.portfolio_agent import PortfolioAgent
        descriptors.append(AgentDescriptor(
            name="PortfolioAgent",
            description="投资组合管理Agent",
            agent_class=PortfolioAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["portfolio_management"],
                tags=["portfolio"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("PortfolioAgent not available")

    # --- Backtest Agent ---------------------------------------------------
    try:
        from stock_datasource.agents.backtest_agent import BacktestAgent
        descriptors.append(AgentDescriptor(
            name="BacktestAgent",
            description="策略回测Agent",
            agent_class=BacktestAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["strategy_backtest"],
                tags=["backtest", "strategy"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("BacktestAgent not available")

    # --- Index Agent ------------------------------------------------------
    try:
        from stock_datasource.agents.index_agent import IndexAgent
        descriptors.append(AgentDescriptor(
            name="IndexAgent",
            description="指数分析Agent",
            agent_class=IndexAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["index_analysis"],
                tags=["index"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("IndexAgent not available")

    # --- ETF Agent --------------------------------------------------------
    try:
        from stock_datasource.agents.etf_agent import EtfAgent
        descriptors.append(AgentDescriptor(
            name="EtfAgent",
            description="ETF分析Agent",
            agent_class=EtfAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["etf_analysis"],
                tags=["etf"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("EtfAgent not available")

    # --- Overview Agent ---------------------------------------------------
    try:
        from stock_datasource.agents.overview_agent import OverviewAgent
        descriptors.append(AgentDescriptor(
            name="OverviewAgent",
            description="市场概览Agent",
            agent_class=OverviewAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["market_overview"],
                tags=["overview", "market"],
            ),
            priority=3,
        ))
    except ImportError:
        logger.debug("OverviewAgent not available")

    # --- TopList Agent ----------------------------------------------------
    try:
        from stock_datasource.agents.toplist_agent import TopListAgent
        descriptors.append(AgentDescriptor(
            name="TopListAgent",
            description="龙虎榜/排行Agent",
            agent_class=TopListAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["toplist"],
                tags=["toplist", "ranking"],
            ),
            priority=3,
        ))
    except ImportError:
        logger.debug("TopListAgent not available")

    # --- News Analyst Agent -----------------------------------------------
    try:
        from stock_datasource.agents.news_analyst_agent import NewsAnalystAgent
        descriptors.append(AgentDescriptor(
            name="NewsAnalystAgent",
            description="新闻分析Agent",
            agent_class=NewsAnalystAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["news_analysis"],
                tags=["news"],
            ),
            priority=3,
        ))
    except ImportError:
        logger.debug("NewsAnalystAgent not available")

    # --- Knowledge Agent (RAG) -------------------------------------------
    try:
        from stock_datasource.agents.knowledge_agent import KnowledgeAgent
        descriptors.append(AgentDescriptor(
            name="KnowledgeAgent",
            description="知识检索Agent(RAG)，用于研报、公告、政策文档查询",
            agent_class=KnowledgeAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["knowledge_search"],
                tags=["knowledge", "rag", "document"],
            ),
            priority=5,
        ))
    except ImportError:
        logger.debug("KnowledgeAgent not available")

    # --- Memory Agent (user preferences) ----------------------------------
    try:
        from stock_datasource.agents.memory_agent import MemoryAgent
        descriptors.append(AgentDescriptor(
            name="MemoryAgent",
            description="负责用户记忆管理，包括偏好设置、自选股管理等",
            agent_class=MemoryAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["memory_management"],
                tags=["memory", "preference", "watchlist"],
            ),
            priority=2,
        ))
    except ImportError:
        logger.debug("MemoryAgent not available")

    # --- DataManage Agent -------------------------------------------------
    try:
        from stock_datasource.agents.datamanage_agent import DataManageAgent
        descriptors.append(AgentDescriptor(
            name="DataManageAgent",
            description="数据管理Agent，支持数据同步、状态查询等",
            agent_class=DataManageAgent,
            role=AgentRole.AGENT,
            capability=CapabilityDescriptor(
                intents=["data_management"],
                tags=["data", "management", "sync"],
            ),
            priority=2,
        ))
    except ImportError:
        logger.debug("DataManageAgent not available")

    # --- Workflow Agent (adapter-role) ------------------------------------
    try:
        from stock_datasource.agents.workflow_agent import WorkflowAgent
        descriptors.append(AgentDescriptor(
            name="WorkflowAgent",
            description="动态工作流执行Agent",
            agent_class=WorkflowAgent,
            role=AgentRole.ADAPTER,
            capability=CapabilityDescriptor(
                intents=["workflow_execution"],
                tags=["workflow"],
            ),
            priority=1,
        ))
    except ImportError:
        logger.debug("WorkflowAgent not available")

    return descriptors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_registered = False


def register_all_agents() -> int:
    """Register all known agents with the global AgentRegistry.

    Safe to call multiple times; only runs once.

    Returns:
        Number of agents successfully registered.
    """
    global _registered
    if _registered:
        return 0
    _registered = True

    registry = get_agent_registry()
    descriptors = _build_descriptors()
    count = 0
    for desc in descriptors:
        try:
            registry.register(desc)
            count += 1
        except Exception as exc:
            logger.warning("Failed to register %s: %s", desc.name, exc)
    logger.info("Explicitly registered %d agents", count)
    return count
