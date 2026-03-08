"""TuShare rt_etf_min plugin - ETF实时分钟K线数据."""

from .plugin import TuShareRtEtfMinPlugin

try:
    from .service import RtEtfMinService
except Exception:
    RtEtfMinService = None

__all__ = ["TuShareRtEtfMinPlugin", "RtEtfMinService"]
