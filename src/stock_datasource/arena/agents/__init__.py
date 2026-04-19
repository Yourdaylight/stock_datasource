"""
Arena Agents Module

Defines the various agent types for the Multi-Agent Strategy Arena.
Each agent has specialized capabilities for strategy generation, review, and analysis.
"""

from .base import ArenaAgentBase, create_agent_from_config
from .market_sentiment import MarketSentimentAgent
from .quant_researcher import QuantResearcherAgent
from .risk_analyst import RiskAnalystAgent
from .strategy_generator import StrategyGeneratorAgent
from .strategy_reviewer import StrategyReviewerAgent

__all__ = [
    "ArenaAgentBase",
    "MarketSentimentAgent",
    "QuantResearcherAgent",
    "RiskAnalystAgent",
    "StrategyGeneratorAgent",
    "StrategyReviewerAgent",
    "create_agent_from_config",
]
