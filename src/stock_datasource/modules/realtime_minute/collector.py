"""Data collector for realtime minute data from Tushare APIs.

Supports four markets: A-stock, ETF, Index, HK.
Each market has a dedicated collect method and the unified ``collect_all``
orchestrates parallel collection with rate limiting.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

from . import config as cfg
from .schemas import MarketType

logger = logging.getLogger(__name__)


class RealtimeMinuteCollector:
    """Collect realtime minute bars from Tushare APIs."""

    def __init__(self):
        if not settings.TUSHARE_TOKEN:
            raise ValueError("TUSHARE_TOKEN not configured")
        ts.set_token(settings.TUSHARE_TOKEN)
        self.pro = ts.pro_api()

        # Rate limiting state
        self._last_call_time: float = 0
        self._min_interval: float = cfg.MIN_CALL_INTERVAL

        # Standard output fields
        self._fields = [
            "ts_code", "trade_time", "open", "close",
            "high", "low", "vol", "amount",
        ]

    # ------------------------------------------------------------------
    # Rate limiter
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call_time = time.time()

    # ------------------------------------------------------------------
    # Low-level API wrappers (with retry)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(cfg.MAX_RETRIES),
           wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_rt_min(self, ts_code: str, freq: str = "1min") -> pd.DataFrame:
        """Call rt_min API for A-stock / ETF."""
        self._rate_limit()
        try:
            result = self.pro.rt_min(ts_code=ts_code, freq=freq)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("rt_min failed for %s freq=%s: %s", ts_code, freq, e)
            raise

    @retry(stop=stop_after_attempt(cfg.MAX_RETRIES),
           wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_rt_idx_min(self, ts_code: str, freq: str = "1min") -> pd.DataFrame:
        """Call rt_idx_min API for index."""
        self._rate_limit()
        try:
            result = self.pro.rt_idx_min(ts_code=ts_code, freq=freq)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("rt_idx_min failed for %s freq=%s: %s", ts_code, freq, e)
            raise

    @retry(stop=stop_after_attempt(cfg.MAX_RETRIES),
           wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_hk_mins(self, ts_code: str, freq: str = "1min",
                      start_date: Optional[str] = None,
                      end_date: Optional[str] = None) -> pd.DataFrame:
        """Call hk_mins API for HK stocks."""
        self._rate_limit()
        try:
            params: Dict[str, Any] = {"ts_code": ts_code, "freq": freq}
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            result = self.pro.hk_mins(**params)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("hk_mins failed for %s freq=%s: %s", ts_code, freq, e)
            raise

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(df: pd.DataFrame, market: MarketType, freq: str) -> pd.DataFrame:
        """Ensure consistent column set and types."""
        if df.empty:
            return df

        # Rename columns if needed (hk_mins may use different names)
        rename_map = {}
        if "trade_date" in df.columns and "trade_time" not in df.columns:
            rename_map["trade_date"] = "trade_time"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Ensure required columns exist
        for col in ["ts_code", "trade_time", "open", "close", "high", "low", "vol", "amount"]:
            if col not in df.columns:
                df[col] = None

        # Parse trade_time
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")

        # Add metadata
        df["market_type"] = market.value
        df["freq"] = freq

        return df

    # ------------------------------------------------------------------
    # Market-specific collectors
    # ------------------------------------------------------------------

    def collect_astock(self, freq: str = "1min") -> pd.DataFrame:
        """Collect A-stock realtime minute data in batches."""
        all_dfs: List[pd.DataFrame] = []
        for batch in cfg.ASTOCK_BATCHES:
            for ts_code in batch:
                try:
                    df = self._call_rt_min(ts_code, freq)
                    if not df.empty:
                        df = self._normalize(df, MarketType.A_STOCK, freq)
                        all_dfs.append(df)
                except Exception as e:
                    logger.warning("A-stock collect failed for %s: %s", ts_code, e)
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    def collect_etf(self, freq: str = "1min") -> pd.DataFrame:
        """Collect ETF realtime minute data."""
        all_dfs: List[pd.DataFrame] = []
        for ts_code in cfg.HOT_ETF_CODES:
            try:
                df = self._call_rt_min(ts_code, freq)
                if not df.empty:
                    df = self._normalize(df, MarketType.ETF, freq)
                    all_dfs.append(df)
            except Exception as e:
                logger.warning("ETF collect failed for %s: %s", ts_code, e)
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    def collect_index(self, freq: str = "1min") -> pd.DataFrame:
        """Collect index realtime minute data."""
        all_dfs: List[pd.DataFrame] = []
        for ts_code in cfg.INDEX_CODES:
            try:
                df = self._call_rt_idx_min(ts_code, freq)
                if not df.empty:
                    df = self._normalize(df, MarketType.INDEX, freq)
                    all_dfs.append(df)
            except Exception as e:
                logger.warning("Index collect failed for %s: %s", ts_code, e)
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    def collect_hk(self, freq: str = "1min") -> pd.DataFrame:
        """Collect HK stock minute data."""
        all_dfs: List[pd.DataFrame] = []
        today = datetime.now().strftime("%Y-%m-%d")
        for ts_code in cfg.HK_CODES:
            try:
                df = self._call_hk_mins(
                    ts_code, freq,
                    start_date=f"{today} 09:00:00",
                    end_date=f"{today} 16:30:00",
                )
                if not df.empty:
                    df = self._normalize(df, MarketType.HK, freq)
                    all_dfs.append(df)
            except Exception as e:
                logger.warning("HK collect failed for %s: %s", ts_code, e)
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Unified entry point
    # ------------------------------------------------------------------

    def collect_all(
        self,
        freq: str = "1min",
        markets: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Collect all configured markets.

        Args:
            freq: Bar frequency.
            markets: List of market names to collect.
                     Defaults to all configured markets.

        Returns:
            Dict mapping market name to its DataFrame.
        """
        if markets is None:
            markets = ["a_stock", "etf", "index", "hk"]

        results: Dict[str, pd.DataFrame] = {}
        collectors = {
            "a_stock": self.collect_astock,
            "etf": self.collect_etf,
            "index": self.collect_index,
            "hk": self.collect_hk,
        }

        for market in markets:
            fn = collectors.get(market)
            if fn is None:
                logger.warning("Unknown market: %s", market)
                continue
            try:
                logger.info("Collecting %s freq=%s ...", market, freq)
                df = fn(freq)
                results[market] = df
                rows = len(df) if not df.empty else 0
                logger.info("Collected %s: %d rows", market, rows)
            except Exception as e:
                logger.error("Collection failed for market %s: %s", market, e)
                results[market] = pd.DataFrame()

        return results


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_collector: Optional[RealtimeMinuteCollector] = None


def get_collector() -> RealtimeMinuteCollector:
    """Get collector singleton."""
    global _collector
    if _collector is None:
        _collector = RealtimeMinuteCollector()
    return _collector
