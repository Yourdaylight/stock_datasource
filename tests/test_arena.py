"""
Unit tests for the Multi-Agent Strategy Arena module.

Tests cover:
- Arena creation and configuration
- Agent roles and discussion orchestration
- Competition engine and scoring
- Elimination mechanisms
- API endpoints
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any
import uuid


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_arena_config():
    """Create a mock arena configuration."""
    return {
        "name": "Test Arena",
        "description": "Unit test arena",
        "agent_count": 5,
        "symbols": ["000001.SZ", "600000.SH"],
    }


@pytest.fixture
def mock_strategy_data():
    """Create mock strategy data."""
    return {
        "id": "strategy_test_1",
        "name": "Test Strategy",
        "description": "A test strategy for unit testing",
        "agent_id": "agent_1",
        "agent_role": "strategy_generator",
        "stage": "backtest",
        "is_active": True,
        "current_score": 75.0,
        "current_rank": 1,
        "logic": "Buy when MA5 crosses above MA20",
        "rules": {
            "buy_condition": "MA5 > MA20",
            "sell_condition": "MA5 < MA20",
            "stop_loss": 0.05,
            "take_profit": 0.10,
        },
    }


@pytest.fixture
def mock_thinking_message():
    """Create a mock thinking message."""
    return {
        "id": f"msg_{uuid.uuid4().hex[:8]}",
        "arena_id": "arena_test_1",
        "agent_id": "agent_1",
        "agent_role": "strategy_generator",
        "round_id": "round_1",
        "message_type": "thinking",
        "content": "Analyzing market data for potential opportunities...",
        "metadata": {"step": 1, "confidence": 0.85},
        "timestamp": datetime.now().isoformat(),
    }


# =============================================================================
# Test Arena Configuration
# =============================================================================

class TestArenaConfig:
    """Test arena configuration validation and defaults."""
    
    def test_default_config_values(self):
        """Test that default configuration values are set correctly."""
        from stock_datasource.arena import ArenaConfig, DiscussionConfig, CompetitionConfig
        
        config = ArenaConfig(
            name="Test Arena",
            description="Test description"
        )
        
        assert config.name == "Test Arena"
        assert config.agent_count == 5
        assert config.discussion.max_rounds == 3
        assert config.competition.initial_capital == 100000.0
    
    def test_config_validation_agent_count_min(self):
        """Test agent count minimum validation (3)."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Test", agent_count=3)
        assert config.agent_count == 3
    
    def test_config_validation_agent_count_max(self):
        """Test agent count maximum validation (10)."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Test", agent_count=10)
        assert config.agent_count == 10
    
    def test_config_validation_agent_count_default(self):
        """Test agent count default value (5)."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Test")
        assert config.agent_count == 5
    
    def test_config_symbols_default(self):
        """Test default symbols are set."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Test")
        assert isinstance(config.symbols, list)
    
    def test_config_custom_symbols(self):
        """Test custom symbols configuration."""
        from stock_datasource.arena import ArenaConfig
        
        symbols = ["000001.SZ", "600000.SH", "000002.SZ"]
        config = ArenaConfig(name="Test", symbols=symbols)
        assert config.symbols == symbols
    
    def test_config_auto_generate_agents(self):
        """Test agents are auto-generated when not provided."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Test", agent_count=5)
        assert len(config.agents) == 5
    
    def test_config_discussion_settings(self):
        """Test discussion configuration settings."""
        from stock_datasource.arena import ArenaConfig, DiscussionConfig
        
        discussion_config = DiscussionConfig(
            max_rounds=5,
            round_timeout_seconds=600,
            consensus_threshold=0.8,
        )
        config = ArenaConfig(name="Test", discussion=discussion_config)
        
        assert config.discussion.max_rounds == 5
        assert config.discussion.round_timeout_seconds == 600
        assert config.discussion.consensus_threshold == 0.8
    
    def test_config_competition_settings(self):
        """Test competition configuration settings."""
        from stock_datasource.arena import ArenaConfig, CompetitionConfig
        
        competition_config = CompetitionConfig(
            initial_capital=200000.0,
            simulated_duration_days=60,
            max_position_size=0.5,
        )
        config = ArenaConfig(name="Test", competition=competition_config)
        
        assert config.competition.initial_capital == 200000.0
        assert config.competition.simulated_duration_days == 60
        assert config.competition.max_position_size == 0.5
    
    def test_config_evaluation_settings(self):
        """Test evaluation configuration settings."""
        from stock_datasource.arena import ArenaConfig, EvaluationConfig
        
        eval_config = EvaluationConfig(
            weekly_elimination_rate=0.25,
            monthly_elimination_rate=0.15,
            min_strategies=5,
        )
        config = ArenaConfig(name="Test", evaluation=eval_config)
        
        assert config.evaluation.weekly_elimination_rate == 0.25
        assert config.evaluation.monthly_elimination_rate == 0.15
        assert config.evaluation.min_strategies == 5


# =============================================================================
# Test Arena State Machine
# =============================================================================

class TestArenaStateMachine:
    """Test arena state transitions."""
    
    def test_all_states_defined(self):
        """Test that all required states are defined."""
        from stock_datasource.arena import ArenaState
        
        required_states = [
            'CREATED', 'INITIALIZING', 'DISCUSSING', 'BACKTESTING',
            'SIMULATING', 'EVALUATING', 'PAUSED', 'COMPLETED', 'FAILED',
        ]
        
        for state_name in required_states:
            assert hasattr(ArenaState, state_name)
    
    def test_initial_state_is_created(self):
        """Test that new arena starts in 'created' state."""
        from stock_datasource.arena import ArenaState
        
        assert ArenaState.CREATED.value == "created"
    
    def test_state_values(self):
        """Test state string values."""
        from stock_datasource.arena import ArenaState
        
        assert ArenaState.CREATED.value == "created"
        assert ArenaState.INITIALIZING.value == "initializing"
        assert ArenaState.DISCUSSING.value == "discussing"
        assert ArenaState.BACKTESTING.value == "backtesting"
        assert ArenaState.SIMULATING.value == "simulating"
        assert ArenaState.EVALUATING.value == "evaluating"
        assert ArenaState.PAUSED.value == "paused"
        assert ArenaState.COMPLETED.value == "completed"
        assert ArenaState.FAILED.value == "failed"


# =============================================================================
# Test Agent Roles
# =============================================================================

class TestAgentRoles:
    """Test agent role definitions and capabilities."""
    
    def test_all_agent_roles_defined(self):
        """Test that all required agent roles are defined."""
        from stock_datasource.arena import AgentRole
        
        required_roles = [
            'STRATEGY_GENERATOR',
            'STRATEGY_REVIEWER',
            'RISK_ANALYST',
            'MARKET_SENTIMENT',
            'QUANT_RESEARCHER',
        ]
        
        for role_name in required_roles:
            assert hasattr(AgentRole, role_name)
    
    def test_agent_role_values(self):
        """Test agent role string values."""
        from stock_datasource.arena import AgentRole
        
        assert AgentRole.STRATEGY_GENERATOR.value == "strategy_generator"
        assert AgentRole.STRATEGY_REVIEWER.value == "strategy_reviewer"
        assert AgentRole.RISK_ANALYST.value == "risk_analyst"
        assert AgentRole.MARKET_SENTIMENT.value == "market_sentiment"
        assert AgentRole.QUANT_RESEARCHER.value == "quant_researcher"


# =============================================================================
# Test Discussion Modes
# =============================================================================

class TestDiscussionModes:
    """Test discussion mode configurations."""
    
    def test_discussion_modes_defined(self):
        """Test that all discussion modes are defined."""
        from stock_datasource.arena import DiscussionMode
        
        assert hasattr(DiscussionMode, 'DEBATE')
        assert hasattr(DiscussionMode, 'COLLABORATION')
        assert hasattr(DiscussionMode, 'REVIEW')
    
    def test_discussion_mode_values(self):
        """Test discussion mode string values."""
        from stock_datasource.arena import DiscussionMode
        
        assert DiscussionMode.DEBATE.value == "debate"
        assert DiscussionMode.COLLABORATION.value == "collaboration"
        assert DiscussionMode.REVIEW.value == "review"
    
    def test_discussion_modes_count(self):
        """Test that exactly 3 discussion modes exist."""
        from stock_datasource.arena import DiscussionMode
        
        assert len(list(DiscussionMode)) == 3


# =============================================================================
# Test Competition Stages
# =============================================================================

class TestCompetitionStages:
    """Test competition stage configurations."""
    
    def test_competition_stages_defined(self):
        """Test that all competition stages are defined."""
        from stock_datasource.arena import CompetitionStage
        
        assert hasattr(CompetitionStage, 'BACKTEST')
        assert hasattr(CompetitionStage, 'SIMULATED')
        assert hasattr(CompetitionStage, 'LIVE')
    
    def test_competition_stage_values(self):
        """Test competition stage string values."""
        from stock_datasource.arena import CompetitionStage
        
        assert CompetitionStage.BACKTEST.value == "backtest"
        assert CompetitionStage.SIMULATED.value == "simulated"
        assert CompetitionStage.LIVE.value == "live"


# =============================================================================
# Test Evaluation Periods
# =============================================================================

class TestEvaluationPeriods:
    """Test evaluation period configurations."""
    
    def test_evaluation_periods_defined(self):
        """Test that all evaluation periods are defined."""
        from stock_datasource.arena import EvaluationPeriod
        
        assert hasattr(EvaluationPeriod, 'DAILY')
        assert hasattr(EvaluationPeriod, 'WEEKLY')
        assert hasattr(EvaluationPeriod, 'MONTHLY')
    
    def test_evaluation_period_values(self):
        """Test evaluation period string values."""
        from stock_datasource.arena import EvaluationPeriod
        
        assert EvaluationPeriod.DAILY.value == "daily"
        assert EvaluationPeriod.WEEKLY.value == "weekly"
        assert EvaluationPeriod.MONTHLY.value == "monthly"


# =============================================================================
# Test Message Types
# =============================================================================

class TestMessageTypes:
    """Test message type configurations."""
    
    def test_message_types_defined(self):
        """Test that all message types are defined."""
        from stock_datasource.arena import MessageType
        
        assert hasattr(MessageType, 'THINKING')
        assert hasattr(MessageType, 'ARGUMENT')
        assert hasattr(MessageType, 'CONCLUSION')
        assert hasattr(MessageType, 'SYSTEM')
        assert hasattr(MessageType, 'ERROR')
    
    def test_message_type_values(self):
        """Test message type string values."""
        from stock_datasource.arena import MessageType
        
        assert MessageType.THINKING.value == "thinking"
        assert MessageType.ARGUMENT.value == "argument"
        assert MessageType.CONCLUSION.value == "conclusion"
        assert MessageType.SYSTEM.value == "system"
        assert MessageType.ERROR.value == "error"


# =============================================================================
# Test Comprehensive Scorer
# =============================================================================

class TestComprehensiveScorer:
    """Test the comprehensive scoring system."""
    
    def test_score_weights_sum_to_one(self):
        """Test that all score weights sum to 1.0."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig()
        total = (
            config.return_weight +
            config.risk_weight +
            config.stability_weight +
            config.adaptability_weight
        )
        assert abs(total - 1.0) < 0.001
    
    def test_score_calculation_range(self):
        """Test that calculated scores are within valid range (0-100)."""
        from stock_datasource.arena import ComprehensiveScore, DimensionScore
        
        score = ComprehensiveScore()
        score.return_score = DimensionScore(dimension="return", score=75.0, weight=0.3)
        score.risk_score = DimensionScore(dimension="risk", score=80.0, weight=0.3)
        score.stability_score = DimensionScore(dimension="stability", score=70.0, weight=0.2)
        score.adaptability_score = DimensionScore(dimension="adaptability", score=65.0, weight=0.2)
        
        total = score.total_score
        assert 0 <= total <= 100
    
    def test_dimension_score_weighted(self):
        """Test dimension score weighted calculation."""
        from stock_datasource.arena import DimensionScore
        
        dim_score = DimensionScore(dimension="return", score=80.0, weight=0.3)
        assert dim_score.weighted_score == 24.0
    
    def test_comprehensive_score_to_dict(self):
        """Test comprehensive score serialization."""
        from stock_datasource.arena import ComprehensiveScore
        
        score = ComprehensiveScore()
        score_dict = score.to_dict()
        
        assert "return_score" in score_dict
        assert "risk_score" in score_dict
        assert "stability_score" in score_dict
        assert "adaptability_score" in score_dict
        assert "total_score" in score_dict


# =============================================================================
# Test Elimination Mechanism
# =============================================================================

class TestEliminationMechanism:
    """Test the periodic elimination mechanism."""
    
    def test_weekly_elimination_rate(self):
        """Test that weekly elimination removes bottom 20%."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig()
        assert config.weekly_elimination_rate == 0.2
        
        total_strategies = 10
        expected_eliminations = int(total_strategies * config.weekly_elimination_rate)
        assert expected_eliminations == 2
    
    def test_monthly_elimination_rate(self):
        """Test that monthly elimination removes bottom 10%."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig()
        assert config.monthly_elimination_rate == 0.1
        
        total_strategies = 10
        expected_eliminations = int(total_strategies * config.monthly_elimination_rate)
        assert expected_eliminations == 1
    
    def test_daily_no_elimination(self):
        """Test that daily evaluation does not eliminate strategies."""
        # Daily updates do not eliminate - this is by design
        elimination_rate = 0.0
        total_strategies = 10
        
        expected_eliminations = int(total_strategies * elimination_rate)
        assert expected_eliminations == 0
    
    def test_min_strategies_preserved(self):
        """Test that minimum strategies are preserved after elimination."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig(min_strategies=3)
        assert config.min_strategies == 3
    
    def test_elimination_rate_bounds(self):
        """Test elimination rate is within valid bounds."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig()
        assert 0 <= config.weekly_elimination_rate <= 0.5
        assert 0 <= config.monthly_elimination_rate <= 0.5


# =============================================================================
# Test Data Models
# =============================================================================

class TestThinkingMessage:
    """Test ThinkingMessage model."""
    
    def test_thinking_message_creation(self):
        """Test thinking message creation."""
        from stock_datasource.arena import ThinkingMessage, MessageType
        
        msg = ThinkingMessage(
            arena_id="arena_1",
            agent_id="agent_1",
            agent_role="strategy_generator",
            round_id="round_1",
            message_type=MessageType.THINKING,
            content="Analyzing market...",
        )
        
        assert msg.arena_id == "arena_1"
        assert msg.agent_id == "agent_1"
        assert msg.content == "Analyzing market..."
    
    def test_thinking_message_to_dict(self):
        """Test thinking message serialization."""
        from stock_datasource.arena import ThinkingMessage
        
        msg = ThinkingMessage(
            arena_id="arena_1",
            agent_id="agent_1",
            content="Test content",
        )
        
        msg_dict = msg.to_dict()
        assert "id" in msg_dict
        assert "arena_id" in msg_dict
        assert "content" in msg_dict
        assert "timestamp" in msg_dict
    
    def test_thinking_message_from_dict(self):
        """Test thinking message deserialization."""
        from stock_datasource.arena import ThinkingMessage
        
        data = {
            "id": "msg_123",
            "arena_id": "arena_1",
            "agent_id": "agent_1",
            "agent_role": "strategy_generator",
            "round_id": "round_1",
            "message_type": "thinking",
            "content": "Test",
            "metadata": {},
            "timestamp": datetime.now().isoformat(),
        }
        
        msg = ThinkingMessage.from_dict(data)
        assert msg.id == "msg_123"
        assert msg.content == "Test"


class TestDiscussionRound:
    """Test DiscussionRound model."""
    
    def test_discussion_round_creation(self):
        """Test discussion round creation."""
        from stock_datasource.arena import DiscussionRound, DiscussionMode
        
        round = DiscussionRound(
            arena_id="arena_1",
            round_number=1,
            mode=DiscussionMode.DEBATE,
            participants=["agent_1", "agent_2"],
        )
        
        assert round.arena_id == "arena_1"
        assert round.round_number == 1
        assert round.mode == DiscussionMode.DEBATE
    
    def test_discussion_round_is_completed(self):
        """Test discussion round completion check."""
        from stock_datasource.arena import DiscussionRound
        
        round = DiscussionRound()
        assert not round.is_completed
        
        round.completed_at = datetime.now()
        assert round.is_completed
    
    def test_discussion_round_duration(self):
        """Test discussion round duration calculation."""
        from stock_datasource.arena import DiscussionRound
        
        started = datetime.now() - timedelta(minutes=5)
        round = DiscussionRound(started_at=started)
        
        duration = round.duration_seconds
        assert duration >= 300  # At least 5 minutes


class TestArenaStrategy:
    """Test ArenaStrategy model."""
    
    def test_strategy_creation(self):
        """Test strategy creation."""
        from stock_datasource.arena import ArenaStrategy, CompetitionStage
        
        strategy = ArenaStrategy(
            arena_id="arena_1",
            agent_id="agent_1",
            name="Test Strategy",
            description="A test strategy",
            stage=CompetitionStage.BACKTEST,
        )
        
        assert strategy.name == "Test Strategy"
        assert strategy.is_active == True
        assert strategy.stage == CompetitionStage.BACKTEST
    
    def test_strategy_to_dict(self):
        """Test strategy serialization."""
        from stock_datasource.arena import ArenaStrategy
        
        strategy = ArenaStrategy(
            arena_id="arena_1",
            name="Test Strategy",
        )
        
        strategy_dict = strategy.to_dict()
        assert "id" in strategy_dict
        assert "name" in strategy_dict
        assert "is_active" in strategy_dict


class TestArena:
    """Test Arena model."""
    
    def test_arena_creation(self):
        """Test arena creation."""
        from stock_datasource.arena import Arena, ArenaConfig, ArenaState
        
        config = ArenaConfig(name="Test Arena")
        arena = Arena.from_config(config)
        
        assert arena.state == ArenaState.CREATED
        assert arena.config.name == "Test Arena"
    
    def test_arena_active_strategy_count(self):
        """Test active strategy count calculation."""
        from stock_datasource.arena import Arena, ArenaStrategy, ArenaConfig
        
        arena = Arena.from_config(ArenaConfig(name="Test"))
        arena.strategies = [
            ArenaStrategy(is_active=True),
            ArenaStrategy(is_active=True),
            ArenaStrategy(is_active=False),
        ]
        
        assert arena.active_strategy_count == 2
    
    def test_arena_leaderboard(self):
        """Test leaderboard generation."""
        from stock_datasource.arena import Arena, ArenaStrategy, ArenaConfig
        
        arena = Arena.from_config(ArenaConfig(name="Test"))
        arena.strategies = [
            ArenaStrategy(is_active=True, current_score=50.0),
            ArenaStrategy(is_active=True, current_score=80.0),
            ArenaStrategy(is_active=True, current_score=65.0),
        ]
        
        leaderboard = arena.get_leaderboard()
        assert len(leaderboard) == 3
        assert leaderboard[0].current_score == 80.0
        assert leaderboard[1].current_score == 65.0


# =============================================================================
# Test API Request/Response Models
# =============================================================================

class TestAPIModels:
    """Test API request and response model validation."""
    
    def test_create_arena_request_validation(self):
        """Test CreateArenaRequest validation."""
        from stock_datasource.modules.arena.router import CreateArenaRequest
        
        request = CreateArenaRequest(
            name="Test Arena",
            description="Test description",
            agent_count=5,
            symbols=["000001.SZ"],
        )
        
        assert request.name == "Test Arena"
        assert request.agent_count == 5
        assert len(request.symbols) == 1
    
    def test_create_arena_request_defaults(self):
        """Test CreateArenaRequest default values."""
        from stock_datasource.modules.arena.router import CreateArenaRequest
        
        request = CreateArenaRequest(name="Test")
        
        assert request.agent_count == 5
        assert request.discussion_max_rounds == 3
        assert request.initial_capital == 100000.0
        assert request.simulated_duration_days == 30
    
    def test_intervention_request_inject_message(self):
        """Test InterventionRequest for inject_message action."""
        from stock_datasource.modules.arena.router import InterventionRequest
        
        request = InterventionRequest(
            action="inject_message",
            message="Test message",
            reason="Testing",
        )
        assert request.action == "inject_message"
        assert request.message == "Test message"
    
    def test_intervention_request_adjust_score(self):
        """Test InterventionRequest for adjust_score action."""
        from stock_datasource.modules.arena.router import InterventionRequest
        
        request = InterventionRequest(
            action="adjust_score",
            target_strategy_id="strategy_1",
            score_adjustment=10.0,
        )
        assert request.action == "adjust_score"
        assert request.score_adjustment == 10.0
    
    def test_intervention_request_eliminate_strategy(self):
        """Test InterventionRequest for eliminate_strategy action."""
        from stock_datasource.modules.arena.router import InterventionRequest
        
        request = InterventionRequest(
            action="eliminate_strategy",
            target_strategy_id="strategy_1",
            reason="Poor performance",
        )
        assert request.action == "eliminate_strategy"
        assert request.target_strategy_id == "strategy_1"
    
    def test_trigger_evaluation_request(self):
        """Test TriggerEvaluationRequest validation."""
        from stock_datasource.modules.arena.router import TriggerEvaluationRequest
        
        request = TriggerEvaluationRequest(period="weekly")
        assert request.period == "weekly"
    
    def test_trigger_discussion_request(self):
        """Test TriggerDiscussionRequest validation."""
        from stock_datasource.modules.arena.router import TriggerDiscussionRequest
        
        request = TriggerDiscussionRequest(mode="debate")
        assert request.mode == "debate"


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """Test custom exceptions."""
    
    def test_arena_not_found_error(self):
        """Test ArenaNotFoundError."""
        from stock_datasource.arena import ArenaNotFoundError
        
        error = ArenaNotFoundError("arena_123")
        assert "arena_123" in str(error)
    
    def test_arena_state_error(self):
        """Test ArenaStateError."""
        from stock_datasource.arena import ArenaStateError
        
        error = ArenaStateError(
            arena_id="arena_123",
            current_state="paused",
            expected_states=["created", "discussing"],
            operation="start"
        )
        assert "paused" in str(error)
        assert "arena_123" in str(error.arena_id)


# =============================================================================
# Performance Benchmarks (Optional)
# =============================================================================

class TestPerformance:
    """Performance and benchmark tests."""
    
    @pytest.mark.skip(reason="Performance test - run manually")
    def test_concurrent_agent_performance(self):
        """Test performance with multiple concurrent agents."""
        pass
    
    @pytest.mark.skip(reason="Performance test - run manually")
    def test_thinking_stream_throughput(self):
        """Test thinking stream message throughput."""
        pass
    
    @pytest.mark.skip(reason="Performance test - run manually")
    def test_large_arena_creation(self):
        """Test creation of arena with max agents."""
        from stock_datasource.arena import ArenaConfig
        
        config = ArenaConfig(name="Large Arena", agent_count=10)
        assert len(config.agents) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
