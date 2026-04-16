"""Agent layer for AI stock platform.

All agents are built on LangGraph/DeepAgents framework for:
- Tool calling with function calling
- Multi-step reasoning
- Langfuse observability
- Streaming responses

Provides specialized agents for:
- Market analysis (K-line, indicators, trend)
- Stock screening
- Financial report analysis
- Portfolio management
- Strategy backtesting
- User memory/preferences
- Data management
"""

from .backtest_agent import BacktestAgent
from .base_agent import (
    AgentConfig,
    AgentContext,
    AgentResult,
    BaseAgent,  # Backward compatibility alias
    BaseStockAgent,  # Backward compatibility alias
    BaseTool,  # Backward compatibility alias
    LangGraphAgent,
    ToolDefinition,
    get_langchain_model,
    get_langfuse_handler,
)
from .chat_agent import ChatAgent
from .datamanage_agent import DataManageAgent

# For backward compatibility with deep_agent imports
from .deep_agent import StockDeepAgent, get_stock_agent
from .etf_agent import EtfAgent, get_etf_agent
from .hk_report_agent import HKReportAgent
from .index_agent import IndexAgent, get_index_agent
from .knowledge_agent import KnowledgeAgent, get_knowledge_agent
from .market_agent import MarketAgent, get_market_agent
from .memory_agent import MemoryAgent
from .news_analyst_agent import NewsAnalystAgent, get_news_analyst_agent
from .orchestrator import OrchestratorAgent, get_orchestrator
from .overview_agent import OverviewAgent, get_overview_agent
from .portfolio_agent import PortfolioAgent
from .report_agent import ReportAgent
from .screener_agent import ScreenerAgent, get_screener_agent
from .tools import STOCK_TOOLS
from .toplist_agent import TopListAgent

__all__ = [
    # Base classes
    "LangGraphAgent",
    "BaseStockAgent",
    "BaseAgent",
    "AgentConfig",
    "ToolDefinition",
    "BaseTool",
    "AgentContext",
    "AgentResult",
    # Utilities
    "get_langchain_model",
    "get_langfuse_handler",
    # Orchestrator
    "OrchestratorAgent",
    "get_orchestrator",
    # Tools
    "STOCK_TOOLS",
    # Specialized agents (all based on LangGraph)
    "ChatAgent",
    "MarketAgent",
    "get_market_agent",
    "ScreenerAgent",
    "get_screener_agent",
    "ReportAgent",
    "HKReportAgent",
    "MemoryAgent",
    "DataManageAgent",
    "PortfolioAgent",
    "BacktestAgent",
    "IndexAgent",
    "get_index_agent",
    "EtfAgent",
    "get_etf_agent",
    "OverviewAgent",
    "get_overview_agent",
    "TopListAgent",
    "NewsAnalystAgent",
    "get_news_analyst_agent",
    "KnowledgeAgent",
    "get_knowledge_agent",
    # DeepAgent (for backward compatibility)
    "StockDeepAgent",
    "get_stock_agent",
]
