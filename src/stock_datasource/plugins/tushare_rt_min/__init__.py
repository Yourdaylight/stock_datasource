"""TuShare rt_min plugin - A股实时分钟K线数据."""

from .plugin import TuShareRtMinPlugin

try:
    from .service import RtMinService
except Exception:
    RtMinService = None

__all__ = ["TuShareRtMinPlugin", "RtMinService"]
