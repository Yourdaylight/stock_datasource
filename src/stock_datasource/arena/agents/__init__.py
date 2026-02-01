"""
Arena Agents Module

Defines the various agent types for the Multi-Agent Strategy Arena.
Each agent has specialized capabilities for strategy generation, review, and analysis.
"""

from .strategy_generator import StrategyGeneratorAgent
from .strategy_reviewer import StrategyReviewerAgent
from .risk_analyst import RiskAnalystAgent
from .market_sentiment import MarketSentimentAgent
from .quant_researcher import QuantResearcherAgent
from .base import ArenaAgentBase, create_agent_from_config

__all__ = [
    'ArenaAgentBase',
    'StrategyGeneratorAgent',
    'StrategyReviewerAgent',
    'RiskAnalystAgent',
    'MarketSentimentAgent',
    'QuantResearcherAgent',
    'create_agent_from_config',
]
