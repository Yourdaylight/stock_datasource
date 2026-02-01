"""
Arena Core Data Models

Defines the core data structures for the Multi-Agent Strategy Arena system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


# =============================================================================
# Enumerations
# =============================================================================

class ArenaState(str, Enum):
    """Arena lifecycle states."""
    CREATED = "created"          # Arena created, not started
    INITIALIZING = "initializing"  # Agents initializing
    DISCUSSING = "discussing"    # Agents in discussion phase
    BACKTESTING = "backtesting"  # Running backtests
    SIMULATING = "simulating"    # Simulated trading in progress
    EVALUATING = "evaluating"    # Periodic evaluation
    PAUSED = "paused"           # Temporarily paused
    COMPLETED = "completed"     # All rounds completed
    FAILED = "failed"           # Critical error occurred
    

class AgentRole(str, Enum):
    """Agent roles in the arena."""
    STRATEGY_GENERATOR = "strategy_generator"  # Generates trading strategies
    STRATEGY_REVIEWER = "strategy_reviewer"    # Reviews and critiques strategies
    RISK_ANALYST = "risk_analyst"              # Analyzes risk exposure
    MARKET_SENTIMENT = "market_sentiment"      # Analyzes market sentiment
    QUANT_RESEARCHER = "quant_researcher"      # Provides quantitative research


class DiscussionMode(str, Enum):
    """Discussion modes for agent collaboration."""
    DEBATE = "debate"           # Agents challenge each other's logic
    COLLABORATION = "collaboration"  # Agents complement each other
    REVIEW = "review"           # Some agents generate, others review


class CompetitionStage(str, Enum):
    """Competition stages for strategy validation."""
    BACKTEST = "backtest"       # Historical data validation
    SIMULATED = "simulated"     # Paper trading validation
    LIVE = "live"               # Real trading (reserved)


class EvaluationPeriod(str, Enum):
    """Evaluation period types."""
    DAILY = "daily"             # Daily update (no elimination)
    WEEKLY = "weekly"           # Weekly evaluation (20% elimination)
    MONTHLY = "monthly"         # Monthly evaluation (10% elimination)


class MessageType(str, Enum):
    """Types of thinking stream messages."""
    THINKING = "thinking"       # Agent reasoning process
    ARGUMENT = "argument"       # Discussion argument
    CONCLUSION = "conclusion"   # Final conclusion
    SYSTEM = "system"           # System notification
    ERROR = "error"             # Error message
    INTERVENTION = "intervention"  # Human intervention message


# =============================================================================
# Configuration Models
# =============================================================================

class AgentConfig(BaseModel):
    """Configuration for a single agent in the arena."""
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: AgentRole = Field(default=AgentRole.STRATEGY_GENERATOR)
    model_name: str = Field(default="gpt-4", description="LLM model to use")
    model_provider: str = Field(default="openai", description="Model provider")
    temperature: float = Field(default=0.7, ge=0, le=2)
    personality: str = Field(default="", description="Agent personality/style")
    focus_areas: List[str] = Field(default_factory=list, description="Areas of focus")
    
    class Config:
        use_enum_values = True


class DiscussionConfig(BaseModel):
    """Configuration for discussion rounds."""
    max_rounds: int = Field(default=3, ge=1, le=10, description="Max discussion rounds")
    modes: List[DiscussionMode] = Field(
        default_factory=lambda: [DiscussionMode.DEBATE, DiscussionMode.COLLABORATION, DiscussionMode.REVIEW]
    )
    round_timeout_seconds: int = Field(default=300, description="Timeout per round")
    min_arguments_per_agent: int = Field(default=1, description="Min arguments per agent")
    consensus_threshold: float = Field(default=0.7, ge=0, le=1, description="Consensus threshold")
    
    class Config:
        use_enum_values = True


class CompetitionConfig(BaseModel):
    """Configuration for strategy competition."""
    initial_capital: float = Field(default=100000.0, description="Initial simulated capital")
    backtest_start_date: Optional[str] = Field(default=None, description="Backtest start date")
    backtest_end_date: Optional[str] = Field(default=None, description="Backtest end date")
    simulated_duration_days: int = Field(default=30, description="Simulated trading duration")
    enable_live: bool = Field(default=False, description="Enable live trading (reserved)")
    max_position_size: float = Field(default=1.0, ge=0, le=1, description="Max position as % of capital")
    

class EvaluationConfig(BaseModel):
    """Configuration for evaluation and elimination."""
    daily_enabled: bool = Field(default=True)
    weekly_enabled: bool = Field(default=True)
    weekly_elimination_rate: float = Field(default=0.2, ge=0, le=0.5)
    monthly_enabled: bool = Field(default=True)
    monthly_elimination_rate: float = Field(default=0.1, ge=0, le=0.5)
    min_strategies: int = Field(default=3, description="Minimum strategies to keep")
    
    # Score weights
    return_weight: float = Field(default=0.3, description="Return metrics weight")
    risk_weight: float = Field(default=0.3, description="Risk metrics weight")
    stability_weight: float = Field(default=0.2, description="Stability metrics weight")
    adaptability_weight: float = Field(default=0.2, description="Adaptability metrics weight")


class ArenaConfig(BaseModel):
    """Complete configuration for an arena."""
    name: str = Field(..., description="Arena name")
    description: str = Field(default="", description="Arena description")
    agent_count: int = Field(default=5, ge=3, le=10, description="Number of competing agents")
    agents: List[AgentConfig] = Field(default_factory=list, description="Agent configurations")
    symbols: List[str] = Field(default_factory=list, description="Stock symbols to trade")
    
    discussion: DiscussionConfig = Field(default_factory=DiscussionConfig)
    competition: CompetitionConfig = Field(default_factory=CompetitionConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    
    # Strategy replenishment
    replenish_new_ratio: float = Field(default=0.7, ge=0, le=1, description="Ratio of new agents vs revived")
    
    def __init__(self, **data):
        super().__init__(**data)
        # Auto-generate agent configs if not provided
        if not self.agents:
            self.agents = self._generate_default_agents()
    
    def _generate_default_agents(self) -> List[AgentConfig]:
        """Generate default heterogeneous agent configurations."""
        agents = []
        
        # Define heterogeneous configurations
        configs = [
            (AgentRole.STRATEGY_GENERATOR, "gpt-4", "aggressive", ["momentum", "growth"]),
            (AgentRole.STRATEGY_GENERATOR, "gpt-4", "conservative", ["value", "dividend"]),
            (AgentRole.STRATEGY_GENERATOR, "gpt-4", "balanced", ["momentum", "value"]),
            (AgentRole.STRATEGY_REVIEWER, "gpt-4", "critical", ["risk", "logic"]),
            (AgentRole.RISK_ANALYST, "gpt-4", "cautious", ["volatility", "drawdown"]),
            (AgentRole.MARKET_SENTIMENT, "gpt-4", "intuitive", ["news", "sentiment"]),
            (AgentRole.QUANT_RESEARCHER, "gpt-4", "analytical", ["statistics", "factors"]),
        ]
        
        for i in range(self.agent_count):
            idx = i % len(configs)
            role, model, personality, focus = configs[idx]
            agents.append(AgentConfig(
                role=role,
                model_name=model,
                personality=personality,
                focus_areas=focus,
            ))
        
        return agents
    
    class Config:
        use_enum_values = True


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class ThinkingMessage:
    """A single message in the thinking stream."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    arena_id: str = ""
    agent_id: str = ""
    agent_role: str = ""
    round_id: str = ""
    message_type: MessageType = MessageType.THINKING
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "arena_id": self.arena_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "round_id": self.round_id,
            "message_type": self.message_type.value if isinstance(self.message_type, MessageType) else self.message_type,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThinkingMessage":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            arena_id=data.get("arena_id", ""),
            agent_id=data.get("agent_id", ""),
            agent_role=data.get("agent_role", ""),
            round_id=data.get("round_id", ""),
            message_type=MessageType(data.get("message_type", "thinking")),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
        )


@dataclass
class DiscussionRound:
    """A complete discussion round."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    arena_id: str = ""
    round_number: int = 0
    mode: DiscussionMode = DiscussionMode.DEBATE
    messages: List[ThinkingMessage] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    conclusions: Dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    @property
    def is_completed(self) -> bool:
        """Check if round is completed."""
        return self.completed_at is not None
    
    @property
    def duration_seconds(self) -> float:
        """Get round duration in seconds."""
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "arena_id": self.arena_id,
            "round_number": self.round_number,
            "mode": self.mode.value if isinstance(self.mode, DiscussionMode) else self.mode,
            "messages": [m.to_dict() for m in self.messages],
            "participants": self.participants,
            "conclusions": self.conclusions,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class DimensionScore:
    """Score for a single evaluation dimension."""
    dimension: str = ""
    score: float = 0.0
    weight: float = 0.25
    metrics: Dict[str, float] = field(default_factory=dict)
    
    @property
    def weighted_score(self) -> float:
        """Get weighted score."""
        return self.score * self.weight
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dimension": self.dimension,
            "score": self.score,
            "weight": self.weight,
            "weighted_score": self.weighted_score,
            "metrics": self.metrics,
        }


@dataclass
class ComprehensiveScore:
    """Comprehensive evaluation score."""
    return_score: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="return", weight=0.3))
    risk_score: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="risk", weight=0.3))
    stability_score: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="stability", weight=0.2))
    adaptability_score: DimensionScore = field(default_factory=lambda: DimensionScore(dimension="adaptability", weight=0.2))
    
    @property
    def total_score(self) -> float:
        """Calculate total weighted score."""
        return (
            self.return_score.weighted_score +
            self.risk_score.weighted_score +
            self.stability_score.weighted_score +
            self.adaptability_score.weighted_score
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "return_score": self.return_score.to_dict(),
            "risk_score": self.risk_score.to_dict(),
            "stability_score": self.stability_score.to_dict(),
            "adaptability_score": self.adaptability_score.to_dict(),
            "total_score": self.total_score,
        }


@dataclass
class StrategyEvaluation:
    """Evaluation result for a strategy."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    strategy_id: str = ""
    arena_id: str = ""
    period: EvaluationPeriod = EvaluationPeriod.DAILY
    score: ComprehensiveScore = field(default_factory=ComprehensiveScore)
    rank: int = 0
    eliminated: bool = False
    evaluated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "strategy_id": self.strategy_id,
            "arena_id": self.arena_id,
            "period": self.period.value if isinstance(self.period, EvaluationPeriod) else self.period,
            "score": self.score.to_dict(),
            "rank": self.rank,
            "eliminated": self.eliminated,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass
class ArenaStrategy:
    """A strategy in the arena competition."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    arena_id: str = ""
    agent_id: str = ""
    agent_role: str = ""
    
    # Strategy details
    name: str = ""
    description: str = ""
    logic: str = ""  # Trading logic in natural language
    rules: Dict[str, Any] = field(default_factory=dict)  # Structured trading rules
    symbols: List[str] = field(default_factory=list)
    
    # Competition status
    stage: CompetitionStage = CompetitionStage.BACKTEST
    is_active: bool = True
    eliminated_at: Optional[datetime] = None
    
    # Discussion history
    discussion_rounds: List[str] = field(default_factory=list)  # Round IDs
    refinement_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Performance tracking
    backtest_result_id: Optional[str] = None
    simulated_positions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Evaluation history
    evaluations: List[StrategyEvaluation] = field(default_factory=list)
    current_score: float = 0.0
    current_rank: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "arena_id": self.arena_id,
            "agent_id": self.agent_id,
            "agent_role": self.agent_role,
            "name": self.name,
            "description": self.description,
            "logic": self.logic,
            "rules": self.rules,
            "symbols": self.symbols,
            "stage": self.stage.value if isinstance(self.stage, CompetitionStage) else self.stage,
            "is_active": self.is_active,
            "eliminated_at": self.eliminated_at.isoformat() if self.eliminated_at else None,
            "discussion_rounds": self.discussion_rounds,
            "refinement_history": self.refinement_history,
            "backtest_result_id": self.backtest_result_id,
            "simulated_positions": self.simulated_positions,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "current_score": self.current_score,
            "current_rank": self.current_rank,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class Arena:
    """The main arena entity."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    config: ArenaConfig = field(default_factory=lambda: ArenaConfig(name="Default Arena"))
    state: ArenaState = ArenaState.CREATED
    
    # Participants
    strategies: List[ArenaStrategy] = field(default_factory=list)
    eliminated_strategies: List[ArenaStrategy] = field(default_factory=list)
    
    # Discussion
    discussion_rounds: List[DiscussionRound] = field(default_factory=list)
    current_round_id: Optional[str] = None
    
    # Evaluation
    evaluations: List[StrategyEvaluation] = field(default_factory=list)
    last_evaluation: Optional[datetime] = None
    
    # Error tracking
    last_error: Optional[str] = None
    error_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def active_strategy_count(self) -> int:
        """Get count of active strategies."""
        return len([s for s in self.strategies if s.is_active])
    
    @property
    def total_rounds(self) -> int:
        """Get total discussion rounds completed."""
        return len([r for r in self.discussion_rounds if r.is_completed])
    
    @property
    def duration_seconds(self) -> float:
        """Get arena duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()
    
    def get_leaderboard(self) -> List[ArenaStrategy]:
        """Get strategies sorted by score (leaderboard)."""
        active = [s for s in self.strategies if s.is_active]
        return sorted(active, key=lambda s: s.current_score, reverse=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "config": self.config.model_dump() if hasattr(self.config, 'model_dump') else dict(self.config),
            "state": self.state.value if isinstance(self.state, ArenaState) else self.state,
            "strategies": [s.to_dict() for s in self.strategies],
            "eliminated_strategies": [s.to_dict() for s in self.eliminated_strategies],
            "discussion_rounds": [r.to_dict() for r in self.discussion_rounds],
            "current_round_id": self.current_round_id,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "last_evaluation": self.last_evaluation.isoformat() if self.last_evaluation else None,
            "last_error": self.last_error,
            "error_count": self.error_count,
            "active_strategy_count": self.active_strategy_count,
            "total_rounds": self.total_rounds,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_config(cls, config: ArenaConfig) -> "Arena":
        """Create arena from configuration."""
        return cls(config=config)
