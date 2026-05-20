"""Agent layer exports.

Imports are intentionally lazy so importing ``stock_datasource.agents`` does not
load every legacy direct-import agent and its optional data-service dependencies.
"""

from __future__ import annotations

from .base_agent import (
    AgentConfig,
    AgentContext,
    AgentResult,
    BaseAgent,
    BaseStockAgent,
    BaseTool,
    LangGraphAgent,
    ToolDefinition,
    get_langchain_model,
    get_langfuse_handler,
)

_LAZY_EXPORTS = {
    "BacktestAgent": (".backtest_agent", "BacktestAgent"),
    "ChatAgent": (".chat_agent", "ChatAgent"),
    "DataManageAgent": (".datamanage_agent", "DataManageAgent"),
    "EtfAgent": (".etf_agent", "EtfAgent"),
    "get_etf_agent": (".etf_agent", "get_etf_agent"),
    "HKReportAgent": (".hk_report_agent", "HKReportAgent"),
    "IndexAgent": (".index_agent", "IndexAgent"),
    "get_index_agent": (".index_agent", "get_index_agent"),
    "KnowledgeAgent": (".knowledge_agent", "KnowledgeAgent"),
    "get_knowledge_agent": (".knowledge_agent", "get_knowledge_agent"),
    "MarketAgent": (".market_agent", "MarketAgent"),
    "get_market_agent": (".market_agent", "get_market_agent"),
    "NewsAnalystAgent": (".news_analyst_agent", "NewsAnalystAgent"),
    "get_news_analyst_agent": (".news_analyst_agent", "get_news_analyst_agent"),
    "OrchestratorAgent": (".orchestrator", "OrchestratorAgent"),
    "get_orchestrator": (".orchestrator", "get_orchestrator"),
    "PortfolioAgent": (".portfolio_agent", "PortfolioAgent"),
    "ReportAgent": (".report_agent", "ReportAgent"),
    "ScreenerAgent": (".screener_agent", "ScreenerAgent"),
    "get_screener_agent": (".screener_agent", "get_screener_agent"),
    "STOCK_TOOLS": (".tools", "STOCK_TOOLS"),
    "TopListAgent": (".toplist_agent", "TopListAgent"),
}


def __getattr__(name: str):
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


__all__ = [
    "LangGraphAgent",
    "BaseStockAgent",
    "BaseAgent",
    "AgentConfig",
    "ToolDefinition",
    "BaseTool",
    "AgentContext",
    "AgentResult",
    "get_langchain_model",
    "get_langfuse_handler",
    *_LAZY_EXPORTS.keys(),
]
