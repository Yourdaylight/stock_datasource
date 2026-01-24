"""港股通每日成交统计插件"""

from stock_datasource.plugins.tushare_ggt_daily.extractor import GgtDailyExtractor
from stock_datasource.plugins.tushare_ggt_daily.plugin import GgtDailyPlugin
from stock_datasource.plugins.tushare_ggt_daily.service import GgtDailyService

__all__ = ["GgtDailyExtractor", "GgtDailyPlugin", "GgtDailyService"]
