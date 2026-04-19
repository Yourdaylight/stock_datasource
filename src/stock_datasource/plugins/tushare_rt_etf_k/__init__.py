"""TuShare rt_etf_k plugin - ETF实时日线."""

from stock_datasource.plugins.tushare_rt_etf_k.extractor import RtEtfKExtractor
from stock_datasource.plugins.tushare_rt_etf_k.plugin import TuShareRtEtfKPlugin

__all__ = ["RtEtfKExtractor", "TuShareRtEtfKPlugin"]
