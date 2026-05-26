"""QMT historical data provider."""

from types import SimpleNamespace

import pandas as pd

from stock_datasource.modules.qmt_gateway.client import QmtGatewayClient

from .normalizer import normalize_daily_bars, normalize_minute_bars


class QmtHistoricalProvider:
    """Historical bar provider backed by a QMT gateway."""

    metadata = SimpleNamespace(name="qmt", display_name="QMT")

    def __init__(self, client: QmtGatewayClient | None = None):
        self.client = client or QmtGatewayClient()

    def get_daily_bars(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        count: int | None = None,
    ) -> pd.DataFrame:
        """Return normalized daily bars."""
        rows = self.client.get_history_bars(
            ts_code=ts_code,
            period="1d",
            start_date=start_date,
            end_date=end_date,
            count=count,
        )
        return normalize_daily_bars(rows, ts_code=ts_code)

    def get_minute_bars(
        self,
        ts_code: str,
        freq: str = "1m",
        start_time: str | None = None,
        end_time: str | None = None,
        count: int | None = None,
    ) -> pd.DataFrame:
        """Return normalized minute bars."""
        rows = self.client.get_history_bars(
            ts_code=ts_code,
            period=freq,
            start_date=start_time,
            end_date=end_time,
            count=count,
        )
        return normalize_minute_bars(rows, ts_code=ts_code, freq=freq)
