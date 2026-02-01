"""
Agent Discussion Orchestrator

Coordinates discussions among multiple agents in the arena.
Supports debate, collaboration, and review modes.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import (
    Arena,
    ArenaStrategy,
    DiscussionMode,
    DiscussionRound,
    ThinkingMessage,
    MessageType,
    AgentConfig,
)
from .agents import ArenaAgentBase, create_agent_from_config
from .stream_processor import ThinkingStreamProcessor
from .exceptions import DiscussionError

logger = logging.getLogger(__name__)


class AgentDiscussionOrchestrator:
    """Orchestrates discussions among multiple agents.
    
    Supports three discussion modes:
    - DEBATE: Agents challenge each other's strategies
    - COLLABORATION: Agents collaborate to improve strategies
    - REVIEW: Some agents generate, others review
    
    Each round follows a structured flow:
    1. Round initialization
    2. Mode-specific discussion
    3. Conclusion collection
    4. Strategy refinement
    """
    
    def __init__(self, arena: Arena, stream_processor: ThinkingStreamProcessor = None):
        self.arena = arena
        self.stream_processor = stream_processor or ThinkingStreamProcessor(arena.id)
        self.agents: Dict[str, ArenaAgentBase] = {}
        self._initialize_agents()
    
    def _initialize_agents(self) -> None:
        """Initialize agents from arena configuration."""
        for agent_config in self.arena.config.agents:
            agent = create_agent_from_config(
                config=agent_config,
                arena_id=self.arena.id,
                stream_processor=self.stream_processor,
            )
            self.agents[agent_config.agent_id] = agent
            logger.info(f"Initialized agent: {agent_config.agent_id} ({agent_config.role})")
    
    async def run_discussion(
        self,
        strategies: List[ArenaStrategy],
        mode: DiscussionMode,
        market_context: Dict[str, Any] = None,
    ) -> DiscussionRound:
        """Run a complete discussion round.
        
        Args:
            strategies: Strategies to discuss
            mode: Discussion mode
            market_context: Current market data
            
        Returns:
            Completed DiscussionRound
        """
        round_id = str(uuid.uuid4())[:8]
        round_number = len(self.arena.discussion_rounds) + 1
        
        discussion_round = DiscussionRound(
            id=round_id,
            arena_id=self.arena.id,
            round_number=round_number,
            mode=mode,
            participants=list(self.agents.keys()),
        )
        
        try:
            # Announce round start
            await self.stream_processor.publish_system(
                f"## 讨论轮次 {round_number}: {mode.value.upper()} 模式\n"
                f"参与者: {len(self.agents)} 个Agent\n"
                f"讨论策略: {len(strategies)} 个",
                metadata={"round_id": round_id, "mode": mode.value},
            )
            
            # Set market context for all agents
            for agent in self.agents.values():
                agent.set_market_context(market_context or {})
            
            # Execute mode-specific discussion
            if mode == DiscussionMode.DEBATE:
                await self._run_debate(discussion_round, strategies)
            elif mode == DiscussionMode.COLLABORATION:
                await self._run_collaboration(discussion_round, strategies)
            elif mode == DiscussionMode.REVIEW:
                await self._run_review(discussion_round, strategies)
            
            # Complete round
            discussion_round.completed_at = datetime.now()
            
            # Announce round completion
            await self.stream_processor.publish_system(
                f"## 讨论轮次 {round_number} 完成\n"
                f"持续时间: {discussion_round.duration_seconds:.1f}秒\n"
                f"消息数量: {len(discussion_round.messages)}",
            )
            
            return discussion_round
            
        except Exception as e:
            logger.error(f"Discussion round failed: {e}")
            await self.stream_processor.publish_error(
                f"讨论轮次 {round_number} 失败: {str(e)}",
                metadata={"round_id": round_id, "error": str(e)},
            )
            raise DiscussionError(
                arena_id=self.arena.id,
                round_id=round_id,
                mode=mode.value,
                error=str(e),
            )
    
    async def _run_debate(
        self,
        discussion_round: DiscussionRound,
        strategies: List[ArenaStrategy],
    ) -> None:
        """Run debate mode discussion.
        
        In debate mode, agents critique each other's strategies,
        challenging logic and identifying weaknesses.
        """
        await self.stream_processor.publish_system(
            "开始辩论模式: 各Agent将质疑和挑战其他策略",
        )
        
        all_critiques: Dict[str, List[Dict[str, Any]]] = {s.id: [] for s in strategies}
        
        # Each agent critiques each strategy (except their own)
        critique_tasks = []
        
        for strategy in strategies:
            for agent_id, agent in self.agents.items():
                # Skip self-critique
                if agent_id == strategy.agent_id:
                    continue
                
                critique_tasks.append(
                    self._agent_critique(
                        agent=agent,
                        strategy=strategy,
                        round_id=discussion_round.id,
                        discussion_round=discussion_round,
                        all_critiques=all_critiques,
                    )
                )
        
        # Run critiques with limited concurrency
        await self._run_with_concurrency(critique_tasks, max_concurrent=3)
        
        # Collect conclusions
        discussion_round.conclusions = {
            s.id: f"收到 {len(all_critiques[s.id])} 条评论"
            for s in strategies
        }
    
    async def _agent_critique(
        self,
        agent: ArenaAgentBase,
        strategy: ArenaStrategy,
        round_id: str,
        discussion_round: DiscussionRound,
        all_critiques: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        """Have an agent critique a strategy."""
        try:
            critique = await agent.critique_strategy(
                strategy=strategy,
                round_id=round_id,
            )
            all_critiques[strategy.id].append(critique)
        except Exception as e:
            logger.warning(f"Agent {agent.agent_id} critique failed: {e}")
    
    async def _run_collaboration(
        self,
        discussion_round: DiscussionRound,
        strategies: List[ArenaStrategy],
    ) -> None:
        """Run collaboration mode discussion.
        
        In collaboration mode, agents work together to improve strategies,
        building on each other's ideas.
        """
        await self.stream_processor.publish_system(
            "开始协作模式: 各Agent将互相补充和完善策略",
        )
        
        # Sequential rounds of improvement
        for i, strategy in enumerate(strategies):
            await self.stream_processor.publish_system(
                f"协作完善策略 {i+1}/{len(strategies)}: {strategy.name}",
            )
            
            # Each agent adds their perspective
            improvements = []
            for agent_id, agent in self.agents.items():
                if agent_id == strategy.agent_id:
                    continue
                
                try:
                    critique = await agent.critique_strategy(
                        strategy=strategy,
                        round_id=discussion_round.id,
                    )
                    improvements.extend(critique.get("suggestions", []))
                except Exception as e:
                    logger.warning(f"Collaboration from {agent_id} failed: {e}")
            
            # Store improvements
            discussion_round.conclusions[strategy.id] = f"收集到 {len(improvements)} 条改进建议"
    
    async def _run_review(
        self,
        discussion_round: DiscussionRound,
        strategies: List[ArenaStrategy],
    ) -> None:
        """Run review mode discussion.
        
        In review mode, designated reviewers evaluate strategies
        and provide structured feedback.
        """
        await self.stream_processor.publish_system(
            "开始评审模式: 评审Agent将对策略进行打分评估",
        )
        
        # Identify reviewers (Strategy Reviewers and Risk Analysts)
        reviewers = [
            agent for agent in self.agents.values()
            if "reviewer" in agent.role.value.lower() or "analyst" in agent.role.value.lower()
        ]
        
        if not reviewers:
            reviewers = list(self.agents.values())[:2]  # Fallback to first 2 agents
        
        await self.stream_processor.publish_system(
            f"评审团: {len(reviewers)} 位评审员",
        )
        
        # Each reviewer evaluates each strategy
        review_scores: Dict[str, List[float]] = {s.id: [] for s in strategies}
        
        for strategy in strategies:
            for reviewer in reviewers:
                try:
                    critique = await reviewer.critique_strategy(
                        strategy=strategy,
                        round_id=discussion_round.id,
                    )
                    score = critique.get("overall_score", 50)
                    review_scores[strategy.id].append(score)
                except Exception as e:
                    logger.warning(f"Review from {reviewer.agent_id} failed: {e}")
        
        # Calculate average scores and conclusions
        for strategy in strategies:
            scores = review_scores[strategy.id]
            avg_score = sum(scores) / len(scores) if scores else 0
            discussion_round.conclusions[strategy.id] = f"平均评分: {avg_score:.1f}/100"
    
    async def refine_strategies(
        self,
        strategies: List[ArenaStrategy],
        discussion_round: DiscussionRound,
    ) -> List[ArenaStrategy]:
        """Refine strategies based on discussion results.
        
        Args:
            strategies: Original strategies
            discussion_round: Completed discussion round
            
        Returns:
            Refined strategies
        """
        refined_strategies = []
        
        # Collect critiques from discussion messages
        critiques_by_strategy: Dict[str, List[Dict[str, Any]]] = {
            s.id: [] for s in strategies
        }
        
        for message in discussion_round.messages:
            if message.message_type == MessageType.ARGUMENT:
                target_id = message.metadata.get("target_strategy_id")
                if target_id and target_id in critiques_by_strategy:
                    critiques_by_strategy[target_id].append({
                        "agent_id": message.agent_id,
                        "content": message.content,
                    })
        
        # Refine each strategy
        for strategy in strategies:
            owner_agent = self.agents.get(strategy.agent_id)
            if not owner_agent:
                # Find any generator agent
                owner_agent = next(
                    (a for a in self.agents.values() if "generator" in a.role.value.lower()),
                    list(self.agents.values())[0] if self.agents else None
                )
            
            if not owner_agent:
                refined_strategies.append(strategy)
                continue
            
            try:
                critiques = critiques_by_strategy.get(strategy.id, [])
                if critiques:
                    refined = await owner_agent.refine_strategy(
                        strategy=strategy,
                        critiques=critiques,
                        round_id=discussion_round.id,
                    )
                    refined_strategies.append(refined)
                else:
                    refined_strategies.append(strategy)
            except Exception as e:
                logger.warning(f"Failed to refine strategy {strategy.id}: {e}")
                refined_strategies.append(strategy)
        
        return refined_strategies
    
    async def _run_with_concurrency(
        self,
        tasks: List,
        max_concurrent: int = 3,
    ) -> None:
        """Run tasks with limited concurrency."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await task
        
        await asyncio.gather(
            *[run_with_semaphore(task) for task in tasks],
            return_exceptions=True,
        )
    
    def get_agent(self, agent_id: str) -> Optional[ArenaAgentBase]:
        """Get an agent by ID."""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> List[ArenaAgentBase]:
        """Get all agents."""
        return list(self.agents.values())
