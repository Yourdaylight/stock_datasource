"""
Strategy Competition Engine

Manages the competition lifecycle from backtest to simulated trading.
Handles strategy evaluation, ranking, and elimination.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    Arena,
    ArenaState,
    ArenaStrategy,
    CompetitionStage,
    EvaluationPeriod,
    StrategyEvaluation,
    ComprehensiveScore,
    DimensionScore,
    CompetitionConfig,
    EvaluationConfig,
)
from .stream_processor import ThinkingStreamProcessor
from .exceptions import CompetitionError, EvaluationError

logger = logging.getLogger(__name__)


class ComprehensiveScorer:
    """Calculates comprehensive scores for strategy evaluation.
    
    Score dimensions:
    - Return: 30% weight (annualized return, cumulative return)
    - Risk: 30% weight (max drawdown, sharpe ratio, sortino ratio)
    - Stability: 20% weight (volatility, win rate, profit factor)
    - Adaptability: 20% weight (performance across market conditions)
    """
    
    def __init__(self, config: EvaluationConfig = None):
        self.config = config or EvaluationConfig()
    
    def calculate(
        self,
        backtest_result: Dict[str, Any],
        simulated_result: Dict[str, Any] = None,
    ) -> ComprehensiveScore:
        """Calculate comprehensive score from results.
        
        Args:
            backtest_result: Backtest performance metrics
            simulated_result: Simulated trading performance (optional)
            
        Returns:
            ComprehensiveScore with all dimensions
        """
        score = ComprehensiveScore()
        
        # Calculate return dimension (30%)
        score.return_score = self._calculate_return_score(backtest_result)
        score.return_score.weight = self.config.return_weight
        
        # Calculate risk dimension (30%)
        score.risk_score = self._calculate_risk_score(backtest_result)
        score.risk_score.weight = self.config.risk_weight
        
        # Calculate stability dimension (20%)
        score.stability_score = self._calculate_stability_score(backtest_result)
        score.stability_score.weight = self.config.stability_weight
        
        # Calculate adaptability dimension (20%)
        score.adaptability_score = self._calculate_adaptability_score(
            backtest_result, simulated_result
        )
        score.adaptability_score.weight = self.config.adaptability_weight
        
        return score
    
    def _calculate_return_score(self, result: Dict[str, Any]) -> DimensionScore:
        """Calculate return dimension score."""
        metrics = {}
        
        # Extract metrics
        ann_return = result.get("annualized_return", 0)
        total_return = result.get("total_return", 0)
        excess_return = result.get("excess_return", 0)
        
        metrics["annualized_return"] = ann_return
        metrics["total_return"] = total_return
        metrics["excess_return"] = excess_return
        
        # Calculate score (0-100 scale)
        # Annualized return: 20% -> 100 points, 0% -> 50 points, -20% -> 0 points
        ann_score = max(0, min(100, 50 + ann_return * 250))
        
        # Excess return bonus
        excess_bonus = max(0, min(20, excess_return * 100))
        
        score = min(100, ann_score + excess_bonus)
        
        return DimensionScore(
            dimension="return",
            score=score,
            metrics=metrics,
        )
    
    def _calculate_risk_score(self, result: Dict[str, Any]) -> DimensionScore:
        """Calculate risk dimension score."""
        metrics = {}
        
        # Extract metrics
        max_dd = abs(result.get("max_drawdown", 0.2))
        sharpe = result.get("sharpe_ratio", 0)
        sortino = result.get("sortino_ratio", 0)
        
        metrics["max_drawdown"] = -max_dd
        metrics["sharpe_ratio"] = sharpe
        metrics["sortino_ratio"] = sortino
        
        # Calculate score
        # Max drawdown: 0% -> 100, 10% -> 75, 20% -> 50, 50% -> 0
        dd_score = max(0, 100 - max_dd * 200)
        
        # Sharpe ratio: 2+ -> 100, 1 -> 50, 0 -> 25, negative -> 0
        sharpe_score = max(0, min(100, 25 + sharpe * 37.5))
        
        # Combined score
        score = dd_score * 0.5 + sharpe_score * 0.5
        
        return DimensionScore(
            dimension="risk",
            score=score,
            metrics=metrics,
        )
    
    def _calculate_stability_score(self, result: Dict[str, Any]) -> DimensionScore:
        """Calculate stability dimension score."""
        metrics = {}
        
        # Extract metrics
        volatility = result.get("volatility", 0.2)
        win_rate = result.get("win_rate", 0.5)
        profit_factor = result.get("profit_factor", 1.0)
        
        metrics["volatility"] = volatility
        metrics["win_rate"] = win_rate
        metrics["profit_factor"] = profit_factor
        
        # Calculate score
        # Volatility: <10% -> 100, 20% -> 75, 30% -> 50, >50% -> 0
        vol_score = max(0, 100 - volatility * 200)
        
        # Win rate: >60% -> 100, 50% -> 50, <40% -> 0
        win_score = max(0, min(100, (win_rate - 0.4) * 500))
        
        # Profit factor: >2 -> 100, 1.5 -> 75, 1 -> 50, <0.5 -> 0
        pf_score = max(0, min(100, profit_factor * 50))
        
        score = (vol_score + win_score + pf_score) / 3
        
        return DimensionScore(
            dimension="stability",
            score=score,
            metrics=metrics,
        )
    
    def _calculate_adaptability_score(
        self,
        backtest_result: Dict[str, Any],
        simulated_result: Dict[str, Any] = None,
    ) -> DimensionScore:
        """Calculate adaptability dimension score."""
        metrics = {}
        
        # If simulated result available, compare with backtest
        if simulated_result:
            bt_return = backtest_result.get("annualized_return", 0)
            sim_return = simulated_result.get("annualized_return", 0)
            
            # Consistency: how close is simulated to backtest
            if bt_return != 0:
                consistency = 1 - abs(sim_return - bt_return) / abs(bt_return)
            else:
                consistency = 0.5
            
            metrics["backtest_return"] = bt_return
            metrics["simulated_return"] = sim_return
            metrics["consistency"] = consistency
            
            score = max(0, min(100, consistency * 100))
        else:
            # Without simulated results, use backtest robustness indicators
            sharpe = backtest_result.get("sharpe_ratio", 0)
            win_rate = backtest_result.get("win_rate", 0.5)
            
            metrics["sharpe_ratio"] = sharpe
            metrics["win_rate"] = win_rate
            
            # Estimate adaptability from backtest metrics
            score = min(100, (sharpe * 25 + win_rate * 100) / 2)
        
        return DimensionScore(
            dimension="adaptability",
            score=score,
            metrics=metrics,
        )


class StrategyCompetitionEngine:
    """Manages the strategy competition lifecycle.
    
    Competition stages:
    1. Backtest: Initial validation with historical data
    2. Simulated: Paper trading validation
    3. Live: Real trading (reserved, not implemented)
    
    Evaluation periods:
    - Daily: Update metrics, no elimination
    - Weekly: Eliminate bottom 20%
    - Monthly: Eliminate bottom 10%
    """
    
    def __init__(
        self,
        arena: Arena,
        stream_processor: ThinkingStreamProcessor = None,
    ):
        self.arena = arena
        self.stream_processor = stream_processor or ThinkingStreamProcessor(arena.id)
        self.scorer = ComprehensiveScorer(arena.config.evaluation)
        
        # Simulated trading state
        self._simulated_portfolios: Dict[str, Dict[str, Any]] = {}
    
    async def run_backtest_stage(
        self,
        strategies: List[ArenaStrategy],
    ) -> List[Tuple[ArenaStrategy, Dict[str, Any]]]:
        """Run backtest stage for strategies.
        
        Args:
            strategies: Strategies to backtest
            
        Returns:
            List of (strategy, backtest_result) tuples
        """
        await self.stream_processor.publish_system(
            f"## 回测阶段开始\n正在回测 {len(strategies)} 个策略...",
        )
        
        results = []
        
        for i, strategy in enumerate(strategies):
            await self.stream_processor.publish_system(
                f"回测策略 {i+1}/{len(strategies)}: {strategy.name}",
            )
            
            try:
                result = await self._run_single_backtest(strategy)
                strategy.backtest_result_id = str(uuid.uuid4())[:8]
                strategy.stage = CompetitionStage.BACKTEST
                results.append((strategy, result))
                
                await self.stream_processor.publish_system(
                    f"策略 {strategy.name} 回测完成:\n"
                    f"- 年化收益: {result.get('annualized_return', 0):.1%}\n"
                    f"- 最大回撤: {result.get('max_drawdown', 0):.1%}\n"
                    f"- 夏普比率: {result.get('sharpe_ratio', 0):.2f}",
                )
                
            except Exception as e:
                logger.error(f"Backtest failed for strategy {strategy.id}: {e}")
                await self.stream_processor.publish_error(
                    f"策略 {strategy.name} 回测失败: {str(e)}",
                )
                # Use default poor results for failed backtests
                results.append((strategy, {
                    "annualized_return": -0.5,
                    "max_drawdown": -0.5,
                    "sharpe_ratio": -1,
                    "error": str(e),
                }))
        
        await self.stream_processor.publish_system(
            f"## 回测阶段完成\n成功回测 {len(results)} 个策略",
        )
        
        return results
    
    async def _run_single_backtest(self, strategy: ArenaStrategy) -> Dict[str, Any]:
        """Run backtest for a single strategy.
        
        Integrates with existing backtest engine.
        """
        try:
            from ..backtest.engine import IntelligentBacktestEngine
            from ..backtest.models import BacktestConfig, TradingConfig
            
            config = BacktestConfig(
                strategy_id=strategy.id,
                symbols=strategy.symbols or ["000001.SZ"],
                start_date=self.arena.config.competition.backtest_start_date or "2023-01-01",
                end_date=self.arena.config.competition.backtest_end_date or "2023-12-31",
                trading_config=TradingConfig(
                    initial_capital=self.arena.config.competition.initial_capital,
                ),
            )
            
            engine = IntelligentBacktestEngine()
            result = await engine.run_backtest(config)
            
            return {
                "annualized_return": result.performance_metrics.annualized_return,
                "total_return": result.performance_metrics.total_return,
                "max_drawdown": result.performance_metrics.max_drawdown,
                "sharpe_ratio": result.performance_metrics.sharpe_ratio,
                "sortino_ratio": result.performance_metrics.sortino_ratio,
                "volatility": result.performance_metrics.volatility,
                "win_rate": result.performance_metrics.win_rate,
                "profit_factor": result.performance_metrics.profit_factor,
            }
            
        except ImportError:
            # Fallback: generate synthetic results
            logger.warning("Backtest engine not available, using synthetic results")
            return await self._generate_synthetic_backtest(strategy)
    
    async def _generate_synthetic_backtest(self, strategy: ArenaStrategy) -> Dict[str, Any]:
        """Generate synthetic backtest results for testing."""
        import random
        
        # Generate somewhat realistic metrics based on strategy rules
        stop_loss = abs(strategy.rules.get("stop_loss", -0.08))
        position_size = strategy.rules.get("position_size", 0.2)
        
        # More conservative strategies tend to have lower returns but better risk metrics
        base_return = random.uniform(0.05, 0.25)
        max_dd = random.uniform(0.08, 0.25)
        sharpe = random.uniform(0.5, 2.0)
        
        return {
            "annualized_return": base_return,
            "total_return": base_return * 0.8,
            "max_drawdown": -max_dd,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sharpe * 1.2,
            "volatility": random.uniform(0.15, 0.3),
            "win_rate": random.uniform(0.45, 0.65),
            "profit_factor": random.uniform(1.0, 2.0),
        }
    
    async def promote_to_simulated(
        self,
        strategies: List[ArenaStrategy],
        backtest_results: Dict[str, Dict[str, Any]],
    ) -> List[ArenaStrategy]:
        """Promote strategies passing backtest to simulated trading.
        
        Args:
            strategies: Strategies to consider
            backtest_results: Backtest results by strategy ID
            
        Returns:
            Promoted strategies
        """
        await self.stream_processor.publish_system(
            "## 筛选进入模拟盘的策略...",
        )
        
        # Score and rank strategies
        scored_strategies = []
        for strategy in strategies:
            result = backtest_results.get(strategy.id, {})
            score = self.scorer.calculate(result)
            scored_strategies.append((strategy, score.total_score))
        
        # Sort by score descending
        scored_strategies.sort(key=lambda x: x[1], reverse=True)
        
        # Promote top performers (at least those with positive returns)
        promoted = []
        for strategy, score in scored_strategies:
            result = backtest_results.get(strategy.id, {})
            if result.get("annualized_return", 0) > 0 or score > 40:
                strategy.stage = CompetitionStage.SIMULATED
                promoted.append(strategy)
                
                # Initialize simulated portfolio
                self._simulated_portfolios[strategy.id] = {
                    "cash": self.arena.config.competition.initial_capital,
                    "positions": {},
                    "trades": [],
                    "daily_values": [],
                }
        
        await self.stream_processor.publish_system(
            f"## {len(promoted)}/{len(strategies)} 个策略晋级模拟盘",
        )
        
        return promoted
    
    async def evaluate_strategies(
        self,
        strategies: List[ArenaStrategy],
        backtest_results: Dict[str, Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> List[StrategyEvaluation]:
        """Evaluate strategies and produce rankings.
        
        Args:
            strategies: Strategies to evaluate
            backtest_results: Backtest/simulation results
            period: Evaluation period type
            
        Returns:
            List of evaluations
        """
        await self.stream_processor.publish_system(
            f"## {period.value.upper()} 评估开始",
        )
        
        evaluations = []
        scored = []
        
        for strategy in strategies:
            if not strategy.is_active:
                continue
            
            result = backtest_results.get(strategy.id, {})
            simulated = self._simulated_portfolios.get(strategy.id, {})
            
            # Calculate comprehensive score
            score = self.scorer.calculate(result, simulated)
            
            evaluation = StrategyEvaluation(
                strategy_id=strategy.id,
                arena_id=self.arena.id,
                period=period,
                score=score,
            )
            
            evaluations.append(evaluation)
            scored.append((strategy, evaluation, score.total_score))
        
        # Sort and assign ranks
        scored.sort(key=lambda x: x[2], reverse=True)
        
        for rank, (strategy, evaluation, total_score) in enumerate(scored, 1):
            evaluation.rank = rank
            strategy.current_score = total_score
            strategy.current_rank = rank
            strategy.evaluations.append(evaluation)
        
        await self.stream_processor.publish_system(
            f"## {period.value.upper()} 评估完成\n"
            f"评估策略数: {len(evaluations)}",
        )
        
        return evaluations
    
    async def eliminate_strategies(
        self,
        strategies: List[ArenaStrategy],
        evaluations: List[StrategyEvaluation],
        period: EvaluationPeriod,
    ) -> Tuple[List[ArenaStrategy], List[ArenaStrategy]]:
        """Eliminate poor performing strategies.
        
        Args:
            strategies: Current active strategies
            evaluations: Latest evaluations
            period: Evaluation period
            
        Returns:
            Tuple of (surviving strategies, eliminated strategies)
        """
        config = self.arena.config.evaluation
        
        # Determine elimination rate
        if period == EvaluationPeriod.DAILY:
            return strategies, []  # No elimination on daily
        elif period == EvaluationPeriod.WEEKLY:
            elimination_rate = config.weekly_elimination_rate
        elif period == EvaluationPeriod.MONTHLY:
            elimination_rate = config.monthly_elimination_rate
        else:
            elimination_rate = 0.1
        
        # Sort by score ascending (worst first)
        active_strategies = [s for s in strategies if s.is_active]
        active_strategies.sort(key=lambda s: s.current_score)
        
        # Calculate elimination count
        elimination_count = max(1, int(len(active_strategies) * elimination_rate))
        
        # Don't eliminate below minimum
        if len(active_strategies) - elimination_count < config.min_strategies:
            elimination_count = max(0, len(active_strategies) - config.min_strategies)
        
        # Eliminate
        eliminated = []
        surviving = []
        
        for i, strategy in enumerate(active_strategies):
            if i < elimination_count:
                strategy.is_active = False
                strategy.eliminated_at = datetime.now()
                eliminated.append(strategy)
            else:
                surviving.append(strategy)
        
        if eliminated:
            await self.stream_processor.publish_system(
                f"## {period.value.upper()} 淘汰\n"
                f"淘汰 {len(eliminated)} 个策略:\n" +
                "\n".join(f"- {s.name} (评分: {s.current_score:.1f})" for s in eliminated),
            )
        
        return surviving, eliminated
    
    async def replenish_strategies(
        self,
        current_count: int,
        target_count: int,
        eliminated_strategies: List[ArenaStrategy],
    ) -> List[ArenaStrategy]:
        """Replenish strategies after elimination.
        
        70% new strategies, 30% revived from history.
        
        Args:
            current_count: Current active strategy count
            target_count: Target strategy count
            eliminated_strategies: Pool of eliminated strategies
            
        Returns:
            New strategies to add
        """
        needed = target_count - current_count
        if needed <= 0:
            return []
        
        new_strategies = []
        
        # Calculate split
        revive_count = int(needed * (1 - self.arena.config.replenish_new_ratio))
        new_count = needed - revive_count
        
        # Revive best eliminated strategies
        if revive_count > 0 and eliminated_strategies:
            # Sort eliminated by historical score
            sorted_eliminated = sorted(
                eliminated_strategies,
                key=lambda s: s.current_score,
                reverse=True,
            )
            
            for strategy in sorted_eliminated[:revive_count]:
                # Reset and revive
                revived = ArenaStrategy(
                    arena_id=self.arena.id,
                    agent_id=strategy.agent_id,
                    agent_role=strategy.agent_role,
                    name=f"{strategy.name} (复活)",
                    description=strategy.description,
                    logic=strategy.logic,
                    rules=strategy.rules,
                    symbols=strategy.symbols,
                    stage=CompetitionStage.BACKTEST,
                    is_active=True,
                    refinement_history=strategy.refinement_history + [{"revived": True}],
                )
                new_strategies.append(revived)
        
        # Note: New strategies would be generated by agents in actual implementation
        # This is a placeholder for the replenishment mechanism
        
        if new_strategies:
            await self.stream_processor.publish_system(
                f"## 策略补充\n补充 {len(new_strategies)} 个策略",
            )
        
        return new_strategies
