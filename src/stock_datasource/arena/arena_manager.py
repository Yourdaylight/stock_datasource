"""
Multi-Agent Arena Manager

The main orchestrator for the multi-agent strategy competition system.
Coordinates all arena lifecycle operations.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import (
    Arena,
    ArenaConfig,
    ArenaState,
    ArenaStrategy,
    CompetitionStage,
    DiscussionMode,
    DiscussionRound,
    EvaluationPeriod,
    StrategyEvaluation,
)
from .agents import create_agent_from_config, ArenaAgentBase
from .discussion_orchestrator import AgentDiscussionOrchestrator
from .competition_engine import StrategyCompetitionEngine
from .stream_processor import ThinkingStreamProcessor
from .persistence import get_arena_repository, get_strategy_repository
from .exceptions import ArenaNotFoundError, ArenaStateError

logger = logging.getLogger(__name__)


class MultiAgentArena:
    """Main orchestrator for multi-agent strategy competition.
    
    Lifecycle:
    1. Create arena with configuration
    2. Initialize agents
    3. Generate initial strategies
    4. Run discussion rounds
    5. Execute backtests
    6. Promote to simulated trading
    7. Periodic evaluation and elimination
    8. Strategy replenishment
    
    The entire process is async and supports:
    - Real-time thinking stream output
    - Background execution
    - Pause/resume capability
    """
    
    def __init__(self, config: ArenaConfig, user_id: str = ""):
        self.arena = Arena.from_config(config, user_id=user_id)
        self.stream_processor = ThinkingStreamProcessor(self.arena.id)
        
        # Sub-components
        self.discussion_orchestrator: Optional[AgentDiscussionOrchestrator] = None
        self.competition_engine: Optional[StrategyCompetitionEngine] = None
        
        # State tracking
        self._task: Optional[asyncio.Task] = None
        self._paused = False
        self._stop_requested = False
        
        # Store reference
        self._repo = get_arena_repository()
        self._strategy_repo = get_strategy_repository()
        
        # Save arena
        self._repo.create(self.arena)
    
    @property
    def id(self) -> str:
        """Get arena ID."""
        return self.arena.id
    
    @property
    def user_id(self) -> str:
        """Get arena user ID."""
        return self.arena.user_id
    
    @property
    def state(self) -> ArenaState:
        """Get current arena state."""
        return self.arena.state
    
    def _set_state(self, state: ArenaState) -> None:
        """Set arena state and persist."""
        self.arena.state = state
        self.arena.updated_at = datetime.now()
        self._repo.update(self.arena)
    
    async def initialize(self) -> None:
        """Initialize the arena and all components."""
        logger.info(f"Initializing arena {self.arena.id}")
        self._set_state(ArenaState.INITIALIZING)
        
        await self.stream_processor.publish_system(
            f"## 竞技场初始化\n"
            f"- 名称: {self.arena.config.name}\n"
            f"- Agent数量: {self.arena.config.agent_count}\n"
            f"- 目标股票: {len(self.arena.config.symbols)} 只",
        )
        
        # Initialize discussion orchestrator (creates agents)
        self.discussion_orchestrator = AgentDiscussionOrchestrator(
            arena=self.arena,
            stream_processor=self.stream_processor,
        )
        
        # Initialize competition engine
        self.competition_engine = StrategyCompetitionEngine(
            arena=self.arena,
            stream_processor=self.stream_processor,
        )
        
        await self.stream_processor.publish_system(
            f"## 初始化完成\n"
            f"- {len(self.discussion_orchestrator.agents)} 个Agent就绪",
        )
        
        self._set_state(ArenaState.CREATED)
    
    async def start(self) -> None:
        """Start the arena competition.
        
        This kicks off the async competition loop.
        """
        if self.arena.state not in [ArenaState.CREATED, ArenaState.PAUSED]:
            raise ArenaStateError(
                arena_id=self.arena.id,
                current_state=self.arena.state.value,
                expected_states=["created", "paused"],
                operation="start",
            )
        
        self.arena.started_at = self.arena.started_at or datetime.now()
        self._paused = False
        self._stop_requested = False
        
        # Start competition in background
        self._task = asyncio.create_task(self._run_competition_loop())
    
    async def pause(self) -> None:
        """Pause the arena competition."""
        if self.arena.state not in [ArenaState.DISCUSSING, ArenaState.BACKTESTING, ArenaState.SIMULATING]:
            raise ArenaStateError(
                arena_id=self.arena.id,
                current_state=self.arena.state.value,
                expected_states=["discussing", "backtesting", "simulating"],
                operation="pause",
            )
        
        self._paused = True
        self._set_state(ArenaState.PAUSED)
        
        await self.stream_processor.publish_system("## 竞技场已暂停")
    
    async def resume(self) -> None:
        """Resume paused arena."""
        if self.arena.state != ArenaState.PAUSED:
            raise ArenaStateError(
                arena_id=self.arena.id,
                current_state=self.arena.state.value,
                expected_states=["paused"],
                operation="resume",
            )
        
        self._paused = False
        await self.stream_processor.publish_system("## 竞技场已恢复")
        
        # Resume competition
        self._task = asyncio.create_task(self._run_competition_loop())
    
    async def stop(self) -> None:
        """Stop the arena competition."""
        self._stop_requested = True
        
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.arena.completed_at = datetime.now()
        self._set_state(ArenaState.COMPLETED)
        
        await self.stream_processor.publish_system("## 竞技场已停止")
    
    async def _run_competition_loop(self) -> None:
        """Main competition loop."""
        try:
            # Phase 1: Generate initial strategies
            if not self.arena.strategies:
                await self._generate_initial_strategies()
            
            # Phase 2: Discussion rounds
            await self._run_discussion_phase()
            
            # Phase 3: Backtest
            await self._run_backtest_phase()
            
            # Phase 4: Simulated trading and periodic evaluation
            await self._run_simulation_phase()
            
            # Complete
            self.arena.completed_at = datetime.now()
            self._set_state(ArenaState.COMPLETED)
            
            await self.stream_processor.publish_system(
                f"## 竞技场完成\n"
                f"- 总持续时间: {self.arena.duration_seconds / 60:.1f} 分钟\n"
                f"- 总讨论轮次: {self.arena.total_rounds}\n"
                f"- 最终存活策略: {self.arena.active_strategy_count}",
            )
            
        except asyncio.CancelledError:
            logger.info(f"Arena {self.arena.id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Arena {self.arena.id} failed: {e}")
            self.arena.last_error = str(e)
            self.arena.error_count += 1
            self._set_state(ArenaState.FAILED)
            
            await self.stream_processor.publish_error(
                f"竞技场运行失败: {str(e)}",
                metadata={"error": str(e)},
            )
            raise
    
    async def _generate_initial_strategies(self) -> None:
        """Generate initial strategies from all agents."""
        await self.stream_processor.publish_system(
            "## 阶段1: 初始策略生成",
        )
        
        self._set_state(ArenaState.DISCUSSING)
        
        # Get market context
        market_context = await self._get_market_context()
        
        # Each agent generates a strategy
        for agent in self.discussion_orchestrator.get_all_agents():
            if self._paused or self._stop_requested:
                return
            
            try:
                agent.set_market_context(market_context)
                strategy = await agent.generate_strategy(
                    symbols=self.arena.config.symbols,
                    market_context=market_context,
                )
                
                self.arena.strategies.append(strategy)
                self._strategy_repo.create(strategy)
                
            except Exception as e:
                logger.warning(f"Agent {agent.agent_id} failed to generate strategy: {e}")
        
        await self.stream_processor.publish_system(
            f"## 初始策略生成完成\n生成 {len(self.arena.strategies)} 个策略",
        )
    
    async def _run_discussion_phase(self) -> None:
        """Run all discussion rounds."""
        await self.stream_processor.publish_system(
            "## 阶段2: 多Agent讨论",
        )
        
        # Get market context
        market_context = await self._get_market_context()
        
        # Run each discussion mode
        modes = self.arena.config.discussion.modes
        
        for mode in modes:
            if self._paused or self._stop_requested:
                return
            
            discussion_round = await self.discussion_orchestrator.run_discussion(
                strategies=self.arena.strategies,
                mode=mode,
                market_context=market_context,
            )
            
            self.arena.discussion_rounds.append(discussion_round)
            self.arena.current_round_id = discussion_round.id
            
            # Refine strategies based on discussion
            self.arena.strategies = await self.discussion_orchestrator.refine_strategies(
                strategies=self.arena.strategies,
                discussion_round=discussion_round,
            )
            
            # Update persisted strategies
            for strategy in self.arena.strategies:
                self._strategy_repo.update(strategy)
    
    async def _run_backtest_phase(self) -> None:
        """Run backtest stage."""
        await self.stream_processor.publish_system(
            "## 阶段3: 策略回测",
        )
        
        self._set_state(ArenaState.BACKTESTING)
        
        # Run backtests
        results = await self.competition_engine.run_backtest_stage(
            strategies=self.arena.strategies,
        )
        
        # Store results
        backtest_results = {
            strategy.id: result
            for strategy, result in results
        }
        
        # Evaluate and rank
        evaluations = await self.competition_engine.evaluate_strategies(
            strategies=self.arena.strategies,
            backtest_results=backtest_results,
            period=EvaluationPeriod.DAILY,
        )
        
        self.arena.evaluations.extend(evaluations)
        self.arena.last_evaluation = datetime.now()
        
        # Promote to simulated
        self.arena.strategies = await self.competition_engine.promote_to_simulated(
            strategies=self.arena.strategies,
            backtest_results=backtest_results,
        )
    
    async def _run_simulation_phase(self) -> None:
        """Run simulated trading phase with periodic evaluation."""
        await self.stream_processor.publish_system(
            "## 阶段4: 模拟盘竞争",
        )
        
        self._set_state(ArenaState.SIMULATING)
        
        # Simulate for configured duration
        duration_days = self.arena.config.competition.simulated_duration_days
        
        await self.stream_processor.publish_system(
            f"模拟盘周期: {duration_days} 天",
        )
        
        # In a real implementation, this would run actual simulated trading
        # For now, we simulate the evaluation cycle
        
        for day in range(duration_days):
            if self._paused or self._stop_requested:
                return
            
            # Daily evaluation (no elimination)
            if day > 0:
                await self._perform_evaluation(EvaluationPeriod.DAILY)
            
            # Weekly evaluation (every 7 days)
            if day > 0 and day % 7 == 0:
                await self._perform_evaluation(EvaluationPeriod.WEEKLY)
            
            # Monthly evaluation (every 30 days)
            if day > 0 and day % 30 == 0:
                await self._perform_evaluation(EvaluationPeriod.MONTHLY)
            
            # Small delay to simulate passage of time (for demo purposes)
            await asyncio.sleep(0.1)
    
    async def _perform_evaluation(self, period: EvaluationPeriod) -> None:
        """Perform periodic evaluation."""
        self._set_state(ArenaState.EVALUATING)
        
        # Get current results (synthetic for demo)
        backtest_results = {
            s.id: await self.competition_engine._generate_synthetic_backtest(s)
            for s in self.arena.strategies
            if s.is_active
        }
        
        # Evaluate
        evaluations = await self.competition_engine.evaluate_strategies(
            strategies=self.arena.strategies,
            backtest_results=backtest_results,
            period=period,
        )
        
        self.arena.evaluations.extend(evaluations)
        self.arena.last_evaluation = datetime.now()
        
        # Eliminate if weekly/monthly
        if period in [EvaluationPeriod.WEEKLY, EvaluationPeriod.MONTHLY]:
            surviving, eliminated = await self.competition_engine.eliminate_strategies(
                strategies=self.arena.strategies,
                evaluations=evaluations,
                period=period,
            )
            
            self.arena.eliminated_strategies.extend(eliminated)
            
            # Replenish if needed
            if len(surviving) < self.arena.config.agent_count:
                new_strategies = await self.competition_engine.replenish_strategies(
                    current_count=len(surviving),
                    target_count=self.arena.config.agent_count,
                    eliminated_strategies=self.arena.eliminated_strategies,
                )
                surviving.extend(new_strategies)
            
            self.arena.strategies = surviving
        
        self._set_state(ArenaState.SIMULATING)
    
    async def _get_market_context(self) -> Dict[str, Any]:
        """Get current market context for agents."""
        # In production, this would fetch real market data
        # For now, return a placeholder
        return {
            "market_summary": "市场整体震荡，结构性行情为主",
            "technical": {
                "trend": "sideways",
                "volatility": "medium",
            },
            "sentiment": {
                "overall": "neutral",
                "north_flow": "positive",
            },
            "timestamp": datetime.now().isoformat(),
        }
    
    # =========================================================================
    # Public API methods
    # =========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get arena status."""
        return {
            "id": self.arena.id,
            "user_id": self.arena.user_id,
            "name": self.arena.config.name,
            "state": self.arena.state.value,
            "active_strategies": self.arena.active_strategy_count,
            "total_strategies": len(self.arena.strategies),
            "eliminated_strategies": len(self.arena.eliminated_strategies),
            "discussion_rounds": self.arena.total_rounds,
            "last_evaluation": self.arena.last_evaluation.isoformat() if self.arena.last_evaluation else None,
            "duration_seconds": self.arena.duration_seconds,
            "error_count": self.arena.error_count,
            "last_error": self.arena.last_error,
        }
    
    def get_strategies(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get strategies in the arena."""
        strategies = self.arena.strategies
        if active_only:
            strategies = [s for s in strategies if s.is_active]
        return [s.to_dict() for s in strategies]
    
    def get_leaderboard(self) -> List[Dict[str, Any]]:
        """Get current leaderboard."""
        leaderboard = self.arena.get_leaderboard()
        return [
            {
                "rank": i + 1,
                "strategy_id": s.id,
                "name": s.name,
                "agent_id": s.agent_id,
                "agent_role": s.agent_role,
                "score": s.current_score,
                "stage": s.stage.value if hasattr(s.stage, 'value') else str(s.stage),
            }
            for i, s in enumerate(leaderboard)
        ]
    
    def get_discussion_history(self) -> List[Dict[str, Any]]:
        """Get discussion history."""
        return [r.to_dict() for r in self.arena.discussion_rounds]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert arena to dictionary."""
        return self.arena.to_dict()


# =============================================================================
# Factory Functions
# =============================================================================

_active_arenas: Dict[str, MultiAgentArena] = {}


def create_arena(config: ArenaConfig, user_id: str = "") -> MultiAgentArena:
    """Create a new arena.
    
    Args:
        config: Arena configuration
        user_id: User ID who creates this arena (for data isolation)
        
    Returns:
        Created MultiAgentArena instance
    """
    arena = MultiAgentArena(config, user_id=user_id)
    _active_arenas[arena.id] = arena
    return arena


def get_arena(arena_id: str) -> MultiAgentArena:
    """Get an arena by ID.
    
    Args:
        arena_id: Arena ID
        
    Returns:
        MultiAgentArena instance
        
    Raises:
        ArenaNotFoundError: If arena not found
    """
    if arena_id not in _active_arenas:
        raise ArenaNotFoundError(arena_id)
    return _active_arenas[arena_id]


def list_arenas(user_id: str = None) -> List[Dict[str, Any]]:
    """List all active arenas.
    
    Args:
        user_id: If provided, only return arenas belonging to this user.
        
    Returns:
        List of arena status dictionaries
    """
    arenas = _active_arenas.values()
    if user_id:
        arenas = [a for a in arenas if a.user_id == user_id]
    return [arena.get_status() for arena in arenas]


def delete_arena(arena_id: str) -> bool:
    """Delete an arena.
    
    Args:
        arena_id: Arena ID
        
    Returns:
        True if deleted
    """
    if arena_id in _active_arenas:
        del _active_arenas[arena_id]
        return True
    return False
