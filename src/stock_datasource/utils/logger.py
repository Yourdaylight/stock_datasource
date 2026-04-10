"""Logging configuration for stock data source.

Unified Loguru logging with:
- Request ID / User ID context injection via contextvars
- Structured JSONL sink for ClickHouse import
- Text file + console + error file sinks
- Timed background watcher for rotated JSONL files
"""

import logging
import sys
import threading
from pathlib import Path
from typing import Optional

from loguru import logger as _loguru_logger

from stock_datasource.config.settings import settings
from stock_datasource.utils.request_context import get_request_id, get_user_id, patch_context


def _patch_context(record):
    """Loguru patch: inject request_id / user_id from contextvars into extra."""
    record["extra"].setdefault("request_id", get_request_id())
    record["extra"].setdefault("user_id", get_user_id())
    return True


# The module-level `logger` is the PATCHED loguru instance.
# All callers that `from stock_datasource.utils.logger import logger` will
# get a logger that automatically injects request_id / user_id into every
# record via the patch pipeline, even when used before setup_logging().
#
# NOTE: setup_logging() must still be called to configure sinks (console,
# file, JSONL); without it, log messages go to the default stderr sink.
logger = _loguru_logger.patch(_patch_context)


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to the patched loguru logger.

    Uses the patched logger so that all log records — whether from loguru
    directly or from stdlib logging — go through the same patch pipeline.
    """

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# ---------- Format helpers ----------

def _format_with_context(fmt: str):
    """Return a format function that injects request_id/user_id defaults.

    This avoids ``KeyError: 'request_id'`` when records are emitted via
    the InterceptHandler (stdlib bridge) which bypasses the Loguru ``patch``.
    """
    def _formatter(record):
        record["extra"].setdefault("request_id", get_request_id())
        record["extra"].setdefault("user_id", get_user_id())
        return fmt
    return _formatter


# Format templates (used by _format_with_context to produce safe formatters)
_CONSOLE_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<blue>{extra[request_id]}</blue> | "
    "<magenta>{extra[user_id]}</magenta> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

_TEXT_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{extra[request_id]} | {extra[user_id]} | "
    "{name}:{function}:{line} - {message}"
)


def _jsonl_sink(message):
    """Custom sink: writes one JSONL line per log record.

    Uses Loguru's record dict to get proper JSON escaping.
    """
    record = message.record
    import json as _json
    entry = {
        "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "level": record["level"].name,
        "request_id": record["extra"].get("request_id", "-"),
        "user_id": record["extra"].get("user_id", "-"),
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        "exception": record["exception"],
    }
    return _json.dumps(entry, ensure_ascii=False, default=str)


_setup_done = False
_setup_lock = threading.Lock()
_watcher_thread: Optional[threading.Thread] = None


def setup_logging():
    """Setup unified logging configuration.

    Safe to call multiple times (idempotent after first call).
    """
    global _setup_done, _watcher_thread

    with _setup_lock:
        if _setup_done:
            return logger
        _setup_done = True

    # Remove all existing handlers from the core logger
    _loguru_logger.remove()

    # Use the module-level patched logger (already has _patch_context)
    # to add sinks. This ensures all records go through the patch pipeline.
    _patched = logger

    # --- Console ---
    # Use format function (not raw string) to ensure request_id/user_id
    # defaults are always injected, even for InterceptHandler records.
    _patched.add(
        sys.stdout,
        format=_format_with_context(_CONSOLE_FMT),
        level=settings.LOG_LEVEL,
        colorize=True,
    )

    # --- Text file (compressed on rotation) ---
    log_file = settings.LOGS_DIR / "stock_datasource.log"
    _patched.add(
        log_file,
        format=_format_with_context(_TEXT_FMT),
        level=settings.LOG_LEVEL,
        rotation=settings.LOG_ROTATION_SIZE,
        retention=settings.LOG_RETENTION_DAYS,
        compression="zip",
    )

    # --- Error file ---
    error_file = settings.LOGS_DIR / "errors.log"
    _patched.add(
        error_file,
        format=_format_with_context(_TEXT_FMT),
        level="ERROR",
        rotation=settings.LOG_ROTATION_SIZE,
        retention=settings.LOG_RETENTION_DAYS,
        compression="zip",
    )

    # --- JSONL file (for ClickHouse import, NOT compressed) ---
    if settings.LOG_CH_SINK_ENABLED:
        jsonl_file = settings.LOGS_DIR / "stock_datasource.jsonl"

        def _write_jsonl(message):
            """Write one JSONL line to the JSONL log file."""
            line = _jsonl_sink(message)
            with open(jsonl_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        _patched.add(
            _write_jsonl,
            level=settings.LOG_LEVEL,
            # No rotation/retention/compression/suffix — custom function sinks
            # don't support them; the CH watcher handles file lifecycle.
        )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Quieten noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("clickhouse_driver").setLevel(logging.WARNING)

    # --- Start CH sink watcher (background thread) ---
    if settings.LOG_CH_SINK_ENABLED and _watcher_thread is None:
        from stock_datasource.utils.log_sink_clickhouse import start_ch_sink_watcher
        _watcher_thread = start_ch_sink_watcher(settings.LOGS_DIR, interval=30.0)

    # --- Import any pending JSONL files from previous runs ---
    if settings.LOG_CH_SINK_ENABLED:
        try:
            from stock_datasource.utils.log_sink_clickhouse import import_pending_files
            import_pending_files(settings.LOGS_DIR)
        except Exception:
            pass  # Non-critical; will retry on next startup

    return logger
