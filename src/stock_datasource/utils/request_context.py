"""Request context variables for log tracing.

Provides contextvars that are automatically injected into every log record
via the Loguru `patch` mechanism, enabling request-level log correlation.
"""

import uuid
from contextvars import ContextVar

# Context variables with safe defaults
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
middleware_trace_id_var: ContextVar[str] = ContextVar(
    "middleware_trace_id", default="-"
)


def generate_request_id() -> str:
    """Generate a short request ID (16-char hex from uuid4)."""
    return uuid.uuid4().hex[:16]


def generate_middleware_trace_id() -> str:
    """Generate a middleware trace ID (12-char hex from uuid4)."""
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    """Get the current request ID from context, or '-' if not set."""
    return request_id_var.get("-")


def get_user_id() -> str:
    """Get the current user ID from context, or '-' if not set."""
    return user_id_var.get("-")


def get_middleware_trace_id() -> str:
    """Get the current middleware trace ID from context, or '-' if not set."""
    return middleware_trace_id_var.get("-")


def set_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    middleware_trace_id: str | None = None,
):
    """Convenience setter for context vars at once."""
    if request_id is not None:
        request_id_var.set(request_id)
    if user_id is not None:
        user_id_var.set(user_id)
    if middleware_trace_id is not None:
        middleware_trace_id_var.set(middleware_trace_id)


def reset_request_context():
    """Reset all context vars to their default values."""
    request_id_var.set("-")
    user_id_var.set("-")
    middleware_trace_id_var.set("-")


def patch_context(record):
    """Loguru patch: inject request_id / user_id / middleware_trace_id from contextvars into extra.

    This function is designed to be used with `loguru_logger.patch(patch_context)`.
    It uses setdefault so that explicit extra values are not overwritten.
    """
    record["extra"].setdefault("request_id", get_request_id())
    record["extra"].setdefault("user_id", get_user_id())
    record["extra"].setdefault("middleware_trace_id", get_middleware_trace_id())
    return True
