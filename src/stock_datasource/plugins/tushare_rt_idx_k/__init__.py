"""TuShare rt_idx_k plugin - 指数实时日线."""
from stock_datasource.plugins.tushare_rt_idx_k.plugin import TuShareRtIdxKPlugin
from stock_datasource.plugins.tushare_rt_idx_k.extractor import RtIdxKExtractor

__all__ = ["TuShareRtIdxKPlugin", "RtIdxKExtractor"]
