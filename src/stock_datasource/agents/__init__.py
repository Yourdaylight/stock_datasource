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

from .base_agent import (
    LangGraphAgent,
    BaseStockAgent,  # Backward compatibility alias
    BaseAgent,  # Backward compatibility alias
    AgentConfig,
    ToolDefinition,
    BaseTool,  # Backward compatibility alias
    AgentContext,
    AgentResult,
    get_langchain_model,
    get_langfuse_handler,
)
from .orchestrator import OrchestratorAgent, get_orchestrator
from .tools import STOCK_TOOLS
from .chat_agent import ChatAgent
from .market_agent import MarketAgent
from .screener_agent import ScreenerAgent
from .report_agent import ReportAgent
from .memory_agent import MemoryAgent
from .datamanage_agent import DataManageAgent
from .portfolio_agent import PortfolioAgent
from .backtest_agent import BacktestAgent
from .index_agent import IndexAgent, get_index_agent

# For backward compatibility with deep_agent imports
from .deep_agent import StockDeepAgent, get_stock_agent

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
    "ScreenerAgent",
    "ReportAgent",
    "MemoryAgent",
    "DataManageAgent",
    "PortfolioAgent",
    "BacktestAgent",
    "IndexAgent",
    "get_index_agent",
    # DeepAgent (for backward compatibility)
    "StockDeepAgent",
    "get_stock_agent",
]
