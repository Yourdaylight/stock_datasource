"""Memory data models for the memory system.

Defines the core data structures used by the memory layer:
- FactItem: A single extracted fact about the user
- ContextSize: Trigger/keep threshold specification (fraction/tokens/messages)
- UserProfile: User profile stored in LangGraph Store
- AgentSharedResult: Cross-agent shared data within a session
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Union

# ---------------------------------------------------------------------------
# Context size specification (reference: deer-flow summarization_config.py)
# ---------------------------------------------------------------------------

ContextSizeType = Literal["fraction", "tokens", "messages"]


@dataclass
class ContextSize:
    """Context size specification for trigger or keep parameters.

    Supports three dimensions:
    - fraction: percentage of model's max input tokens (recommended, adapts to model)
    - tokens: absolute token count
    - messages: message count (weakest dimension, not recommended as primary)
    """

    type: ContextSizeType
    value: Union[int, float]

    def resolve(self, model_max_tokens: int = 128000, current_message_count: int = 0) -> float:
        """Resolve to an absolute token/message count.

        Args:
            model_max_tokens: The model's maximum input token limit.
            current_message_count: Current number of messages (for messages type).

        Returns:
            Absolute threshold value.
        """
        if self.type == "fraction":
            return model_max_tokens * self.value
        elif self.type == "tokens":
            return float(self.value)
        elif self.type == "messages":
            return float(self.value)
        return float(self.value)


# ---------------------------------------------------------------------------
# Fact item
# ---------------------------------------------------------------------------

FactCategory = Literal[
    "risk_preference",
    "sector_focus",
    "stock_opinion",
    "trading_style",
    "conclusion",
]


@dataclass
class FactItem:
    """A single extracted fact about the user.

    Confidence evolution:
    - Initial: 0.7
    - Each reinforcement: +0.1 (cap 1.0)
    - Each contradiction: -0.3
    - Auto-decay: 7 days without reinforcement and confidence < 0.5 → delete
    """

    content: str
    category: FactCategory
    confidence: float = 0.7
    source: str = ""
    created_at: float = field(default_factory=time.time)
    reinforced_at: List[float] = field(default_factory=list)
    contradicted_at: List[float] = field(default_factory=list)

    # Class-level constants
    INITIAL_CONFIDENCE: float = 0.7
    REINFORCEMENT_DELTA: float = 0.1
    CONTRADICTION_DELTA: float = 0.3
    MAX_CONFIDENCE: float = 1.0
    MIN_CONFIDENCE: float = 0.0
    DECAY_THRESHOLD: float = 0.5
    DECAY_DAYS: int = 7

    def reinforce(self) -> None:
        """Reinforce this fact (user confirmed it)."""
        self.confidence = min(self.MAX_CONFIDENCE, self.confidence + self.REINFORCEMENT_DELTA)
        self.reinforced_at.append(time.time())

    def contradict(self) -> None:
        """Mark this fact as contradicted (user corrected it)."""
        self.confidence = max(self.MIN_CONFIDENCE, self.confidence - self.CONTRADICTION_DELTA)
        self.contradicted_at.append(time.time())

    def should_decay(self) -> bool:
        """Check if this fact should be auto-decayed/deleted."""
        now = time.time()
        seven_days_ago = now - (self.DECAY_DAYS * 86400)
        if self.confidence < self.DECAY_THRESHOLD:
            last_reinforcement = self.reinforced_at[-1] if self.reinforced_at else self.created_at
            return last_reinforcement < seven_days_ago
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for Store persistence."""
        return {
            "content": self.content,
            "category": self.category,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "reinforced_at": self.reinforced_at,
            "contradicted_at": self.contradicted_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FactItem:
        """Deserialize from dict."""
        return cls(
            content=data["content"],
            category=data.get("category", "conclusion"),
            confidence=data.get("confidence", 0.7),
            source=data.get("source", ""),
            created_at=data.get("created_at", time.time()),
            reinforced_at=data.get("reinforced_at", []),
            contradicted_at=data.get("contradicted_at", []),
        )


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

@dataclass
class UserProfileEntry:
    """A single profile attribute for a user."""

    key: str
    value: Any
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "value": self.value, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UserProfileEntry:
        return cls(
            key=data["key"],
            value=data["value"],
            updated_at=data.get("updated_at", time.time()),
        )


# ---------------------------------------------------------------------------
# Agent shared result (session-level)
# ---------------------------------------------------------------------------

@dataclass
class AgentSharedResult:
    """Result shared by an agent within a session for cross-agent collaboration."""

    agent_name: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    key_findings: List[str] = field(default_factory=list)
    token_count: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "tool_calls": self.tool_calls,
            "key_findings": self.key_findings,
            "token_count": self.token_count,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentSharedResult:
        return cls(
            agent_name=data["agent_name"],
            tool_calls=data.get("tool_calls", []),
            key_findings=data.get("key_findings", []),
            token_count=data.get("token_count", 0),
            timestamp=data.get("timestamp", time.time()),
        )


# ---------------------------------------------------------------------------
# Signal detection result (3-layer)
# ---------------------------------------------------------------------------

SignalType = Literal["correction", "reinforcement", "neutral"]


@dataclass
class SignalResult:
    """Result from the 3-layer signal detection."""

    signal: SignalType = "neutral"
    target_fact: str = ""
    correct_value: str = ""
    detected_by: str = ""  # "regex" | "llm_intent" | "none"

    @property
    def is_correction(self) -> bool:
        return self.signal == "correction"

    @property
    def is_reinforcement(self) -> bool:
        return self.signal == "reinforcement"
