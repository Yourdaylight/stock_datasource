"""QMT realtime quote collector."""

from typing import Any

from stock_datasource.modules.qmt_gateway.client import QmtGatewayClient

from .cache_store import QmtRealtimeCacheStore
from .normalizer import normalize_realtime_quotes


class QmtRealtimeCollector:
    """Collect realtime quotes from QMT gateway into cache."""

    def __init__(
        self,
        client: QmtGatewayClient | None = None,
        cache: QmtRealtimeCacheStore | None = None,
    ):
        self.client = client or QmtGatewayClient()
        self.cache = cache or QmtRealtimeCacheStore()

    def collect(self, symbols: list[str], market: str | None = None) -> list[dict[str, Any]]:
        raw = self.client.get_realtime_quotes(symbols, market=market)
        quotes = normalize_realtime_quotes(raw, market=market)
        self.cache.set_many_latest(quotes)
        return quotes
