"""TuShare rt_idx_k plugin - 指数实时日线."""

from stock_datasource.plugins.tushare_rt_idx_k.extractor import RtIdxKExtractor
from stock_datasource.plugins.tushare_rt_idx_k.plugin import TuShareRtIdxKPlugin

__all__ = ["RtIdxKExtractor", "TuShareRtIdxKPlugin"]
