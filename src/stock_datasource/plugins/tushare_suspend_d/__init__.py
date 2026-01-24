"""Tushare每日停复牌信息插件"""

from .extractor import SuspendDExtractor
from .plugin import SuspendDPlugin
from .service import SuspendDService

__all__ = ["SuspendDExtractor", "SuspendDPlugin", "SuspendDService"]
