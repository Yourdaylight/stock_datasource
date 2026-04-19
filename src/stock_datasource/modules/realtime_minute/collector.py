"""Data collector for realtime minute data from Tushare APIs.

Supports two collection channels:
- a_etf: A-stock + ETF merged, using batch rt_min API (up to 300 codes/request)
  with asyncio coroutines for high concurrency.
- index: Index codes, using rt_idx_min API (one-by-one).

HK stocks are NOT supported for realtime minute data.
"""

import asyncio
import logging
import time

import pandas as pd
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

from . import config as cfg
from .schemas import MarketType

logger = logging.getLogger(__name__)


class RealtimeMinuteCollector:
    """Collect realtime minute bars from Tushare APIs with batch & asyncio concurrency."""

    def __init__(self):
        if not settings.TUSHARE_TOKEN:
            raise ValueError("TUSHARE_TOKEN not configured")
        ts.set_token(settings.TUSHARE_TOKEN)
        self.pro = ts.pro_api()

        # Rate limiting state (shared across concurrent calls via lock)
        self._last_call_time: float = 0
        self._min_interval: float = cfg.MIN_CALL_INTERVAL
        self._rate_lock = __import__("threading").Lock()

    # ------------------------------------------------------------------
    # Rate limiter (thread-safe, called from asyncio.to_thread)
    # ------------------------------------------------------------------

    def _rate_limit(self) -> None:
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call_time = time.time()

    # ------------------------------------------------------------------
    # Synchronous API calls (run in thread pool via asyncio.to_thread)
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_rt_min_batch(
        self, ts_codes: list[str], freq: str = "1MIN"
    ) -> pd.DataFrame:
        """Call rt_min API with multiple codes (up to 300, comma-separated)."""
        self._rate_limit()
        codes_str = ",".join(ts_codes)
        try:
            result = self.pro.rt_min(ts_code=codes_str, freq=freq)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error(
                "rt_min batch failed for %d codes (first=%s): %s",
                len(ts_codes),
                ts_codes[0] if ts_codes else "?",
                e,
            )
            raise

    @retry(
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_rt_min_single(self, ts_code: str, freq: str = "1MIN") -> pd.DataFrame:
        """Call rt_min API for a single code (fallback)."""
        self._rate_limit()
        try:
            result = self.pro.rt_min(ts_code=ts_code, freq=freq)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("rt_min failed for %s: %s", ts_code, e)
            raise

    @retry(
        stop=stop_after_attempt(cfg.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_rt_idx_min(self, ts_code: str, freq: str = "1MIN") -> pd.DataFrame:
        """Call rt_idx_min API for index."""
        self._rate_limit()
        try:
            result = self.pro.rt_idx_min(ts_code=ts_code, freq=freq)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("rt_idx_min failed for %s: %s", ts_code, e)
            raise

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(df: pd.DataFrame, market: MarketType, freq: str) -> pd.DataFrame:
        """Ensure consistent column set and types."""
        if df.empty:
            return df

        # Rename columns if needed (API may return different names)
        rename_map = {}
        if "time" in df.columns and "trade_time" not in df.columns:
            rename_map["time"] = "trade_time"
        if "trade_date" in df.columns and "trade_time" not in df.columns:
            rename_map["trade_date"] = "trade_time"
        if "code" in df.columns and "ts_code" not in df.columns:
            rename_map["code"] = "ts_code"
        if "volume" in df.columns and "vol" not in df.columns:
            rename_map["volume"] = "vol"
        if rename_map:
            df = df.rename(columns=rename_map)

        # Ensure required columns exist
        for col in [
            "ts_code",
            "trade_time",
            "open",
            "close",
            "high",
            "low",
            "vol",
            "amount",
        ]:
            if col not in df.columns:
                df[col] = None

        # Parse trade_time
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")

        # Add freq
        df["freq"] = freq

        # Infer market_type from ts_code when market is A_STOCK (covers A+ETF merged batch)
        if market == MarketType.A_STOCK and "ts_code" in df.columns:
            # ETF codes start with 51/52/15/16/56/58 and end with .SH/.SZ
            def _infer_market(code):
                if not isinstance(code, str):
                    return "a_stock"
                prefix = code[:3] if len(code) >= 3 else ""
                if prefix in (
                    "510",
                    "511",
                    "512",
                    "513",
                    "515",
                    "516",
                    "518",
                    "520",
                    "560",
                    "561",
                    "562",
                    "563",
                    "588",
                    "159",
                    "150",
                    "501",
                    "502",
                ):
                    return "etf"
                return "a_stock"

            df["market_type"] = df["ts_code"].apply(_infer_market)
        else:
            df["market_type"] = market.value

        return df

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_list(lst: list[str], size: int) -> list[list[str]]:
        """Split a list into chunks of given size."""
        return [lst[i : i + size] for i in range(0, len(lst), size)]

    # ------------------------------------------------------------------
    # Async collection for A-stock + ETF (merged, batch API)
    # ------------------------------------------------------------------

    async def _collect_a_etf(self, freq: str = "1MIN") -> pd.DataFrame:
        """Collect A-stock + ETF minute data using asyncio coroutines.

        Merges A-stock and ETF codes into one list, splits into batches
        of 300, and fires up to 50 concurrent requests.
        """
        codes = cfg.get_all_a_etf_codes()
        if not codes:
            return pd.DataFrame()

        batches = self._chunk_list(codes, cfg.BATCH_SIZE)
        logger.info(
            "Collecting A+ETF minute data: %d codes → %d batches, concurrency=%d",
            len(codes),
            len(batches),
            cfg.CONCURRENT_WORKERS,
        )

        # Semaphore to limit concurrency
        semaphore = asyncio.Semaphore(cfg.CONCURRENT_WORKERS)

        async def _fetch_batch(batch: list[str], batch_idx: int) -> pd.DataFrame:
            """Async wrapper: run sync API call in thread pool."""
            async with semaphore:
                try:
                    df = await asyncio.to_thread(self._call_rt_min_batch, batch, freq)
                    return df
                except Exception as e:
                    logger.warning(
                        "Batch %d (%d codes, first=%s) failed: %s",
                        batch_idx,
                        len(batch),
                        batch[0] if batch else "?",
                        e,
                    )
                    # Fallback: try one by one
                    dfs = []
                    for code in batch:
                        try:
                            df = await asyncio.to_thread(
                                self._call_rt_min_single, code, freq
                            )
                            if not df.empty:
                                dfs.append(df)
                        except Exception:
                            pass
                    if dfs:
                        return pd.concat(dfs, ignore_index=True)
                    return pd.DataFrame()

        # Fire all tasks concurrently
        tasks = [_fetch_batch(b, i) for i, b in enumerate(batches)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_dfs = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Batch %d raised exception: %s", i, result)
                continue
            if result is not None and not result.empty:
                df = self._normalize(result, MarketType.A_STOCK, freq)
                all_dfs.append(df)

        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Async collection for Index (one-by-one API)
    # ------------------------------------------------------------------

    async def _collect_index(self, freq: str = "1MIN") -> pd.DataFrame:
        """Collect index minute data using asyncio coroutines."""
        codes = cfg.INDEX_CODES
        if not codes:
            return pd.DataFrame()

        semaphore = asyncio.Semaphore(cfg.CONCURRENT_WORKERS)

        async def _fetch_one(code: str) -> pd.DataFrame:
            async with semaphore:
                try:
                    df = await asyncio.to_thread(self._call_rt_idx_min, code, freq)
                    return df
                except Exception as e:
                    logger.warning("Index collect failed for %s: %s", code, e)
                    return pd.DataFrame()

        tasks = [_fetch_one(code) for code in codes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_dfs = []
        for result in results:
            if isinstance(result, Exception):
                continue
            if result is not None and not result.empty:
                df = self._normalize(result, MarketType.INDEX, freq)
                all_dfs.append(df)

        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Sync wrappers (for non-async callers like scheduler)
    # ------------------------------------------------------------------

    def _run_async(self, coro):
        """Run an async coroutine, compatible with both sync and async contexts."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an existing event loop (e.g. FastAPI/uvicorn)
            # Use a new thread to run the coroutine with its own loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            # No running loop, safe to use asyncio.run
            return asyncio.run(coro)

    def collect_a_etf(self, freq: str = "1MIN") -> pd.DataFrame:
        """Sync wrapper: collect A-stock + ETF minute data."""
        return self._run_async(self._collect_a_etf(freq))

    def collect_index(self, freq: str = "1MIN") -> pd.DataFrame:
        """Sync wrapper: collect index minute data."""
        return self._run_async(self._collect_index(freq))

    # ------------------------------------------------------------------
    # Unified entry point
    # ------------------------------------------------------------------

    def collect_all(
        self,
        freq: str = "1MIN",
        markets: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Collect all configured markets.

        Args:
            freq: Bar frequency.
            markets: List of market names to collect.
                     Defaults to ["a_etf", "index"].
                     Supported: "a_etf", "a_stock", "etf", "index"
                     Note: "a_stock" and "etf" are merged into "a_etf".

        Returns:
            Dict mapping market name to its DataFrame.
        """
        if markets is None:
            markets = ["a_etf", "index"]

        # Merge a_stock + etf into a_etf
        effective_markets = set()
        for m in markets:
            if m in ("a_stock", "etf"):
                effective_markets.add("a_etf")
            else:
                effective_markets.add(m)
        effective_markets = list(effective_markets)

        results: dict[str, pd.DataFrame] = {}
        collectors = {
            "a_etf": self.collect_a_etf,
            "index": self.collect_index,
        }

        for market in effective_markets:
            fn = collectors.get(market)
            if fn is None:
                logger.warning("Unknown or unsupported market: %s", market)
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

_collector: RealtimeMinuteCollector | None = None


def get_collector() -> RealtimeMinuteCollector:
    """Get collector singleton."""
    global _collector
    if _collector is None:
        _collector = RealtimeMinuteCollector()
    return _collector
