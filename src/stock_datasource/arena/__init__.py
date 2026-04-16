"""
Multi-Agent Strategy Arena Module

This module implements a multi-agent competitive strategy system that simulates
real investment research team collaboration patterns.

Features:
- Configurable multi-agent arena (3-10 agents)
- Discussion modes: Debate, Collaboration, Review
- Competition stages: Backtest → Simulated Trading → Live (reserved)
- Real-time thinking stream with persistence
- Periodic evaluation and elimination mechanism
"""

from .arena_manager import (
    MultiAgentArena,
    create_arena,
    delete_arena,
    get_arena,
    list_arenas,
)
from .exceptions import (
    AgentExecutionError,
    ArenaException,
    ArenaNotFoundError,
    ArenaStateError,
    DiscussionError,
    EvaluationError,
)
from .models import (
    AgentConfig as ArenaAgentConfig,
)
from .models import (
    AgentRole,
    Arena,
    # Configuration models
    ArenaConfig,
    # Core enums
    ArenaState,
    ArenaStrategy,
    CompetitionConfig,
    CompetitionStage,
    ComprehensiveScore,
    # Score models
    DimensionScore,
    DiscussionConfig,
    DiscussionMode,
    DiscussionRound,
    EvaluationConfig,
    EvaluationPeriod,
    MessageType,
    StrategyEvaluation,
    # Data models
    ThinkingMessage,
)
from .stream_processor import ThinkingStreamProcessor, generate_sse_stream

__all__ = [
    # Enums
    "ArenaState",
    "AgentRole",
    "DiscussionMode",
    "CompetitionStage",
    "EvaluationPeriod",
    "MessageType",
    # Config
    "ArenaConfig",
    "ArenaAgentConfig",
    "DiscussionConfig",
    "CompetitionConfig",
    "EvaluationConfig",
    # Models
    "ThinkingMessage",
    "DiscussionRound",
    "ArenaStrategy",
    "StrategyEvaluation",
    "Arena",
    "DimensionScore",
    "ComprehensiveScore",
    # Exceptions
    "ArenaException",
    "ArenaNotFoundError",
    "ArenaStateError",
    "AgentExecutionError",
    "DiscussionError",
    "EvaluationError",
    # Arena Manager
    "MultiAgentArena",
    "create_arena",
    "get_arena",
    "list_arenas",
    "delete_arena",
    # Stream
    "ThinkingStreamProcessor",
    "generate_sse_stream",
]
