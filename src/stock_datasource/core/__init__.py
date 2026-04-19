"""Core modules for stock data source."""

from .base_plugin import BasePlugin, PluginCategory, PluginRole
from .plugin_manager import (
    DependencyCheckResult,
    DependencyNotSatisfiedError,
    PluginManager,
    plugin_manager,
)
from .task_runner import TaskRunner, task_runner
from .trade_calendar import (
    MARKET_CN,
    MARKET_HK,
    CalendarNotFoundError,
    InvalidDateError,
    TradeCalendarError,
    TradeCalendarService,
    trade_calendar_service,
)

__all__ = [
    "MARKET_CN",
    "MARKET_HK",
    "BasePlugin",
    "CalendarNotFoundError",
    "DependencyCheckResult",
    "DependencyNotSatisfiedError",
    "InvalidDateError",
    "PluginCategory",
    "PluginManager",
    "PluginRole",
    "TaskRunner",
    "TradeCalendarError",
    "TradeCalendarService",
    "plugin_manager",
    "task_runner",
    "trade_calendar_service",
]
