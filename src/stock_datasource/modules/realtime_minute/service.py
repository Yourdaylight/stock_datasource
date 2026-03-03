"""Query service layer for realtime minute data.

Reads from Redis first, falls back to ClickHouse for historical data.
All ClickHouse queries use parameterized SQL.
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import config as cfg
from .cache_store import get_cache_store
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
    """Heuristic to determine market from ts_code."""
    code = ts_code.upper()
    if code.endswith(".HK"):
        return MarketType.HK.value
    # ETF codes are typically 5 or 6 digits starting with 1/5
    prefix = code.split(".")[0]
    if prefix.startswith(("51", "15", "58", "56")):
        return MarketType.ETF.value
    # Indices typically in INDEX_CODES
    if ts_code in cfg.INDEX_CODES:
        return MarketType.INDEX.value
    return MarketType.A_STOCK.value


class RealtimeMinuteService:
    """Query service for realtime minute data."""

    def __init__(self):
        self._cache = get_cache_store()

    # ------------------------------------------------------------------
    # Basic queries
    # ------------------------------------------------------------------

    def get_minute_data(
        self,
        ts_code: str,
        freq: str = "1min",
        date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get minute bars for a single code."""
        market = _detect_market(ts_code)
        bars = self._cache.get_bars(market, ts_code, freq, date, start_time, end_time)

        # Fallback to ClickHouse
        if not bars:
            bars = self._query_clickhouse(ts_code, freq, date, start_time, end_time)

        return {
            "ts_code": ts_code,
            "freq": freq,
            "count": len(bars),
            "data": bars,
        }

    def get_batch_minute_data(
        self,
        ts_codes: List[str],
        freq: str = "1min",
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Batch query minute data for multiple codes."""
        result: Dict[str, List] = {}
        total_bars = 0
        for code in ts_codes:
            resp = self.get_minute_data(code, freq, date)
            result[code] = resp.get("data", [])
            total_bars += resp.get("count", 0)
        return {
            "freq": freq,
            "total_codes": len(ts_codes),
            "total_bars": total_bars,
            "data": result,
        }

    def get_latest_minute(
        self,
        ts_code: str,
        freq: str = "1min",
    ) -> Optional[Dict[str, Any]]:
        """Get the latest minute bar for a code."""
        market = _detect_market(ts_code)
        return self._cache.get_latest(market, ts_code, freq)

    def get_collect_status(self) -> Dict[str, Any]:
        """Get collection status from Redis."""
        status = self._cache.get_status()
        key_count = self._cache.get_cached_key_count()
        last_time = None
        for v in status.values():
            t = v.get("last_collect_time")
            if t and (last_time is None or t > last_time):
                last_time = t
        return {
            "is_collecting": False,
            "markets": status,
            "last_collect_time": last_time,
            "total_cached_keys": key_count,
        }

    # ------------------------------------------------------------------
    # Ranking queries
    # ------------------------------------------------------------------

    def _rank(
        self,
        sort_key: str,
        ascending: bool = False,
        freq: str = "1min",
        market: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get ranked items by sort_key from latest snapshots."""
        items = self._cache.get_all_latest(market=market, freq=freq)
        # Compute pct_chg if needed
        for item in items:
            if item.get("pct_chg") is None:
                o = item.get("open")
                c = item.get("close")
                if o and c and o != 0:
                    item["pct_chg"] = round((c - o) / o * 100, 2)
                else:
                    item["pct_chg"] = 0

        items.sort(
            key=lambda x: x.get(sort_key) or 0,
            reverse=not ascending,
        )
        return items[:limit]

    def get_top_gainers(self, freq: str = "1min", market: Optional[str] = None, limit: int = 20):
        return {
            "rank_type": "gainers",
            "freq": freq,
            "count": 0,
            "data": self._rank("pct_chg", ascending=False, freq=freq, market=market, limit=limit),
        }

    def get_top_losers(self, freq: str = "1min", market: Optional[str] = None, limit: int = 20):
        return {
            "rank_type": "losers",
            "freq": freq,
            "count": 0,
            "data": self._rank("pct_chg", ascending=True, freq=freq, market=market, limit=limit),
        }

    def get_top_volume(self, freq: str = "1min", market: Optional[str] = None, limit: int = 20):
        return {
            "rank_type": "volume",
            "freq": freq,
            "count": 0,
            "data": self._rank("vol", ascending=False, freq=freq, market=market, limit=limit),
        }

    def get_top_amount(self, freq: str = "1min", market: Optional[str] = None, limit: int = 20):
        return {
            "rank_type": "amount",
            "freq": freq,
            "count": 0,
            "data": self._rank("amount", ascending=False, freq=freq, market=market, limit=limit),
        }

    # ------------------------------------------------------------------
    # Market overview
    # ------------------------------------------------------------------

    def get_market_overview(self, freq: str = "1min") -> Dict[str, Any]:
        """Compute overview stats from latest snapshots."""
        items = self._cache.get_all_latest(freq=freq)
        if not items:
            return {
                "freq": freq, "total": 0, "up_count": 0,
                "down_count": 0, "flat_count": 0,
                "total_vol": None, "total_amount": None,
                "avg_pct_chg": None,
            }

        up = down = flat = 0
        total_vol = 0.0
        total_amount = 0.0
        pct_sum = 0.0

        for item in items:
            o = item.get("open")
            c = item.get("close")
            if o and c and o != 0:
                pct = (c - o) / o * 100
            else:
                pct = 0
            if pct > 0:
                up += 1
            elif pct < 0:
                down += 1
            else:
                flat += 1
            pct_sum += pct
            total_vol += item.get("vol") or 0
            total_amount += item.get("amount") or 0

        total = len(items)
        return {
            "freq": freq,
            "total": total,
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "total_vol": round(total_vol, 2),
            "total_amount": round(total_amount, 2),
            "avg_pct_chg": round(pct_sum / total, 2) if total else None,
        }

    def get_market_stats(self) -> Dict[str, Any]:
        """Extended market stats with limit-up / limit-down and per-market breakdown."""
        items = self._cache.get_all_latest(freq="1min")
        up = down = flat = limit_up = limit_down = 0
        markets: Dict[str, Dict[str, int]] = {}

        for item in items:
            o = item.get("open")
            c = item.get("close")
            if o and c and o != 0:
                pct = (c - o) / o * 100
            else:
                pct = 0

            if pct > 0:
                up += 1
            elif pct < 0:
                down += 1
            else:
                flat += 1
            if pct >= 9.9:
                limit_up += 1
            if pct <= -9.9:
                limit_down += 1

            mt = item.get("market_type", "a_stock")
            if mt not in markets:
                markets[mt] = {"up": 0, "down": 0, "flat": 0}
            if pct > 0:
                markets[mt]["up"] += 1
            elif pct < 0:
                markets[mt]["down"] += 1
            else:
                markets[mt]["flat"] += 1

        return {
            "total": len(items),
            "up_count": up,
            "down_count": down,
            "flat_count": flat,
            "limit_up_count": limit_up,
            "limit_down_count": limit_down,
            "markets": markets,
        }

    # ------------------------------------------------------------------
    # K-line format
    # ------------------------------------------------------------------

    def get_kline_data(
        self,
        ts_code: str,
        freq: str = "1min",
        date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return K-line formatted data compatible with frontend charting."""
        resp = self.get_minute_data(ts_code, freq, date)
        bars = resp.get("data", [])
        klines = []
        for b in bars:
            klines.append({
                "time": b.get("trade_time"),
                "open": b.get("open"),
                "close": b.get("close"),
                "high": b.get("high"),
                "low": b.get("low"),
                "volume": b.get("vol"),
                "amount": b.get("amount"),
            })
        return {
            "ts_code": ts_code,
            "freq": freq,
            "count": len(klines),
            "klines": klines,
        }

    # ------------------------------------------------------------------
    # ClickHouse fallback (parameterized)
    # ------------------------------------------------------------------

    def _query_clickhouse(
        self,
        ts_code: str,
        freq: str = "1min",
        date: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fallback query from ClickHouse using parameterized SQL."""
        market = _detect_market(ts_code)
        table = cfg.get_table_for_market(market)

        conditions = ["ts_code = %(ts_code)s", "freq = %(freq)s"]
        params: Dict[str, Any] = {"ts_code": ts_code, "freq": freq}

        if date:
            conditions.append("toDate(trade_time) = %(trade_date)s")
            params["trade_date"] = datetime.strptime(date, "%Y%m%d").date()
        if start_time:
            conditions.append("trade_time >= %(start_time)s")
            params["start_time"] = start_time
        if end_time:
            conditions.append("trade_time <= %(end_time)s")
            params["end_time"] = end_time

        where = " AND ".join(conditions)
        query = f"""
        SELECT ts_code, trade_time, open, close, high, low, vol, amount, freq
        FROM {table}
        WHERE {where}
        ORDER BY trade_time ASC
        LIMIT 1000
        """
        rows = _execute_query(query, params)
        # Normalize trade_time to string and add market_type
        for r in rows:
            if r.get("trade_time") and hasattr(r["trade_time"], "strftime"):
                r["trade_time"] = r["trade_time"].strftime("%Y-%m-%d %H:%M:%S")
            r["market_type"] = market
        return rows


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_service: Optional[RealtimeMinuteService] = None


def get_realtime_minute_service() -> RealtimeMinuteService:
    global _service
    if _service is None:
        _service = RealtimeMinuteService()
    return _service
