"""ClickHouse sink for QMT realtime quotes."""

from typing import Any

import pandas as pd

from .cache_store import QmtRealtimeCacheStore


class QmtRealtimeSyncService:
    """Persist cached QMT realtime quotes to ClickHouse."""

    def __init__(self, cache: QmtRealtimeCacheStore | None = None, db=None):
        self.cache = cache or QmtRealtimeCacheStore()
        if db is None:
            from stock_datasource.models.database import db_client

            db = db_client
        self.db = db
        self.table_name = "ods_qmt_realtime_quote"

    def sync_latest(self, market: str | None = None) -> dict[str, Any]:
        quotes = self.cache.get_all_latest(market)
        if not quotes:
            return {"status": "no_data", "table": self.table_name, "records": 0}

        data = pd.DataFrame(quotes)
        self.db.insert_dataframe(self.table_name, data)
        return {"status": "success", "table": self.table_name, "records": len(data)}
