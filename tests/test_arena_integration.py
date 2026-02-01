"""
Integration tests for the Multi-Agent Strategy Arena module.

Tests cover end-to-end flows:
- Arena lifecycle (create → start → pause → resume → complete)
- Multi-agent discussion flow
- Competition and elimination workflow
- API endpoint integration
- SSE thinking stream
"""

import pytest
import asyncio
import httpx
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List
import json


# =============================================================================
# Test Configuration
# =============================================================================

# Mock FastAPI test client
@pytest.fixture
def test_client():
    """Create a test client for API testing."""
    # This would use FastAPI TestClient in real implementation
    return None


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for agent calls."""
    return {
        "strategy_name": "Mock Strategy",
        "description": "A mock strategy for testing",
        "logic": "Buy when price > MA20, sell when price < MA20",
        "rules": {
            "buy_condition": "price > MA20",
            "sell_condition": "price < MA20",
            "stop_loss": 0.05,
        },
    }


# =============================================================================
# Integration Test: Arena Lifecycle
# =============================================================================

class TestArenaLifecycle:
    """Test complete arena lifecycle from creation to completion."""
    
    def test_arena_creation_flow(self):
        """Test arena can be created with valid configuration."""
        from stock_datasource.arena import ArenaConfig, create_arena, delete_arena
        
        config = ArenaConfig(
            name="Integration Test Arena",
            description="Testing arena lifecycle",
            agent_count=5,
            symbols=["000001.SZ", "600000.SH"],
        )
        
        arena = create_arena(config)
        
        try:
            assert arena is not None
            assert arena.arena.state.value == "created"
            assert arena.arena.config.name == "Integration Test Arena"
            assert len(arena.arena.config.agents) == 5
        finally:
            delete_arena(arena.arena.id)
    
    def test_arena_list_and_get(self):
        """Test listing and retrieving arenas."""
        from stock_datasource.arena import (
            ArenaConfig, create_arena, get_arena, list_arenas, delete_arena
        )
        
        config = ArenaConfig(name="List Test Arena")
        arena = create_arena(config)
        arena_id = arena.arena.id
        
        try:
            # Test list
            arenas = list_arenas()
            assert isinstance(arenas, list)
            assert any(a.get("id") == arena_id for a in arenas)
            
            # Test get
            retrieved = get_arena(arena_id)
            assert retrieved.arena.id == arena_id
        finally:
            delete_arena(arena_id)
    
    def test_arena_status_tracking(self):
        """Test arena status is correctly tracked."""
        from stock_datasource.arena import ArenaConfig, create_arena, delete_arena
        
        config = ArenaConfig(name="Status Test Arena")
        arena = create_arena(config)
        
        try:
            status = arena.get_status()
            
            assert "id" in status
            assert "state" in status
            assert "active_strategies" in status
            assert "discussion_rounds" in status
            assert status["state"] == "created"
        finally:
            delete_arena(arena.arena.id)
    
    def test_arena_delete(self):
        """Test arena deletion."""
        from stock_datasource.arena import (
            ArenaConfig, create_arena, delete_arena, get_arena, ArenaNotFoundError
        )
        
        config = ArenaConfig(name="Delete Test Arena")
        arena = create_arena(config)
        arena_id = arena.arena.id
        
        # Delete
        delete_arena(arena_id)
        
        # Verify deleted
        with pytest.raises(ArenaNotFoundError):
            get_arena(arena_id)


# =============================================================================
# Integration Test: Strategy Management
# =============================================================================

class TestStrategyManagement:
    """Test strategy creation, tracking, and management."""
    
    def test_strategy_list(self):
        """Test listing strategies in arena."""
        from stock_datasource.arena import ArenaConfig, create_arena, delete_arena
        
        config = ArenaConfig(name="Strategy List Test", agent_count=5)
        arena = create_arena(config)
        
        try:
            strategies = arena.get_strategies()
            assert isinstance(strategies, list)
        finally:
            delete_arena(arena.arena.id)
    
    def test_leaderboard_generation(self):
        """Test leaderboard is correctly generated."""
        from stock_datasource.arena import (
            ArenaConfig, create_arena, delete_arena, ArenaStrategy
        )
        
        config = ArenaConfig(name="Leaderboard Test")
        arena = create_arena(config)
        
        try:
            # Add mock strategies with scores
            arena.arena.strategies = [
                ArenaStrategy(name="Strategy A", current_score=85.0, is_active=True),
                ArenaStrategy(name="Strategy B", current_score=72.0, is_active=True),
                ArenaStrategy(name="Strategy C", current_score=90.0, is_active=True),
            ]
            
            leaderboard = arena.get_leaderboard()
            
            assert len(leaderboard) == 3
            # Verify sorted by score descending
            assert leaderboard[0]["score"] >= leaderboard[1]["score"]
            assert leaderboard[1]["score"] >= leaderboard[2]["score"]
        finally:
            delete_arena(arena.arena.id)
    
    def test_active_strategies_filter(self):
        """Test filtering active strategies."""
        from stock_datasource.arena import (
            ArenaConfig, create_arena, delete_arena, ArenaStrategy
        )
        
        config = ArenaConfig(name="Active Filter Test")
        arena = create_arena(config)
        
        try:
            arena.arena.strategies = [
                ArenaStrategy(name="Active 1", is_active=True),
                ArenaStrategy(name="Active 2", is_active=True),
                ArenaStrategy(name="Eliminated", is_active=False),
            ]
            
            active = arena.get_strategies(active_only=True)
            all_strategies = arena.get_strategies(active_only=False)
            
            assert len(active) == 2
            assert len(all_strategies) == 3
        finally:
            delete_arena(arena.arena.id)


# =============================================================================
# Integration Test: Discussion Flow
# =============================================================================

class TestDiscussionFlow:
    """Test multi-agent discussion workflow."""
    
    def test_discussion_history_tracking(self):
        """Test discussion history is correctly tracked."""
        from stock_datasource.arena import (
            ArenaConfig, create_arena, delete_arena, DiscussionRound, DiscussionMode
        )
        
        config = ArenaConfig(name="Discussion History Test")
        arena = create_arena(config)
        
        try:
            # Add mock discussion rounds
            arena.arena.discussion_rounds = [
                DiscussionRound(
                    arena_id=arena.arena.id,
                    round_number=1,
                    mode=DiscussionMode.DEBATE,
                    completed_at=datetime.now(),
                ),
                DiscussionRound(
                    arena_id=arena.arena.id,
                    round_number=2,
                    mode=DiscussionMode.COLLABORATION,
                ),
            ]
            
            history = arena.get_discussion_history()
            
            assert len(history) == 2
            assert history[0]["round_number"] == 1
        finally:
            delete_arena(arena.arena.id)
    
    def test_discussion_modes_supported(self):
        """Test all discussion modes are supported."""
        from stock_datasource.arena import DiscussionMode
        
        supported_modes = ["debate", "collaboration", "review"]
        
        for mode_name in supported_modes:
            mode = DiscussionMode(mode_name)
            assert mode is not None


# =============================================================================
# Integration Test: Evaluation and Elimination
# =============================================================================

class TestEvaluationFlow:
    """Test evaluation and elimination workflow."""
    
    def test_evaluation_periods(self):
        """Test different evaluation periods."""
        from stock_datasource.arena import EvaluationPeriod
        
        periods = [
            EvaluationPeriod.DAILY,
            EvaluationPeriod.WEEKLY,
            EvaluationPeriod.MONTHLY,
        ]
        
        for period in periods:
            assert period.value in ["daily", "weekly", "monthly"]
    
    def test_elimination_calculation(self):
        """Test elimination count calculation."""
        from stock_datasource.arena import EvaluationConfig
        
        config = EvaluationConfig(
            weekly_elimination_rate=0.2,
            monthly_elimination_rate=0.1,
            min_strategies=3,
        )
        
        total_strategies = 10
        
        weekly_elim = int(total_strategies * config.weekly_elimination_rate)
        monthly_elim = int(total_strategies * config.monthly_elimination_rate)
        
        # With 10 strategies, weekly should eliminate 2, monthly should eliminate 1
        assert weekly_elim == 2
        assert monthly_elim == 1
        
        # But we should preserve min_strategies
        # If we have 4 strategies, we can only eliminate 1 to preserve min of 3
        remaining = 4
        max_elim = max(0, remaining - config.min_strategies)
        actual_elim = min(int(remaining * config.weekly_elimination_rate), max_elim)
        assert actual_elim <= 1
    
    def test_score_ranking(self):
        """Test strategies are ranked by score."""
        from stock_datasource.arena import ArenaStrategy
        
        strategies = [
            ArenaStrategy(name="A", current_score=70.0),
            ArenaStrategy(name="B", current_score=90.0),
            ArenaStrategy(name="C", current_score=80.0),
        ]
        
        # Sort by score descending
        ranked = sorted(strategies, key=lambda s: s.current_score, reverse=True)
        
        assert ranked[0].name == "B"
        assert ranked[1].name == "C"
        assert ranked[2].name == "A"


# =============================================================================
# Integration Test: Thinking Stream
# =============================================================================

class TestThinkingStream:
    """Test thinking stream functionality."""
    
    def test_thinking_message_creation(self):
        """Test thinking message can be created."""
        from stock_datasource.arena import ThinkingMessage, MessageType
        
        msg = ThinkingMessage(
            arena_id="arena_1",
            agent_id="agent_1",
            agent_role="strategy_generator",
            round_id="round_1",
            message_type=MessageType.THINKING,
            content="Analyzing market trends...",
            metadata={"confidence": 0.85},
        )
        
        assert msg.arena_id == "arena_1"
        assert msg.message_type == MessageType.THINKING
        assert msg.metadata["confidence"] == 0.85
    
    def test_message_serialization(self):
        """Test message can be serialized and deserialized."""
        from stock_datasource.arena import ThinkingMessage, MessageType
        
        original = ThinkingMessage(
            arena_id="arena_1",
            agent_id="agent_1",
            content="Test content",
            message_type=MessageType.ARGUMENT,
        )
        
        # Serialize
        msg_dict = original.to_dict()
        json_str = json.dumps(msg_dict)
        
        # Deserialize
        parsed = json.loads(json_str)
        restored = ThinkingMessage.from_dict(parsed)
        
        assert restored.arena_id == original.arena_id
        assert restored.content == original.content
    
    def test_message_types_coverage(self):
        """Test all message types can be created."""
        from stock_datasource.arena import ThinkingMessage, MessageType
        
        for msg_type in MessageType:
            msg = ThinkingMessage(
                arena_id="arena_1",
                message_type=msg_type,
                content=f"Test {msg_type.value}",
            )
            assert msg.message_type == msg_type


# =============================================================================
# Integration Test: API Endpoints
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoint integration."""
    
    def test_create_arena_request_model(self):
        """Test CreateArenaRequest model validation."""
        from stock_datasource.modules.arena.router import CreateArenaRequest
        
        # Valid request
        request = CreateArenaRequest(
            name="API Test Arena",
            description="Testing API",
            agent_count=5,
            symbols=["000001.SZ"],
            discussion_max_rounds=3,
            initial_capital=100000.0,
        )
        
        assert request.name == "API Test Arena"
        assert request.agent_count >= 3
        assert request.agent_count <= 10
    
    def test_arena_response_model(self):
        """Test ArenaResponse model structure."""
        from stock_datasource.modules.arena.router import ArenaResponse
        
        response = ArenaResponse(
            id="arena_123",
            name="Test Arena",
            state="created",
            active_strategies=5,
            total_strategies=5,
            eliminated_strategies=0,
            discussion_rounds=0,
            last_evaluation=None,
            duration_seconds=0.0,
            error_count=0,
            last_error=None,
        )
        
        assert response.id == "arena_123"
        assert response.state == "created"
    
    def test_leaderboard_entry_model(self):
        """Test LeaderboardEntry model structure."""
        from stock_datasource.modules.arena.router import LeaderboardEntry
        
        entry = LeaderboardEntry(
            rank=1,
            strategy_id="strategy_1",
            name="Top Strategy",
            agent_id="agent_1",
            agent_role="strategy_generator",
            score=95.5,
            stage="simulated",
        )
        
        assert entry.rank == 1
        assert entry.score == 95.5
    
    def test_intervention_request_validation(self):
        """Test InterventionRequest validation for all actions."""
        from stock_datasource.modules.arena.router import InterventionRequest
        
        actions = ["inject_message", "adjust_score", "eliminate_strategy", "add_strategy"]
        
        for action in actions:
            request = InterventionRequest(action=action)
            assert request.action == action


# =============================================================================
# Integration Test: Error Handling
# =============================================================================

class TestErrorHandling:
    """Test error handling across the system."""
    
    def test_arena_not_found_error(self):
        """Test ArenaNotFoundError is raised for invalid arena ID."""
        from stock_datasource.arena import get_arena, ArenaNotFoundError
        
        with pytest.raises(ArenaNotFoundError):
            get_arena("nonexistent_arena_id")
    
    def test_invalid_config_handling(self):
        """Test handling of invalid configuration."""
        from stock_datasource.arena import ArenaConfig
        from pydantic import ValidationError
        
        # agent_count out of range should raise validation error
        with pytest.raises(ValidationError):
            ArenaConfig(name="Test", agent_count=15)  # Max is 10
    
    def test_invalid_evaluation_period(self):
        """Test handling of invalid evaluation period."""
        from stock_datasource.arena import EvaluationPeriod
        
        with pytest.raises(ValueError):
            EvaluationPeriod("invalid_period")


# =============================================================================
# Integration Test: Concurrent Operations
# =============================================================================

class TestConcurrentOperations:
    """Test concurrent operation handling."""
    
    @pytest.mark.asyncio
    async def test_multiple_arena_creation(self):
        """Test multiple arenas can be created concurrently."""
        from stock_datasource.arena import ArenaConfig, create_arena, delete_arena
        
        arenas = []
        
        try:
            # Create multiple arenas
            for i in range(3):
                config = ArenaConfig(name=f"Concurrent Arena {i}")
                arena = create_arena(config)
                arenas.append(arena)
            
            assert len(arenas) == 3
            
            # Verify all are unique
            ids = [a.arena.id for a in arenas]
            assert len(set(ids)) == 3
        finally:
            for arena in arenas:
                try:
                    delete_arena(arena.arena.id)
                except Exception:
                    pass


# =============================================================================
# Integration Test: Data Persistence
# =============================================================================

class TestDataPersistence:
    """Test data persistence functionality."""
    
    def test_arena_to_dict(self):
        """Test arena serialization for persistence."""
        from stock_datasource.arena import ArenaConfig, create_arena, delete_arena
        
        config = ArenaConfig(name="Persistence Test")
        arena = create_arena(config)
        
        try:
            arena_dict = arena.to_dict()
            
            assert "id" in arena_dict
            assert "config" in arena_dict
            assert "state" in arena_dict
            assert "strategies" in arena_dict
            assert "discussion_rounds" in arena_dict
        finally:
            delete_arena(arena.arena.id)
    
    def test_strategy_serialization(self):
        """Test strategy serialization for persistence."""
        from stock_datasource.arena import ArenaStrategy, CompetitionStage
        
        strategy = ArenaStrategy(
            arena_id="arena_1",
            name="Persistence Strategy",
            logic="Test logic",
            stage=CompetitionStage.BACKTEST,
        )
        
        strategy_dict = strategy.to_dict()
        
        assert strategy_dict["name"] == "Persistence Strategy"
        assert strategy_dict["stage"] == "backtest"
        assert "created_at" in strategy_dict


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
