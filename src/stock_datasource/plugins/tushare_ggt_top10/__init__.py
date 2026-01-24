"""港股通十大成交股插件"""

from stock_datasource.plugins.tushare_ggt_top10.extractor import GgtTop10Extractor
from stock_datasource.plugins.tushare_ggt_top10.plugin import GgtTop10Plugin
from stock_datasource.plugins.tushare_ggt_top10.service import GgtTop10Service

__all__ = ["GgtTop10Extractor", "GgtTop10Plugin", "GgtTop10Service"]
