"""Base abstractions for historical market data providers."""

from typing import Protocol

import pandas as pd


class ProviderMetadata(Protocol):
    """Structural metadata for a historical data provider."""

    name: str
    display_name: str | None


class HistoricalDataProvider(Protocol):
    """Protocol for providers that return normalized historical bars."""

    metadata: ProviderMetadata

    def get_daily_bars(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        count: int | None = None,
    ) -> pd.DataFrame:
        """Return canonical daily bars."""

    def get_minute_bars(
        self,
        ts_code: str,
        freq: str = "1m",
        start_time: str | None = None,
        end_time: str | None = None,
        count: int | None = None,
    ) -> pd.DataFrame:
        """Return canonical minute bars."""
