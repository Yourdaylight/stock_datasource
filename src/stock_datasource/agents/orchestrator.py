"""Orchestrator Agent for routing and coordinating multiple LangGraph agents.

Uses LangGraph to create a multi-agent workflow that routes user requests
to the appropriate specialized agent.
"""

import re
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator

from .base_agent import LangGraphAgent, AgentConfig, AgentResult

logger = logging.getLogger(__name__)


# Intent to Agent mapping
INTENT_AGENT_MAP = {
    "market_analysis": "MarketAgent",
    "stock_screening": "ScreenerAgent",
    "financial_report": "ReportAgent",
    "portfolio_management": "PortfolioAgent",
    "strategy_backtest": "BacktestAgent",
    "memory_management": "MemoryAgent",
    "data_management": "DataManageAgent",
    "general_chat": "ChatAgent",
}

# Keywords for intent classification
INTENT_KEYWORDS = {
    "market_analysis": [
        "分析", "行情", "走势", "k线", "kline", "技术", "均线", "macd", "rsi",
        "趋势", "涨跌", "价格", "估值", "pe", "pb", "市值"
    ],
    "stock_screening": [
        "选股", "筛选", "找出", "哪些股票", "推荐", "低估", "高成长", "股息"
    ],
    "financial_report": [
        "财报", "财务", "报表", "利润", "营收", "roe", "毛利", "净利", "资产负债"
    ],
    "portfolio_management": [
        "持仓", "仓位", "买入", "卖出", "加仓", "减仓", "盈亏", "收益"
    ],
    "strategy_backtest": [
        "回测", "策略", "模拟", "历史", "测试策略"
    ],
    "memory_management": [
        "自选", "关注", "偏好", "设置", "记住", "记忆"
    ],
    "data_management": [
        "数据", "同步", "数据源", "插件", "质量", "更新数据"
    ],
}


class OrchestratorAgent:
    """Orchestrator for routing requests to specialized LangGraph agents.
    
    This orchestrator:
    1. Classifies user intent using keyword matching
    2. Extracts stock codes from the query
    3. Routes to the appropriate specialized agent
    4. Returns the agent's response
    """
    
    def __init__(self):
        self._agents: Dict[str, LangGraphAgent] = {}
    
    def _get_agent(self, agent_name: str) -> LangGraphAgent:
        """Get or create an agent by name."""
        if agent_name not in self._agents:
            if agent_name == "MarketAgent":
                from .market_agent import MarketAgent
                self._agents[agent_name] = MarketAgent()
            elif agent_name == "ScreenerAgent":
                from .screener_agent import ScreenerAgent
                self._agents[agent_name] = ScreenerAgent()
            elif agent_name == "ReportAgent":
                from .report_agent import ReportAgent
                self._agents[agent_name] = ReportAgent()
            elif agent_name == "PortfolioAgent":
                from .portfolio_agent import PortfolioAgent
                self._agents[agent_name] = PortfolioAgent()
            elif agent_name == "BacktestAgent":
                from .backtest_agent import BacktestAgent
                self._agents[agent_name] = BacktestAgent()
            elif agent_name == "MemoryAgent":
                from .memory_agent import MemoryAgent
                self._agents[agent_name] = MemoryAgent()
            elif agent_name == "DataManageAgent":
                from .datamanage_agent import DataManageAgent
                self._agents[agent_name] = DataManageAgent()
            else:
                from .chat_agent import ChatAgent
                self._agents[agent_name] = ChatAgent()
        
        return self._agents[agent_name]
    
    def _classify_intent(self, query: str) -> str:
        """Classify user intent based on keywords."""
        query_lower = query.lower()
        
        # Score each intent
        scores = {}
        for intent, keywords in INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[intent] = score
        
        if scores:
            best_intent = max(scores, key=scores.get)
            logger.info(f"Classified intent: {best_intent} (score: {scores[best_intent]})")
            return best_intent
        
        return "general_chat"
    
    def _extract_stock_codes(self, query: str) -> List[str]:
        """Extract stock codes from query."""
        codes = []
        
        # Pattern: 600519.SH or 000001.SZ
        pattern1 = r'(\d{6}\.[A-Za-z]{2})'
        matches = re.findall(pattern1, query)
        codes.extend([m.upper() for m in matches])
        
        # Pattern: 6-digit code
        pattern2 = r'(?<!\d)(\d{6})(?!\d)'
        matches = re.findall(pattern2, query)
        for code in matches:
            if code.startswith('6'):
                codes.append(f"{code}.SH")
            elif code.startswith(('0', '3')):
                codes.append(f"{code}.SZ")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_codes = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique_codes.append(code)
        
        return unique_codes
    
    async def execute(self, query: str, context: Dict[str, Any] = None) -> AgentResult:
        """Execute query by routing to appropriate agent.
        
        Args:
            query: User's query
            context: Optional context
            
        Returns:
            AgentResult from the specialized agent
        """
        context = context or {}
        
        # Classify intent
        intent = self._classify_intent(query)
        
        # Extract stock codes
        stock_codes = self._extract_stock_codes(query)
        
        # Update context
        context["intent"] = intent
        if stock_codes:
            context["stock_codes"] = stock_codes
        
        # Get appropriate agent
        agent_name = INTENT_AGENT_MAP.get(intent, "ChatAgent")
        agent = self._get_agent(agent_name)
        
        logger.info(f"Routing to {agent_name} for intent: {intent}")
        
        # Execute agent
        result = await agent.execute(query, context)
        
        # Add routing metadata
        result.metadata["routed_by"] = "OrchestratorAgent"
        result.metadata["intent"] = intent
        result.metadata["stock_codes"] = stock_codes
        
        return result
    
    async def execute_stream(
        self, 
        query: str, 
        context: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute query with streaming response.
        
        Args:
            query: User's query
            context: Optional context
            
        Yields:
            Event dicts from the specialized agent
        """
        context = context or {}
        
        # Classify intent
        intent = self._classify_intent(query)
        
        # Extract stock codes
        stock_codes = self._extract_stock_codes(query)
        
        # Update context
        context["intent"] = intent
        if stock_codes:
            context["stock_codes"] = stock_codes
        
        # Get appropriate agent
        agent_name = INTENT_AGENT_MAP.get(intent, "ChatAgent")
        agent = self._get_agent(agent_name)
        
        logger.info(f"Streaming via {agent_name} for intent: {intent}")
        
        # Stream from agent
        async for event in agent.execute_stream(query, context):
            # Add routing info to thinking events
            if event.get("type") == "thinking":
                event["routed_by"] = "OrchestratorAgent"
                event["intent"] = intent
            
            yield event


# Singleton instance
_orchestrator: Optional[OrchestratorAgent] = None


def get_orchestrator() -> OrchestratorAgent:
    """Get or create the orchestrator agent."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = OrchestratorAgent()
    return _orchestrator
