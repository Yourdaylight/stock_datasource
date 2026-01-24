"""Tushare周线行情插件"""

from .extractor import WeeklyExtractor
from .plugin import WeeklyPlugin
from .service import WeeklyService

__all__ = ["WeeklyExtractor", "WeeklyPlugin", "WeeklyService"]
