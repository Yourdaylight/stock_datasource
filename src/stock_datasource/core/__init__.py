"""Core modules for stock data source."""

from .task_runner import task_runner, TaskRunner
from .plugin_manager import (
    plugin_manager, 
    PluginManager,
    DependencyCheckResult,
    DependencyNotSatisfiedError
)
from .base_plugin import BasePlugin, PluginCategory, PluginRole
from .trade_calendar import (
    trade_calendar_service, 
    TradeCalendarService,
    TradeCalendarError,
    CalendarNotFoundError,
    InvalidDateError
)

__all__ = [
    "task_runner",
    "TaskRunner", 
    "plugin_manager",
    "PluginManager",
    "DependencyCheckResult",
    "DependencyNotSatisfiedError",
    "BasePlugin",
    "PluginCategory",
    "PluginRole",
    "trade_calendar_service",
    "TradeCalendarService",
    "TradeCalendarError",
    "CalendarNotFoundError",
    "InvalidDateError"
]
