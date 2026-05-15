"""Sentinel implementations for the hierarchical stock selection system."""

from __future__ import annotations

from ..core.base_sentinel import BaseSentinel
from .capital_flow_sentinel import CapitalFlowSentinel
from .financial_anomaly_sentinel import FinancialAnomalySentinel
from .ma_crossover_sentinel import MACrossoverSentinel
from .market_risk_sentinel import MarketRiskSentinel
from .news_sentiment_sentinel import NewsSentimentSentinel
from .pool_change_sentinel import PoolChangeSentinel
from .rps_breakout_sentinel import RPSBreakoutSentinel
from .sector_flow_sentinel import SectorFlowSentinel
from .volume_anomaly_sentinel import VolumeAnomalySentinel

__all__ = [
    "MarketRiskSentinel",
    "SectorFlowSentinel",
    "MACrossoverSentinel",
    "VolumeAnomalySentinel",
    "NewsSentimentSentinel",
    "CapitalFlowSentinel",
    "RPSBreakoutSentinel",
    "FinancialAnomalySentinel",
    "PoolChangeSentinel",
    "create_all_sentinels",
]


def create_all_sentinels(config: dict | None = None) -> list[BaseSentinel]:
    """Factory function to create all sentinel instances.

    Args:
        config: Optional configuration dict passed to each sentinel.

    Returns:
        List of all sentinel instances ready for scanning.
    """
    cfg = config or {}
    return [
        MarketRiskSentinel(config=cfg),
        SectorFlowSentinel(config=cfg),
        MACrossoverSentinel(config=cfg),
        VolumeAnomalySentinel(config=cfg),
        NewsSentimentSentinel(config=cfg),
        CapitalFlowSentinel(config=cfg),
        RPSBreakoutSentinel(config=cfg),
        FinancialAnomalySentinel(config=cfg),
        PoolChangeSentinel(config=cfg),
    ]
