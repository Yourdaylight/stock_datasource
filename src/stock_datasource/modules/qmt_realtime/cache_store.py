"""Cache store for QMT realtime quotes."""

from typing import Any


class QmtRealtimeCacheStore:
    """Small in-memory cache for latest QMT quotes.

    This is the module-local foundation. It can be replaced by Redis using the same
    methods when the runtime deployment needs cross-process sharing.
    """

    def __init__(self):
        self._latest: dict[tuple[str, str], dict[str, Any]] = {}

    def set_latest(self, quote: dict[str, Any]) -> None:
        market = quote.get("market") or "a_stock"
        ts_code = quote.get("ts_code")
        if not ts_code:
            raise ValueError("quote ts_code is required")
        self._latest[(market, ts_code)] = quote.copy()

    def set_many_latest(self, quotes: list[dict[str, Any]]) -> None:
        for quote in quotes:
            self.set_latest(quote)

    def get_latest(self, market: str, ts_code: str) -> dict[str, Any] | None:
        quote = self._latest.get((market, ts_code))
        return quote.copy() if quote else None

    def get_all_latest(self, market: str | None = None) -> list[dict[str, Any]]:
        return [
            quote.copy()
            for (quote_market, _), quote in self._latest.items()
            if market is None or quote_market == market
        ]
