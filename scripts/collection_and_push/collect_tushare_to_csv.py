#!/usr/bin/env python3
"""Standalone TuShare realtime collector -> CSV.

特点：
1) 不依赖 Redis / ClickHouse
2) 采集逻辑内置（a_stock / etf / index / hk）
3) 支持 HTTP 接口地址与代理设置（可通过参数覆盖）
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import tushare as ts


logger = logging.getLogger("collect_tushare_to_csv")


CN_TRADING_HOURS: List[tuple[str, str]] = [
    ("09:25", "11:35"),
    ("12:55", "15:05"),
]
HK_TRADING_HOURS: List[tuple[str, str]] = [
    ("09:15", "12:05"),
    ("12:55", "16:15"),
]


MARKET_QUERIES: Dict[str, List[Dict[str, str]]] = {
    "a_stock": [
        {"api": "rt_k", "ts_code": "6*.SH,68*.SH,*.BJ"},
        {"api": "rt_k", "ts_code": "0*.SZ,3*.SZ"},
    ],
    "etf": [
        {"api": "rt_etf_k", "ts_code": "1*.SZ"},
        {"api": "rt_etf_k", "ts_code": "5*.SH", "topic": "HQ_FND_TICK"},
    ],
    "index": [
        {"api": "rt_idx_k", "ts_code": "0*.SH,399*.SZ", "fields": "ts_code,name,trade_time,close,vol,pct_chg"},
    ],
    "hk": [
        {"api": "rt_hk_k", "ts_code": "*.HK"},
    ],
}


@dataclass
class CollectConfig:
    token: str
    api_url: str | None
    proxy_url: str | None
    rate_limit: int
    timeout: int
    max_retries: int
    retry_min_seconds: float
    retry_max_seconds: float
    market_inner_concurrency: int


class RateLimiter:
    def __init__(self, rate_limit_per_minute: int):
        safe_limit = max(1, min(rate_limit_per_minute, 50))
        self._min_interval = 60.0 / safe_limit
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call = time.time()


class TuShareRealtimeCollector:
    def __init__(self, cfg: CollectConfig):
        self.cfg = cfg
        self._api_limiters: Dict[str, RateLimiter] = {}
        self._api_limiters_lock = threading.Lock()

        self._configure_http(proxy_url=cfg.proxy_url, api_url=cfg.api_url)
        ts.set_token(cfg.token)
        try:
            self.pro = ts.pro_api(timeout=cfg.timeout)
        except TypeError:
            self.pro = ts.pro_api()

    @staticmethod
    def _configure_http(proxy_url: str | None, api_url: str | None) -> None:
        if proxy_url:
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            logger.info("Proxy enabled")

        try:
            import tushare.pro.client as tushare_client

            if hasattr(tushare_client, "DataApi"):
                current_url = getattr(tushare_client.DataApi, "_DataApi__http_url", None)
                if api_url:
                    target = api_url.strip().rstrip("/")
                    if not target.startswith("http://") and not target.startswith("https://"):
                        target = f"https://{target}"
                    tushare_client.DataApi._DataApi__http_url = target
                    logger.info("TuShare DataApi URL overridden: %s", target)
                elif current_url and current_url.startswith("http://"):
                    patched = current_url.replace("http://", "https://", 1)
                    tushare_client.DataApi._DataApi__http_url = patched
                    logger.info("TuShare DataApi URL patched to HTTPS: %s", patched)
        except Exception as e:
            logger.warning("Failed to configure TuShare API URL: %s", e)

    def _get_api_limiter(self, api_name: str) -> RateLimiter:
        with self._api_limiters_lock:
            limiter = self._api_limiters.get(api_name)
            if limiter is None:
                limiter = RateLimiter(self.cfg.rate_limit)
                self._api_limiters[api_name] = limiter
            return limiter

    def _call_api(self, api_name: str, **params) -> pd.DataFrame:
        last_error: Exception | None = None

        for attempt in range(1, self.cfg.max_retries + 1):
            self._get_api_limiter(api_name).wait()
            try:
                fn = getattr(self.pro, api_name)
                df = fn(**params)
                if df is None or df.empty:
                    return pd.DataFrame()
                return df
            except Exception as e:
                last_error = e
                if attempt >= self.cfg.max_retries:
                    break
                backoff = min(self.cfg.retry_max_seconds, max(self.cfg.retry_min_seconds, 2 ** (attempt - 1)))
                logger.warning(
                    "API failed api=%s params=%s attempt=%s/%s err=%s, retry in %.1fs",
                    api_name,
                    params,
                    attempt,
                    self.cfg.max_retries,
                    e,
                    backoff,
                )
                time.sleep(backoff)

        raise RuntimeError(f"API call failed api={api_name} params={params}: {last_error}")

    def _normalize(self, market: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        if df.empty:
            return []

        x = df.copy()

        if "trade_time" in x.columns:
            x["trade_time"] = pd.to_datetime(x["trade_time"], errors="coerce")
            x["trade_date"] = x["trade_time"].apply(
                lambda v: v.strftime("%Y%m%d") if pd.notna(v) else datetime.now().strftime("%Y%m%d")
            )
            x["trade_time"] = x["trade_time"].apply(
                lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(v) else None
            )
        else:
            x["trade_time"] = None
            x["trade_date"] = datetime.now().strftime("%Y%m%d")

        for col in [
            "ts_code", "name", "open", "close", "high", "low", "pre_close", "vol", "amount", "pct_chg", "bid", "ask",
        ]:
            if col not in x.columns:
                x[col] = None

        if ("bid" not in x.columns or x["bid"].isna().all()) and "bid_price1" in x.columns:
            x["bid"] = x["bid_price1"]
        if ("ask" not in x.columns or x["ask"].isna().all()) and "ask_price1" in x.columns:
            x["ask"] = x["ask_price1"]

        if market in ("index", "hk"):
            x["amount"] = None

        mask = x["pct_chg"].isna() & x["pre_close"].notna() & x["close"].notna()
        if mask.any():
            x.loc[mask, "pct_chg"] = ((x.loc[mask, "close"] - x.loc[mask, "pre_close"]) / x.loc[mask, "pre_close"] * 100).round(2)

        for col in ("open", "close", "high", "low", "pre_close", "vol", "amount", "pct_chg", "bid", "ask"):
            x[col] = pd.to_numeric(x[col], errors="coerce")

        now = datetime.now()
        collected_at = now.strftime("%Y-%m-%d %H:%M:%S")
        version = int(now.timestamp() * 1000)

        rows: List[Dict[str, Any]] = []
        for _, row in x.iterrows():
            rows.append(
                {
                    "ts_code": row.get("ts_code"),
                    "name": self._safe_value(row.get("name")),
                    "trade_date": row.get("trade_date"),
                    "trade_time": row.get("trade_time"),
                    "open": self._safe_value(row.get("open")),
                    "high": self._safe_value(row.get("high")),
                    "low": self._safe_value(row.get("low")),
                    "close": self._safe_value(row.get("close")),
                    "pre_close": self._safe_value(row.get("pre_close")),
                    "vol": self._safe_value(row.get("vol")),
                    "amount": self._safe_value(row.get("amount")),
                    "pct_chg": self._safe_value(row.get("pct_chg")),
                    "bid": self._safe_value(row.get("bid")),
                    "ask": self._safe_value(row.get("ask")),
                    "market": market,
                    "collected_at": collected_at,
                    "version": version,
                }
            )
        return rows

    @staticmethod
    def _safe_value(v: Any) -> Any:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    def collect_market(self, market: str) -> List[Dict[str, Any]]:
        if market not in MARKET_QUERIES:
            return []

        queries = MARKET_QUERIES[market]
        if not queries:
            return []

        max_workers = min(len(queries), max(1, self.cfg.market_inner_concurrency))
        dfs: List[pd.DataFrame] = []

        def _run_query(query: Dict[str, str]) -> pd.DataFrame:
            query_copy = dict(query)
            api_name = query_copy.pop("api")
            return self._call_api(api_name, **query_copy)

        if max_workers <= 1:
            for query in queries:
                try:
                    df = _run_query(query)
                    if not df.empty:
                        dfs.append(df)
                except Exception as e:
                    logger.warning("collect market=%s query=%s failed: %s", market, query, e)
        else:
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"rt-{market}") as executor:
                futures = {executor.submit(_run_query, q): q for q in queries}
                for future in as_completed(futures):
                    query = futures[future]
                    try:
                        df = future.result()
                        if not df.empty:
                            dfs.append(df)
                    except Exception as e:
                        logger.warning("collect market=%s query=%s failed: %s", market, query, e)

        if not dfs:
            return []

        merged = pd.concat(dfs, ignore_index=True)
        return self._normalize(market, merged)


def parse_markets(raw: str) -> List[str]:
    markets = [m.strip() for m in raw.split(",") if m.strip()]
    valid = set(MARKET_QUERIES.keys())
    invalid = [m for m in markets if m not in valid]
    if invalid:
        raise ValueError(f"invalid markets={invalid}, valid={sorted(valid)}")
    return markets


def in_time_windows(windows: List[tuple[str, str]]) -> bool:
    now_hm = datetime.now().strftime("%H:%M")
    return any(start <= now_hm <= end for start, end in windows)


def should_collect_market(market: str, ignore_trading_window: bool) -> bool:
    if ignore_trading_window:
        return True
    if market in ("a_stock", "etf", "index"):
        return in_time_windows(CN_TRADING_HOURS)
    if market == "hk":
        return in_time_windows(HK_TRADING_HOURS)
    return False


def write_csv(output_dir: Path, data: Dict[str, List[Dict[str, Any]]], timestamp: str, append: bool) -> Dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stats: Dict[str, int] = {}

    for market, rows in data.items():
        count = len(rows)
        stats[market] = count
        if count <= 0:
            continue

        df = pd.DataFrame(rows)
        if append:
            out_file = output_dir / f"{market}.csv"
            write_header = not out_file.exists()
            df.to_csv(out_file, mode="a", header=write_header, index=False, encoding="utf-8-sig")
        else:
            out_file = output_dir / f"{market}_{timestamp}.csv"
            df.to_csv(out_file, index=False, encoding="utf-8-sig")

    return stats


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone TuShare realtime collector to CSV")
    parser.add_argument("--token", default=os.getenv("TUSHARE_TOKEN", ""), help="TuShare token")
    parser.add_argument("--api-url", default=os.getenv("TUSHARE_API_URL", ""), help="TuShare DataApi URL (e.g. https://api.tushare.pro)")
    parser.add_argument("--proxy-url", default=os.getenv("HTTP_PROXY", ""), help="HTTP/HTTPS proxy URL")

    parser.add_argument("--markets", default="a_stock,etf,index,hk", help="Comma-separated markets")
    parser.add_argument("--output-dir", default="data/tushare_csv", help="CSV output directory")
    parser.add_argument("--append", action="store_true", help="Append into <market>.csv")

    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=float, default=1.5, help="Loop interval seconds")
    parser.add_argument("--rounds", type=int, default=0, help="Max rounds in loop mode, 0 means unlimited")

    parser.add_argument(
        "--trading-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Collect only in market trading windows",
    )
    parser.add_argument("--ignore-trading-window", action="store_true", help="Force collect even outside trading windows")
    parser.add_argument("--idle-sleep", type=float, default=30.0, help="Sleep seconds outside trading windows")

    parser.add_argument("--rate-limit", type=int, default=50, help="Max API calls per minute per API (safe<=50)")
    parser.add_argument("--timeout", type=int, default=15, help="TuShare client timeout seconds")
    parser.add_argument("--max-retries", type=int, default=3, help="Retries per API call")
    parser.add_argument("--retry-min-seconds", type=float, default=2.0, help="Min retry backoff")
    parser.add_argument("--retry-max-seconds", type=float, default=10.0, help="Max retry backoff")

    parser.add_argument("--market-inner-concurrency", type=int, default=3, help="Parallel queries per market")

    parser.add_argument("--log-level", default="INFO", help="DEBUG/INFO/WARNING/ERROR")
    return parser.parse_args()


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if not args.token:
        print("[ERROR] missing token. set --token or env TUSHARE_TOKEN")
        return 1

    try:
        markets = parse_markets(args.markets)
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    cfg = CollectConfig(
        token=args.token,
        api_url=args.api_url.strip() or None,
        proxy_url=args.proxy_url.strip() or None,
        rate_limit=args.rate_limit,
        timeout=args.timeout,
        max_retries=max(1, int(args.max_retries)),
        retry_min_seconds=max(0.1, float(args.retry_min_seconds)),
        retry_max_seconds=max(float(args.retry_min_seconds), float(args.retry_max_seconds)),
        market_inner_concurrency=max(1, int(args.market_inner_concurrency)),
    )

    collector = TuShareRealtimeCollector(cfg)
    output_dir = Path(args.output_dir)

    round_no = 0
    while True:
        round_no += 1
        t0 = time.monotonic()
        ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")

        active_markets: List[str] = []
        if args.ignore_trading_window or not args.trading_only:
            active_markets = markets
        else:
            active_markets = [m for m in markets if should_collect_market(m, ignore_trading_window=False)]
            if not active_markets:
                logger.info("round=%s outside trading window, sleep %.1fs", round_no, args.idle_sleep)
                if not args.loop:
                    break
                time.sleep(args.idle_sleep)
                continue

        batch: Dict[str, List[Dict[str, Any]]] = {}
        for market in active_markets:
            try:
                rows = collector.collect_market(market)
                batch[market] = rows
            except Exception as e:
                logger.error("round=%s market=%s failed: %s", round_no, market, e)
                batch[market] = []

        stats = write_csv(output_dir=output_dir, data=batch, timestamp=ts_tag, append=args.append)
        total = sum(stats.values())
        logger.info("round=%s total=%s details=%s output=%s", round_no, total, stats, output_dir)

        if not args.loop:
            break
        if args.rounds > 0 and round_no >= args.rounds:
            break

        elapsed = time.monotonic() - t0
        wait_s = max(0.0, float(args.interval) - elapsed)
        if wait_s > 0:
            time.sleep(wait_s)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
