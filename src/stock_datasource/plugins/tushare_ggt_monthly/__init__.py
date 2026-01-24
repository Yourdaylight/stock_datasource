"""港股通每月成交统计插件"""

from stock_datasource.plugins.tushare_ggt_monthly.extractor import GgtMonthlyExtractor
from stock_datasource.plugins.tushare_ggt_monthly.plugin import GgtMonthlyPlugin
from stock_datasource.plugins.tushare_ggt_monthly.service import GgtMonthlyService

__all__ = ["GgtMonthlyExtractor", "GgtMonthlyPlugin", "GgtMonthlyService"]
