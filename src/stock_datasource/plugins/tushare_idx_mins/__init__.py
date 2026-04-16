"""TuShare idx_mins plugin - 指数历史分钟行情."""

from stock_datasource.plugins.tushare_idx_mins.extractor import IdxMinsExtractor
from stock_datasource.plugins.tushare_idx_mins.plugin import TuShareIdxMinsPlugin

__all__ = ["IdxMinsExtractor", "TuShareIdxMinsPlugin"]
