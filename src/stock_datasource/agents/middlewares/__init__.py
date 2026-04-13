"""Middleware chain for stock_datasource agents.

All middlewares follow the BaseMiddleware before/after pattern.
Execution order:
1. LoopDetectionMiddleware - detect tool call loops
2. SummarizationMiddleware - fraction-based context summarization
3. GuardrailMiddleware - input/output safety checks
4. MemoryInjectionMiddleware - inject memory from Store
5. CrossValidationMiddleware - cross-validate agent conclusions
"""

from .base import AgentContext, AgentResponse, BaseMiddleware
from .loop_detection import LoopDetectionMiddleware
from .summarization import SummarizationMiddleware
from .memory_injection import MemoryInjectionMiddleware
from .guardrail import GuardrailMiddleware
from .cross_validation import CrossValidationMiddleware

from stock_datasource.modules.memory.models import ContextSize
from stock_datasource.modules.memory.store import MemoryStore, get_memory_store

__all__ = [
    # Base
    "AgentContext",
    "AgentResponse",
    "BaseMiddleware",
    # Middlewares
    "LoopDetectionMiddleware",
    "SummarizationMiddleware",
    "GuardrailMiddleware",
    "MemoryInjectionMiddleware",
    "CrossValidationMiddleware",
    # Helpers
    "ContextSize",
    "MemoryStore",
    "get_memory_store",
    "build_default_middleware_chain",
]


def build_default_middleware_chain(
    store: MemoryStore = None,
) -> list:
    """Build the default middleware chain with recommended configuration.

    Args:
        store: Optional MemoryStore instance. If None, uses global singleton.

    Returns:
        Ordered list of BaseMiddleware instances.
    """
    store = store or get_memory_store()

    return [
        LoopDetectionMiddleware(max_consecutive=3),
        SummarizationMiddleware(
            trigger=[
                ContextSize(type="fraction", value=0.7),
                ContextSize(type="tokens", value=6000),
            ],
            keep=ContextSize(type="fraction", value=0.3),
        ),
        GuardrailMiddleware(hallucination_check_enabled=False),
        MemoryInjectionMiddleware(store=store),
        CrossValidationMiddleware(store=store),
    ]
