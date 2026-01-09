"""DeepAgent implementation for stock analysis platform.

This is a general-purpose stock analysis agent that combines all tools.
For specialized tasks, use the specific agents (MarketAgent, ScreenerAgent, etc.)
"""

from typing import Dict, Any, Optional, List, Callable
import logging

from .base_agent import LangGraphAgent, AgentConfig
from .tools import STOCK_TOOLS

logger = logging.getLogger(__name__)


class StockDeepAgent(LangGraphAgent):
    """General-purpose stock analysis agent using DeepAgents framework.
    
    This agent has access to all stock analysis tools and can handle
    a wide variety of queries. For specialized tasks, consider using
    the specific agents (MarketAgent, ScreenerAgent, etc.)
    """
    
    def __init__(self):
        config = AgentConfig(
            name="StockDeepAgent",
            description="通用股票分析智能体，具备所有分析工具",
            recursion_limit=50,
        )
        super().__init__(config)
    
    def get_tools(self) -> List[Callable]:
        """Return all stock analysis tools."""
        return STOCK_TOOLS
    
    def get_system_prompt(self) -> str:
        """Return system prompt for the general agent."""
        return """你是一个专业的A股股票分析AI助手。

## 可用工具
- get_stock_info: 获取股票基本信息和最新行情
- get_stock_kline: 获取K线数据
- get_stock_valuation: 获取PE、PB等估值指标
- calculate_technical_indicators: 计算均线、趋势等技术指标
- screen_stocks: 根据条件筛选股票
- get_market_overview: 获取大盘整体情况

## 常用股票代码
- 贵州茅台: 600519
- 平安银行: 000001
- 比亚迪: 002594

## 分析原则
1. 直接调用工具获取数据，不要过度规划
2. 获取数据后立即给出分析结论
3. 使用中文回复，简洁专业
4. 最多调用3个工具，然后给出结论
5. 明确指出投资风险

## 免责声明
分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。
"""


# Singleton instance
_stock_agent: Optional[StockDeepAgent] = None


def get_stock_agent() -> StockDeepAgent:
    """Get or create the stock analysis agent."""
    global _stock_agent
    if _stock_agent is None:
        _stock_agent = StockDeepAgent()
    return _stock_agent
