"""TuShare idx_mins plugin - 指数历史分钟行情."""
from stock_datasource.plugins.tushare_idx_mins.plugin import TuShareIdxMinsPlugin
from stock_datasource.plugins.tushare_idx_mins.extractor import IdxMinsExtractor

__all__ = ["TuShareIdxMinsPlugin", "IdxMinsExtractor"]
