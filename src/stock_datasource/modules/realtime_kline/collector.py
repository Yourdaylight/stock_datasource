"""Data collector for realtime daily K-line snapshots.

Implements the 1.5-second collection loop with per-market adaptive backoff
as specified in design.md §Timing Model.
"""

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from stock_datasource.config.settings import settings
from stock_datasource.plugins.tushare_rt_etf_k.extractor import RtEtfKExtractor
from stock_datasource.plugins.tushare_rt_hk_k.extractor import RtHkKExtractor
from stock_datasource.plugins.tushare_rt_idx_k.extractor import RtIdxKExtractor
from stock_datasource.plugins.tushare_rt_k.extractor import RtKExtractor

from . import config as cfg
from .schemas import MarketType
from . import metrics as m

logger = logging.getLogger(__name__)


def _safe_value(v: Any) -> Any:
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


class BackoffController:
    """Per-market adaptive backoff: 1.5s → 3s → 5s and recovery."""

    def __init__(self):
        self._levels = cfg.BACKOFF_LEVELS  # [1.5, 3.0, 5.0]
        self._current_idx: Dict[str, int] = {}
        self._consecutive_fails: Dict[str, int] = {}
        self._consecutive_ok: Dict[str, int] = {}

    def current_interval(self, market: str) -> float:
        idx = self._current_idx.get(market, 0)
        return self._levels[idx]

    def record_success(self, market: str) -> None:
        self._consecutive_fails[market] = 0
        ok = self._consecutive_ok.get(market, 0) + 1
        self._consecutive_ok[market] = ok
        idx = self._current_idx.get(market, 0)
        if ok >= cfg.BACKOFF_RECOVER_THRESHOLD and idx > 0:
            self._current_idx[market] = idx - 1
            self._consecutive_ok[market] = 0
            m.collector_backoff_level(market, self._levels[idx - 1])
            logger.info("Backoff recover %s → %.1fs", market, self._levels[idx - 1])

    def record_failure(self, market: str) -> None:
        self._consecutive_ok[market] = 0
        fails = self._consecutive_fails.get(market, 0) + 1
        self._consecutive_fails[market] = fails
        idx = self._current_idx.get(market, 0)
        if fails >= cfg.BACKOFF_FAIL_THRESHOLD and idx < len(self._levels) - 1:
            self._current_idx[market] = idx + 1
            self._consecutive_fails[market] = 0
            m.collector_backoff_level(market, self._levels[idx + 1])
            logger.warning("Backoff escalate %s → %.1fs", market, self._levels[idx + 1])


class RealtimeKlineCollector:
    """Collect realtime daily K-line snapshots from 4 TuShare APIs."""

    def __init__(self):
        self.rt_k_extractor = RtKExtractor()
        self.rt_etf_extractor = RtEtfKExtractor()
        self.rt_idx_extractor = RtIdxKExtractor()
        self.rt_hk_extractor = RtHkKExtractor()
        self.backoff = BackoffController()
        self.market_inner_concurrency = max(1, int(settings.RT_KLINE_MARKET_INNER_CONCURRENCY))
        self._hk_cursor = 0
        self._hk_cursor_lock = threading.Lock()

    def _pick_hk_patterns(self) -> List[str]:
        patterns = cfg.HK_PATTERNS
        if not patterns:
            return []

        per_round = max(1, min(int(cfg.HK_PATTERNS_PER_ROUND), len(patterns)))
        with self._hk_cursor_lock:
            start = self._hk_cursor
            selected = [patterns[(start + i) % len(patterns)] for i in range(per_round)]
            self._hk_cursor = (start + per_round) % len(patterns)
        return selected

    def _collect_parallel(self, items: List[Any], extract_fn, market_label: str) -> pd.DataFrame:
        if not items:
            return pd.DataFrame()

        max_workers = min(len(items), self.market_inner_concurrency)
        if max_workers <= 1:
            dfs = []
            for item in items:
                try:
                    df = extract_fn(item)
                    if not df.empty:
                        dfs.append(df)
                except Exception as e:
                    logger.warning("%s collect failed for %s: %s", market_label, item, e)
            return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

        dfs = []
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"rt-{market_label}") as executor:
            future_map = {executor.submit(extract_fn, item): item for item in items}
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    df = future.result()
                    if not df.empty:
                        dfs.append(df)
                except Exception as e:
                    logger.warning("%s collect failed for %s: %s", market_label, item, e)

        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    # ------------------------------------------------------------------
    # Normalize
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(df: pd.DataFrame, market: MarketType) -> List[Dict[str, Any]]:
        """Normalize a DataFrame into a list of canonical snapshot dicts."""
        if df.empty:
            return []

        df = df.copy()

        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
            df["trade_date"] = df["trade_time"].apply(
                lambda x: x.strftime("%Y%m%d") if pd.notna(x) else datetime.now().strftime("%Y%m%d")
            )
            df["trade_time"] = df["trade_time"].apply(
                lambda x: x.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(x) else None
            )
        else:
            df["trade_date"] = datetime.now().strftime("%Y%m%d")
            df["trade_time"] = None

        for col in [
            "ts_code", "name", "open", "close", "high", "low", "pre_close",
            "vol", "amount", "pct_chg", "bid", "ask",
        ]:
            if col not in df.columns:
                df[col] = None

        if "bid" not in df.columns or df["bid"].isna().all():
            if "bid_price1" in df.columns:
                df["bid"] = df["bid_price1"]
        if "ask" not in df.columns or df["ask"].isna().all():
            if "ask_price1" in df.columns:
                df["ask"] = df["ask_price1"]

        if market in (MarketType.INDEX, MarketType.HK):
            df["amount"] = None

        mask = df["pct_chg"].isna() & df["pre_close"].notna() & df["close"].notna()
        if mask.any():
            df.loc[mask, "pct_chg"] = (
                (df.loc[mask, "close"] - df.loc[mask, "pre_close"]) / df.loc[mask, "pre_close"] * 100
            ).round(2)

        for col in ("open", "close", "high", "low", "pre_close", "vol", "amount", "pct_chg", "bid", "ask"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

        now = datetime.now()
        collected_at = now.strftime("%Y-%m-%d %H:%M:%S")
        version = int(now.timestamp() * 1000)

        rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            rows.append({
                "ts_code": row.get("ts_code"),
                "name": _safe_value(row.get("name")),
                "trade_date": row.get("trade_date"),
                "trade_time": row.get("trade_time"),
                "open": _safe_value(row.get("open")),
                "high": _safe_value(row.get("high")),
                "low": _safe_value(row.get("low")),
                "close": _safe_value(row.get("close")),
                "pre_close": _safe_value(row.get("pre_close")),
                "vol": _safe_value(row.get("vol")),
                "amount": _safe_value(row.get("amount")),
                "pct_chg": _safe_value(row.get("pct_chg")),
                "bid": _safe_value(row.get("bid")),
                "ask": _safe_value(row.get("ask")),
                "market": market.value,
                "source_api": cfg.MARKET_API_MAP.get(market.value, ""),
                "collected_at": collected_at,
                "version": version,
            })
        return rows

    # ------------------------------------------------------------------
    # Per-market collection
    # ------------------------------------------------------------------
    @staticmethod
    def _in_window_hms(window: tuple[str, str]) -> bool:
        now_hms = datetime.now().strftime("%H:%M:%S")
        start_hms = f"{window[0]}:00"
        end_hms = f"{window[1]}:00"
        return start_hms <= now_hms <= end_hms

    def _is_cn_collect_time(self) -> bool:
        return any(self._in_window_hms(window) for window in cfg.CN_TRADING_HOURS)

    def _is_hk_collect_time(self) -> bool:
        return any(self._in_window_hms(window) for window in cfg.HK_TRADING_HOURS)

    def _collect_market(self, market: str) -> List[Dict[str, Any]]:
        market_enum = MarketType(market)

        t0 = time.monotonic()
        try:
            if market == "a_stock":
                raw = self._collect_parallel(cfg.ASTOCK_PATTERNS, self.rt_k_extractor.extract, "a_stock")
            elif market == "etf":
                raw = self._collect_parallel(
                    cfg.ETF_QUERY_PATTERNS,
                    lambda q: self.rt_etf_extractor.extract(ts_code=q["ts_code"], topic=q.get("topic")),
                    "etf",
                )
            elif market == "index":
                raw = self._collect_parallel(
                    cfg.INDEX_QUERY_PATTERNS,
                    lambda q: self.rt_idx_extractor.extract(ts_code=q["ts_code"], fields=q.get("fields")),
                    "index",
                )
            elif market == "hk":
                hk_patterns = self._pick_hk_patterns()
                logger.info("HK round-robin shards: %s", hk_patterns)
                raw = self._collect_parallel(hk_patterns, self.rt_hk_extractor.extract, "hk")
            else:
                raw = pd.DataFrame()

            rows = self._normalize(raw, market_enum)
            latency_ms = (time.monotonic() - t0) * 1000
            m.collector_call(market, True, latency_ms)
            self.backoff.record_success(market)
            return rows

        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000
            m.collector_call(market, False, latency_ms)
            self.backoff.record_failure(market)
            logger.error("Collection failed for %s: %s", market, e)
            return []

    def collect_all(self, markets: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        if markets is None:
            markets = list(cfg.CLICKHOUSE_TABLES.keys())

        valid_markets = [m for m in markets if m in cfg.CLICKHOUSE_TABLES]
        if not self._is_cn_collect_time():
            valid_markets = [m for m in valid_markets if m not in ("a_stock", "etf", "index")]
        if not self._is_hk_collect_time():
            valid_markets = [m for m in valid_markets if m != "hk"]
        if not valid_markets:
            return {}

        max_workers = min(len(valid_markets), len(cfg.CLICKHOUSE_TABLES))
        results: Dict[str, List[Dict[str, Any]]] = {m: [] for m in valid_markets}

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rt-kline-collect") as executor:
            future_map = {executor.submit(self._collect_market, market): market for market in valid_markets}
            for future in as_completed(future_map):
                market = future_map[future]
                try:
                    rows = future.result()
                    results[market] = rows
                    logger.info("Collected %s: %d rows", market, len(rows))
                except Exception as e:
                    logger.error("Collected %s failed: %s", market, e, exc_info=True)
                    results[market] = []

        return results


_collector: Optional[RealtimeKlineCollector] = None


def get_collector() -> RealtimeKlineCollector:
    global _collector
    if _collector is None:
        _collector = RealtimeKlineCollector()
    return _collector
