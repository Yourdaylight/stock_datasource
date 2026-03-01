"""Query service layer for realtime daily K-line data."""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import config as cfg
from .cache import get_cache_store
from .schemas import MarketType

logger = logging.getLogger(__name__)


def _get_db():
    from stock_datasource.models.database import db_client
    return db_client


def _safe(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def _execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    db = _get_db()
    try:
        df = db.execute_query(query, params or {})
    except Exception as e:
        logger.warning("ClickHouse query failed: %s", e)
        return []
    if df is None or df.empty:
        return []
    return [{k: _safe(v) for k, v in r.items()} for r in df.to_dict("records")]


def _detect_market(ts_code: str) -> str:
    code = ts_code.upper()
    if code.endswith(".HK"):
        return MarketType.HK.value
    prefix = code.split(".")[0]
    if prefix.startswith(("51", "15", "58", "56")):
        return MarketType.ETF.value
    if ts_code in cfg.INDEX_CODES:
        return MarketType.INDEX.value
    return MarketType.A_STOCK.value


def _normalize_market(market: Optional[str]) -> Optional[str]:
    if not market:
        return None
    market = market.strip().lower()
    alias = {
        "cn": "a_stock",
        "astock": "a_stock",
        "stock": "a_stock",
        "sz": "a_stock",
        "sh": "a_stock",
    }
    return alias.get(market, market)


class RealtimeKlineService:
    def __init__(self):
        self._cache = get_cache_store()

    def get_latest(self, ts_code: str, market: Optional[str] = None) -> Dict[str, Any]:
        mkt = _normalize_market(market) or _detect_market(ts_code)
        data = self._cache.get_latest(mkt, ts_code)
        if data:
            return {"ts_code": ts_code, "market": mkt, "data": data, "source": "redis"}

        ch_data = self._query_clickhouse_latest(ts_code, mkt)
        return {"ts_code": ts_code, "market": mkt, "data": ch_data, "source": "clickhouse"}

    def get_batch_latest(self, market: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        mkt = _normalize_market(market)
        items = self._cache.get_all_latest(market=mkt)
        if limit and len(items) > limit:
            items = items[:limit]
        return {"market": mkt, "count": len(items), "data": items}

    def get_collect_status(self) -> Dict[str, Any]:
        from .scheduler import get_runtime
        from .cloud_push import _is_push_enabled

        rt = get_runtime()
        status = self._cache.get_status()
        key_count = self._cache.get_cached_key_count()
        last_time = None
        for v in status.values():
            if isinstance(v, dict):
                t = v.get("last_collect_time")
                if t and (last_time is None or t > last_time):
                    last_time = t
        return {
            "is_running": rt.is_running,
            "workers": rt.health(),
            "markets": status,
            "last_collect_time": last_time,
            "total_cached_keys": key_count,
            "push_enabled": _is_push_enabled(),
        }

    def _query_clickhouse_latest(self, ts_code: str, market: str) -> Optional[Dict[str, Any]]:
        table = cfg.get_table_for_market(market)
        query = f"""
        SELECT ts_code, trade_date, trade_time, name,
               open, close, high, low, pre_close, vol, amount, pct_chg,
               bid, ask, collected_at, version
        FROM {table}
        WHERE ts_code = %(ts_code)s
        ORDER BY trade_date DESC, version DESC
        LIMIT 1
        """
        rows = _execute_query(query, {"ts_code": ts_code})
        if not rows:
            return None
        row = rows[0]
        if row.get("trade_date") and hasattr(row["trade_date"], "strftime"):
            row["trade_date"] = row["trade_date"].strftime("%Y%m%d")
        if row.get("collected_at") and hasattr(row["collected_at"], "strftime"):
            row["collected_at"] = row["collected_at"].strftime("%Y-%m-%d %H:%M:%S")
        row["market"] = market
        return row

    def query_daily(self, market: str, trade_date: str, limit: int = 5000) -> List[Dict[str, Any]]:
        mkt = _normalize_market(market) or market
        table = cfg.get_table_for_market(mkt)
        query = f"""
        SELECT ts_code, trade_date, trade_time, name,
               open, close, high, low, pre_close, vol, amount, pct_chg,
               bid, ask, collected_at, version
        FROM {table}
        WHERE trade_date = %(trade_date)s
        ORDER BY ts_code
        LIMIT %(limit)s
        """
        try:
            td = datetime.strptime(trade_date, "%Y%m%d").date()
        except ValueError:
            td = trade_date

        rows = _execute_query(query, {"trade_date": td, "limit": limit})
        for r in rows:
            if r.get("trade_date") and hasattr(r["trade_date"], "strftime"):
                r["trade_date"] = r["trade_date"].strftime("%Y%m%d")
            if r.get("collected_at") and hasattr(r["collected_at"], "strftime"):
                r["collected_at"] = r["collected_at"].strftime("%Y-%m-%d %H:%M:%S")
            r["market"] = mkt
        return rows


_service: Optional[RealtimeKlineService] = None


def get_realtime_kline_service() -> RealtimeKlineService:
    global _service
    if _service is None:
        _service = RealtimeKlineService()
    return _service
