"""TuShare rt_k plugin - 沪深京实时日线."""

from stock_datasource.plugins.tushare_rt_k.extractor import RtKExtractor
from stock_datasource.plugins.tushare_rt_k.plugin import TuShareRtKPlugin

__all__ = ["RtKExtractor", "TuShareRtKPlugin"]
