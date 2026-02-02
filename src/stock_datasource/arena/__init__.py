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

from .models import (
    # Core enums
    ArenaState,
    AgentRole,
    DiscussionMode,
    CompetitionStage,
    EvaluationPeriod,
    MessageType,
    
    # Configuration models
    ArenaConfig,
    AgentConfig as ArenaAgentConfig,
    DiscussionConfig,
    CompetitionConfig,
    EvaluationConfig,
    
    # Data models
    ThinkingMessage,
    DiscussionRound,
    ArenaStrategy,
    StrategyEvaluation,
    Arena,
    
    # Score models
    DimensionScore,
    ComprehensiveScore,
)

from .exceptions import (
    ArenaException,
    ArenaNotFoundError,
    ArenaStateError,
    AgentExecutionError,
    DiscussionError,
    EvaluationError,
)

from .arena_manager import (
    MultiAgentArena,
    create_arena,
    get_arena,
    list_arenas,
    delete_arena,
)

from .stream_processor import ThinkingStreamProcessor, generate_sse_stream

__all__ = [
    # Enums
    'ArenaState',
    'AgentRole',
    'DiscussionMode',
    'CompetitionStage',
    'EvaluationPeriod',
    'MessageType',
    
    # Config
    'ArenaConfig',
    'ArenaAgentConfig',
    'DiscussionConfig',
    'CompetitionConfig',
    'EvaluationConfig',
    
    # Models
    'ThinkingMessage',
    'DiscussionRound',
    'ArenaStrategy',
    'StrategyEvaluation',
    'Arena',
    'DimensionScore',
    'ComprehensiveScore',
    
    # Exceptions
    'ArenaException',
    'ArenaNotFoundError',
    'ArenaStateError',
    'AgentExecutionError',
    'DiscussionError',
    'EvaluationError',
    
    # Arena Manager
    'MultiAgentArena',
    'create_arena',
    'get_arena',
    'list_arenas',
    'delete_arena',
    
    # Stream
    'ThinkingStreamProcessor',
    'generate_sse_stream',
]
