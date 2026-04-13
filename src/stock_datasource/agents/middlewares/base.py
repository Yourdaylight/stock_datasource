"""Middleware base classes and context models.

All middlewares follow a before/after pattern:
- before(context): Process request context before agent execution
- after(context, response): Process response after agent execution
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _get_logger(name: str):
    """Get a loguru logger bound with the given name."""
    try:
        from stock_datasource.utils.logger import logger as _loguru
        return _loguru.bind(name=name)
    except Exception:
        import logging
        return logging.getLogger(name)


@dataclass
class AgentContext:
    """Context passed through the middleware chain.

    This is the mutable state that middlewares read and modify.
    """

    query: str = ""
    session_id: str = "default"
    user_id: str = "default"
    intent: str = ""
    stock_codes: List[str] = field(default_factory=list)
    is_deep_research: bool = False
    # Memory injection result
    memory_block: str = ""
    # Signal detection result
    signal: Optional[Any] = None  # SignalResult
    # Loop detection
    loop_detected: bool = False
    # Guardrail flags
    is_financial_query: bool = True
    hallucination_warning: str = ""
    # Tool call tracking
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    # Middleware metadata
    middleware_trace: List[str] = field(default_factory=list)
    # Extra arbitrary data
    extra: Dict[str, Any] = field(default_factory=dict)

    def trace(self, middleware_name: str, action: str) -> None:
        """Add a trace entry for debugging."""
        self.middleware_trace.append(f"{middleware_name}:{action}@{time.time():.3f}")


@dataclass
class AgentResponse:
    """Response passed through the middleware chain (after phase).

    Middlewares can modify the response content or add metadata.
    """

    content: str = ""
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    # Cross-validation results (populated by CrossValidationMiddleware)
    validation_result: Optional[Dict[str, Any]] = None
    # Guardrail additions
    warnings: List[str] = field(default_factory=list)


class BaseMiddleware(ABC):
    """Abstract base class for all middlewares.

    Subclasses must implement before() and after().
    Provides before_with_logging / after_with_logging wrappers that
    emit structured log events with duration and middleware_trace_id.
    """

    # Whether this middleware is enabled (can be toggled at runtime)
    enabled: bool = True

    def __init__(self):
        self._log = _get_logger(f"middleware.{self.__class__.__name__}")

    @abstractmethod
    async def before(self, context: AgentContext) -> AgentContext:
        """Process context before agent execution.

        Args:
            context: The current agent context. May be modified.

        Returns:
            The (possibly modified) context.
        """

    @abstractmethod
    async def after(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Process response after agent execution.

        Args:
            context: The agent context (read-only reference).
            response: The agent's response. May be modified.

        Returns:
            The (possibly modified) response.
        """

    @property
    def name(self) -> str:
        """Middleware name for logging and tracing."""
        return self.__class__.__name__

    async def before_with_logging(self, context: AgentContext) -> AgentContext:
        """Wrapper: structured log around before()."""
        if not self.enabled:
            return context
        t0 = time.time()
        self._log.info("middleware.before.start", middleware=self.name, session_id=context.session_id)
        try:
            result = await self.before(context)
            ms = round((time.time() - t0) * 1000, 1)
            self._log.info("middleware.before.done", middleware=self.name, duration_ms=ms)
            return result
        except Exception as e:
            self._log.error("middleware.before.failed", middleware=self.name, error=str(e))
            raise

    async def after_with_logging(self, context: AgentContext, response: AgentResponse) -> AgentResponse:
        """Wrapper: structured log around after()."""
        if not self.enabled:
            return response
        t0 = time.time()
        self._log.info("middleware.after.start", middleware=self.name, session_id=context.session_id)
        try:
            result = await self.after(context, response)
            ms = round((time.time() - t0) * 1000, 1)
            self._log.info("middleware.after.done", middleware=self.name, duration_ms=ms)
            return result
        except Exception as e:
            self._log.error("middleware.after.failed", middleware=self.name, error=str(e))
            raise
