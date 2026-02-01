"""
Arena Exception Classes

Defines custom exceptions for the Multi-Agent Strategy Arena system.
"""


class ArenaException(Exception):
    """Base exception for arena-related errors."""
    
    def __init__(self, message: str, arena_id: str = None, details: dict = None):
        super().__init__(message)
        self.arena_id = arena_id
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": str(self),
            "arena_id": self.arena_id,
            "details": self.details,
        }


class ArenaNotFoundError(ArenaException):
    """Raised when an arena cannot be found."""
    
    def __init__(self, arena_id: str):
        super().__init__(f"Arena not found: {arena_id}", arena_id=arena_id)


class ArenaStateError(ArenaException):
    """Raised when an operation is invalid for the current arena state."""
    
    def __init__(self, arena_id: str, current_state: str, expected_states: list, operation: str = ""):
        message = f"Invalid arena state for operation '{operation}': current={current_state}, expected one of {expected_states}"
        super().__init__(message, arena_id=arena_id, details={
            "current_state": current_state,
            "expected_states": expected_states,
            "operation": operation,
        })


class AgentExecutionError(ArenaException):
    """Raised when an agent fails to execute properly."""
    
    def __init__(self, arena_id: str, agent_id: str, agent_role: str, error: str):
        message = f"Agent execution failed: {agent_role} ({agent_id}): {error}"
        super().__init__(message, arena_id=arena_id, details={
            "agent_id": agent_id,
            "agent_role": agent_role,
            "error": error,
        })


class DiscussionError(ArenaException):
    """Raised when a discussion round fails."""
    
    def __init__(self, arena_id: str, round_id: str, mode: str, error: str):
        message = f"Discussion round failed: {mode} round ({round_id}): {error}"
        super().__init__(message, arena_id=arena_id, details={
            "round_id": round_id,
            "mode": mode,
            "error": error,
        })


class EvaluationError(ArenaException):
    """Raised when strategy evaluation fails."""
    
    def __init__(self, arena_id: str, period: str, error: str, strategy_ids: list = None):
        message = f"Evaluation failed for period {period}: {error}"
        super().__init__(message, arena_id=arena_id, details={
            "period": period,
            "error": error,
            "strategy_ids": strategy_ids or [],
        })


class ThinkingStreamError(ArenaException):
    """Raised when thinking stream operations fail."""
    
    def __init__(self, arena_id: str, operation: str, error: str):
        message = f"Thinking stream error during {operation}: {error}"
        super().__init__(message, arena_id=arena_id, details={
            "operation": operation,
            "error": error,
        })


class CompetitionError(ArenaException):
    """Raised when competition operations fail."""
    
    def __init__(self, arena_id: str, stage: str, error: str, strategy_id: str = None):
        message = f"Competition error at stage {stage}: {error}"
        super().__init__(message, arena_id=arena_id, details={
            "stage": stage,
            "error": error,
            "strategy_id": strategy_id,
        })


class ConfigurationError(ArenaException):
    """Raised when arena configuration is invalid."""
    
    def __init__(self, message: str, config_field: str = None, value: any = None):
        super().__init__(message, details={
            "config_field": config_field,
            "value": value,
        })
