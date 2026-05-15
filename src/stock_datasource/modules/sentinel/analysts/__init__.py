"""Analyst agents for the sentinel system."""

from ..core.base_analyst import BaseAnalyst


def create_all_analysts() -> list[BaseAnalyst]:
    from .market_environment_analyst import MarketEnvironmentAnalyst
    from .sector_rotation_analyst import SectorRotationAnalyst
    from .stock_quality_analyst import StockQualityAnalyst
    from .timing_analyst import TimingAnalyst

    return [
        MarketEnvironmentAnalyst(),
        SectorRotationAnalyst(),
        StockQualityAnalyst(),
        TimingAnalyst(),
    ]
