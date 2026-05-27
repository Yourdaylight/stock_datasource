"""Query service for QMT realtime quotes."""

from typing import Any

from .cache_store import QmtRealtimeCacheStore


class QmtRealtimeService:
    """Cache-first query service for QMT realtime data."""

    def __init__(self, cache: QmtRealtimeCacheStore | None = None):
        self.cache = cache or QmtRealtimeCacheStore()

    def get_latest(self, ts_code: str, market: str = "a_stock") -> dict[str, Any] | None:
        return self.cache.get_latest(market, ts_code)

    def get_batch_latest(self, market: str | None = None, limit: int = 100) -> dict[str, Any]:
        items = self.cache.get_all_latest(market)
        if limit:
            items = items[:limit]
        return {"market": market, "count": len(items), "data": items}
