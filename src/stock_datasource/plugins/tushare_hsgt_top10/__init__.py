"""Tushare沪深股通十大成交股插件"""

from .extractor import HsgtTop10Extractor
from .plugin import HsgtTop10Plugin
from .service import HsgtTop10Service

__all__ = ["HsgtTop10Extractor", "HsgtTop10Plugin", "HsgtTop10Service"]
