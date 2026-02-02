"""
Arena Agent Base Class

Defines the base class for all arena agents with common functionality.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
import asyncio

from ..models import AgentConfig, AgentRole, ThinkingMessage, MessageType, ArenaStrategy
from ..stream_processor import ThinkingStreamProcessor

logger = logging.getLogger(__name__)


class ArenaAgentBase(ABC):
    """Base class for all arena agents.
    
    Provides common functionality:
    - LLM integration
    - Thinking stream publishing
    - Market context integration
    - Tool execution
    """
    
    def __init__(
        self,
        config: AgentConfig,
        arena_id: str,
        stream_processor: ThinkingStreamProcessor = None,
    ):
        self.config = config
        self.arena_id = arena_id
        self.agent_id = config.agent_id
        self.role = config.role
        self.model_name = config.model_name
        self.temperature = config.temperature
        self.personality = config.personality
        self.focus_areas = config.focus_areas
        
        # Stream processor for thinking output
        self.stream_processor = stream_processor or ThinkingStreamProcessor(arena_id)
        
        # LLM client (lazy loaded)
        self._llm_client = None
        
        # Market context (injected)
        self._market_context: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def role_name(self) -> str:
        """Human-readable role name."""
        pass
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass
    
    @abstractmethod
    async def generate_strategy(
        self,
        symbols: List[str],
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> ArenaStrategy:
        """Generate a trading strategy.
        
        Args:
            symbols: Stock symbols to consider
            market_context: Current market data and analysis
            round_id: Current discussion round ID
            
        Returns:
            Generated ArenaStrategy
        """
        pass
    
    @abstractmethod
    async def critique_strategy(
        self,
        strategy: ArenaStrategy,
        market_context: Dict[str, Any] = None,
        round_id: str = "",
    ) -> Dict[str, Any]:
        """Critique another agent's strategy.
        
        Args:
            strategy: Strategy to critique
            market_context: Current market data
            round_id: Current discussion round ID
            
        Returns:
            Critique with strengths, weaknesses, and suggestions
        """
        pass
    
    @abstractmethod
    async def refine_strategy(
        self,
        strategy: ArenaStrategy,
        critiques: List[Dict[str, Any]],
        round_id: str = "",
    ) -> ArenaStrategy:
        """Refine a strategy based on critiques.
        
        Args:
            strategy: Original strategy
            critiques: List of critiques from other agents
            round_id: Current discussion round ID
            
        Returns:
            Refined ArenaStrategy
        """
        pass
    
    def set_market_context(self, context: Dict[str, Any]) -> None:
        """Set market context for strategy generation."""
        self._market_context = context
    
    async def think(
        self,
        content: str,
        message_type: MessageType = MessageType.THINKING,
        round_id: str = "",
        metadata: Dict[str, Any] = None,
    ) -> ThinkingMessage:
        """Publish a thinking message to the stream.
        
        Args:
            content: Thinking content
            message_type: Type of message
            round_id: Discussion round ID
            metadata: Additional metadata
            
        Returns:
            Published ThinkingMessage
        """
        return await self.stream_processor.publish(
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            content=content,
            message_type=message_type,
            round_id=round_id,
            metadata=metadata or {},
        )
    
    async def argue(
        self,
        content: str,
        round_id: str = "",
        target_strategy_id: str = None,
        metadata: Dict[str, Any] = None,
    ) -> ThinkingMessage:
        """Publish an argument in the discussion.
        
        Args:
            content: Argument content
            round_id: Discussion round ID
            target_strategy_id: Strategy being discussed
            metadata: Additional metadata
            
        Returns:
            Published ThinkingMessage
        """
        meta = metadata or {}
        if target_strategy_id:
            meta["target_strategy_id"] = target_strategy_id
        
        return await self.stream_processor.publish(
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            content=content,
            message_type=MessageType.ARGUMENT,
            round_id=round_id,
            metadata=meta,
        )
    
    async def conclude(
        self,
        content: str,
        round_id: str = "",
        metadata: Dict[str, Any] = None,
    ) -> ThinkingMessage:
        """Publish a conclusion.
        
        Args:
            content: Conclusion content
            round_id: Discussion round ID
            metadata: Additional metadata
            
        Returns:
            Published ThinkingMessage
        """
        return await self.stream_processor.publish(
            agent_id=self.agent_id,
            agent_role=self.role.value if hasattr(self.role, 'value') else str(self.role),
            content=content,
            message_type=MessageType.CONCLUSION,
            round_id=round_id,
            metadata=metadata or {},
        )
    
    async def _get_llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from ...llm.client import get_llm_client
                self._llm_client = get_llm_client()
            except Exception as e:
                logger.error(f"Failed to get LLM client: {e}")
                raise
        return self._llm_client
    
    async def _call_llm(
        self,
        prompt: str,
        system_prompt: str = None,
        temperature: float = None,
    ) -> str:
        """Call the LLM with the given prompt.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            temperature: Optional temperature override
            
        Returns:
            LLM response string
        """
        client = await self._get_llm_client()
        
        response = await client.generate(
            prompt=prompt,
            system_prompt=system_prompt or self.get_system_prompt(),
            temperature=temperature or self.temperature,
        )
        
        return response
    
    async def _call_llm_streaming(
        self,
        prompt: str,
        system_prompt: str = None,
        round_id: str = "",
    ) -> str:
        """Call LLM with streaming, publishing thinking as we go.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt override
            round_id: Discussion round ID
            
        Returns:
            Complete LLM response
        """
        client = await self._get_llm_client()
        
        full_response = ""
        buffer = ""
        
        async for chunk in client.stream(
            prompt=prompt,
            system_prompt=system_prompt or self.get_system_prompt(),
            temperature=self.temperature,
        ):
            full_response += chunk
            buffer += chunk
            
            # Publish thinking in chunks
            if len(buffer) > 100 or chunk.endswith("\n"):
                await self.think(buffer, round_id=round_id)
                buffer = ""
        
        # Publish remaining buffer
        if buffer:
            await self.think(buffer, round_id=round_id)
        
        return full_response
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information."""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value if hasattr(self.role, 'value') else str(self.role),
            "role_name": self.role_name,
            "model": self.model_name,
            "personality": self.personality,
            "focus_areas": self.focus_areas,
        }


def create_agent_from_config(
    config: AgentConfig,
    arena_id: str,
    stream_processor: ThinkingStreamProcessor = None,
) -> ArenaAgentBase:
    """Factory function to create an agent from configuration.
    
    Args:
        config: Agent configuration
        arena_id: Arena ID
        stream_processor: Optional stream processor
        
    Returns:
        Created agent instance
    """
    from .strategy_generator import StrategyGeneratorAgent
    from .strategy_reviewer import StrategyReviewerAgent
    from .risk_analyst import RiskAnalystAgent
    from .market_sentiment import MarketSentimentAgent
    from .quant_researcher import QuantResearcherAgent
    
    role_to_class = {
        AgentRole.STRATEGY_GENERATOR: StrategyGeneratorAgent,
        AgentRole.STRATEGY_REVIEWER: StrategyReviewerAgent,
        AgentRole.RISK_ANALYST: RiskAnalystAgent,
        AgentRole.MARKET_SENTIMENT: MarketSentimentAgent,
        AgentRole.QUANT_RESEARCHER: QuantResearcherAgent,
    }
    
    agent_class = role_to_class.get(config.role, StrategyGeneratorAgent)
    
    return agent_class(
        config=config,
        arena_id=arena_id,
        stream_processor=stream_processor,
    )
