"""
Agent Discussion Orchestrator

Coordinates discussions among multiple agents in the arena.
Supports debate, collaboration, and review modes.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from .agents import ArenaAgentBase, create_agent_from_config
from .decision_summarizer import get_decision_summarizer
from .exceptions import DiscussionError
from .models import (
    Arena,
    ArenaStrategy,
    DecisionSummary,
    DiscussionMode,
    DiscussionRound,
    MessageType,
)
from .stream_processor import ThinkingStreamProcessor

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
        self.agents: dict[str, ArenaAgentBase] = {}
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
            logger.info(
                f"Initialized agent: {agent_config.agent_id} ({agent_config.role})"
            )

    async def run_discussion(
        self,
        strategies: list[ArenaStrategy],
        mode: DiscussionMode,
        market_context: dict[str, Any] = None,
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

            # Phase 1: Emit instant preview signal from rule-based vote counting
            # This gives the user a signal in <1s while the LLM synthesis runs
            preview_signal = await self._emit_preview_signal(
                discussion_round=discussion_round,
                strategies=strategies,
            )

            # Phase 2: Generate full decision summary (hybrid: rule-based + LLM)
            # This takes 10-30s but produces richer reasoning
            decision_summary = await self._generate_decision_summary(
                discussion_round=discussion_round,
                strategies=strategies,
                market_context=market_context,
            )

            # Publish decision summary via SSE (upgrades the preview)
            if decision_summary:
                await self.stream_processor.publish_system(
                    f"## 决策信号: {decision_summary.signal.upper()}\n"
                    f"- 置信度: {decision_summary.confidence:.0%}\n"
                    f"- 看多: {decision_summary.bull_count} | "
                    f"看空: {decision_summary.bear_count} | "
                    f"中性: {decision_summary.neutral_count}\n"
                    f"- 建议: {decision_summary.suggested_action}",
                    metadata={
                        "type": "decision_summary",
                        "signal": decision_summary.signal,
                        "confidence": decision_summary.confidence,
                        "decision_id": decision_summary.id,
                    },
                )
                # Store on the round for retrieval
                discussion_round.conclusions["_decision_summary"] = (
                    decision_summary.id
                )

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
                f"讨论轮次 {round_number} 失败: {e!s}",
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
        strategies: list[ArenaStrategy],
    ) -> None:
        """Run debate mode discussion.

        In debate mode, agents critique each other's strategies,
        challenging logic and identifying weaknesses.
        """
        await self.stream_processor.publish_system(
            "开始辩论模式: 各Agent将质疑和挑战其他策略",
        )

        all_critiques: dict[str, list[dict[str, Any]]] = {s.id: [] for s in strategies}

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
            s.id: f"收到 {len(all_critiques[s.id])} 条评论" for s in strategies
        }

    async def _agent_critique(
        self,
        agent: ArenaAgentBase,
        strategy: ArenaStrategy,
        round_id: str,
        discussion_round: DiscussionRound,
        all_critiques: dict[str, list[dict[str, Any]]],
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
        strategies: list[ArenaStrategy],
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
                f"协作完善策略 {i + 1}/{len(strategies)}: {strategy.name}",
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
            discussion_round.conclusions[strategy.id] = (
                f"收集到 {len(improvements)} 条改进建议"
            )

    async def _run_review(
        self,
        discussion_round: DiscussionRound,
        strategies: list[ArenaStrategy],
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
            agent
            for agent in self.agents.values()
            if "reviewer" in agent.role.value.lower()
            or "analyst" in agent.role.value.lower()
        ]

        if not reviewers:
            reviewers = list(self.agents.values())[:2]  # Fallback to first 2 agents

        await self.stream_processor.publish_system(
            f"评审团: {len(reviewers)} 位评审员",
        )

        # Each reviewer evaluates each strategy
        review_scores: dict[str, list[float]] = {s.id: [] for s in strategies}

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

    async def _generate_decision_summary(
        self,
        discussion_round: DiscussionRound,
        strategies: list[ArenaStrategy],
        market_context: dict[str, Any] = None,
    ) -> DecisionSummary | None:
        """Generate a decision summary after discussion completes.

        Uses the DecisionSummarizer to produce buy/sell/hold signals
        from the discussion messages.
        """
        try:
            summarizer = get_decision_summarizer()

            # Determine target stock code from strategies
            stock_code = ""
            if strategies:
                symbols = strategies[0].symbols
                if symbols:
                    stock_code = symbols[0]

            summary = await summarizer.generate_summary(
                discussion_round=discussion_round,
                stock_code=stock_code,
                market_context=market_context,
                arena_id=self.arena.id,
                user_id=self.arena.user_id,
            )

            # Store the summary for later retrieval
            if not hasattr(self.arena, "_decision_summaries"):
                self.arena._decision_summaries = []
            self.arena._decision_summaries.append(summary)

            logger.info(
                f"Generated decision summary: signal={summary.signal}, "
                f"confidence={summary.confidence:.2f}"
            )
            return summary

        except Exception as e:
            logger.warning(f"Failed to generate decision summary: {e}")
            return None

    async def _emit_preview_signal(
        self,
        discussion_round: DiscussionRound,
        strategies: list[ArenaStrategy],
    ) -> dict[str, Any] | None:
        """Emit instant rule-based preview signal via SSE.

        This runs in <100ms using only vote counting from metadata,
        giving the user a fast "whoa" signal while the full LLM
        synthesis runs in the background (10-30s).

        The frontend shows this as a "预览信号" badge that upgrades
        to the final signal when decision_summary arrives.
        """
        try:
            summarizer = get_decision_summarizer()
            vote_result = summarizer._count_votes(discussion_round.messages)
            key_arguments = summarizer._extract_key_arguments(discussion_round.messages)

            total = (
                vote_result["bull_count"]
                + vote_result["bear_count"]
                + vote_result["neutral_count"]
            )
            if total == 0:
                return None

            # Determine preview signal from votes only
            bull = vote_result["bull_count"]
            bear = vote_result["bear_count"]

            if bull > bear and bull / total >= 0.5:
                signal = "buy"
                confidence = min(bull / total, 0.8)
            elif bear > bull and bear / total >= 0.5:
                signal = "sell"
                confidence = min(bear / total, 0.8)
            else:
                signal = "hold"
                confidence = 0.4

            preview = {
                "signal": signal.upper(),
                "confidence": round(confidence, 2),
                "bull_count": bull,
                "bear_count": bear,
                "neutral_count": vote_result["neutral_count"],
                "is_preview": True,
            }

            # Determine stock code
            stock_code = ""
            if strategies:
                symbols = strategies[0].symbols
                if symbols:
                    stock_code = symbols[0]

            await self.stream_processor.publish_system(
                f"## 预览信号: {signal.upper()} ({stock_code})\n"
                f"- 置信度: {confidence:.0%} (基于投票)\n"
                f"- 看多: {bull} | 看空: {bear} | 中性: {vote_result['neutral_count']}\n"
                f"- ⏳ 完整分析生成中...",
                metadata={
                    "type": "preview_signal",
                    "signal": signal.upper(),
                    "confidence": round(confidence, 2),
                    "bull_count": bull,
                    "bear_count": bear,
                    "neutral_count": vote_result["neutral_count"],
                    "is_preview": True,
                    "stock_code": stock_code,
                },
            )

            logger.info(
                f"Emitted preview signal: {signal.upper()} "
                f"(confidence={confidence:.2f}, votes={total})"
            )
            return preview

        except Exception as e:
            logger.warning(f"Failed to emit preview signal: {e}")
            return None

    async def refine_strategies(
        self,
        strategies: list[ArenaStrategy],
        discussion_round: DiscussionRound,
    ) -> list[ArenaStrategy]:
        """Refine strategies based on discussion results.

        Args:
            strategies: Original strategies
            discussion_round: Completed discussion round

        Returns:
            Refined strategies
        """
        refined_strategies = []

        # Collect critiques from discussion messages
        critiques_by_strategy: dict[str, list[dict[str, Any]]] = {
            s.id: [] for s in strategies
        }

        for message in discussion_round.messages:
            if message.message_type == MessageType.ARGUMENT:
                target_id = message.metadata.get("target_strategy_id")
                if target_id and target_id in critiques_by_strategy:
                    critiques_by_strategy[target_id].append(
                        {
                            "agent_id": message.agent_id,
                            "content": message.content,
                        }
                    )

        # Refine each strategy
        for strategy in strategies:
            owner_agent = self.agents.get(strategy.agent_id)
            if not owner_agent:
                # Find any generator agent
                owner_agent = next(
                    (
                        a
                        for a in self.agents.values()
                        if "generator" in a.role.value.lower()
                    ),
                    list(self.agents.values())[0] if self.agents else None,
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
        tasks: list,
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

    def get_agent(self, agent_id: str) -> ArenaAgentBase | None:
        """Get an agent by ID."""
        return self.agents.get(agent_id)

    def get_all_agents(self) -> list[ArenaAgentBase]:
        """Get all agents."""
        return list(self.agents.values())
