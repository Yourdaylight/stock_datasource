#!/usr/bin/env python3
"""Standalone TuShare realtime collector -> CSV.

特点：
1) 不依赖 Redis / ClickHouse
2) 采集逻辑内置（a_stock / etf / index / hk）
3) 支持 HTTP 接口地址与代理设置（可通过参数覆盖）
4) 市场间并行采集，港股分片轮转，normalize 向量化
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
    # 港股：一次查询覆盖全部号段（总计 ~3400 只，远低于 6000 限制）
    "hk": [
        {"api": "rt_hk_k", "ts_code": "00*.HK,01*.HK,02*.HK,03*.HK,04*.HK,06*.HK,08*.HK,09*.HK,11*.HK"},
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

    def _normalize(self, market: str, df: pd.DataFrame) -> pd.DataFrame:
        """向量化标准化，返回 DataFrame 而非 list[dict]，减少内存拷贝和循环开销。

        注意：直接在 df 上原地操作（不再 copy），因为调用方 collect_market()
        中的 merged = pd.concat(dfs, ignore_index=True) 已经创建了新 DataFrame。
        """
        if df.empty:
            return pd.DataFrame()

        # --- trade_time / trade_date ---
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
            df["trade_date"] = df["trade_time"].dt.strftime("%Y%m%d").fillna(datetime.now().strftime("%Y%m%d"))
            df["trade_time"] = df["trade_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            df["trade_time"] = None
            df["trade_date"] = datetime.now().strftime("%Y%m%d")

        # --- 补齐缺失列 ---
        for col in ("ts_code", "name", "open", "close", "high", "low", "pre_close",
                     "vol", "amount", "num", "pct_chg",
                     "bid", "ask", "bid_volume1", "ask_volume1"):
            if col not in df.columns:
                df[col] = None

        # --- bid/ask 回退 ---
        if df["bid"].isna().all() and "bid_price1" in df.columns:
            df["bid"] = df["bid_price1"]
        if df["ask"].isna().all() and "ask_price1" in df.columns:
            df["ask"] = df["ask_price1"]

        # --- 指数/港股无成交额 ---
        if market in ("index", "hk"):
            df["amount"] = None

        # --- 补算涨跌幅（向量化） ---
        mask = df["pct_chg"].isna() & df["pre_close"].notna() & df["close"].notna()
        if mask.any():
            df.loc[mask, "pct_chg"] = ((df.loc[mask, "close"].astype(float) - df.loc[mask, "pre_close"].astype(float)) / df.loc[mask, "pre_close"].astype(float) * 100).round(2)

        # --- 数值类型统一转换（用 astype 替代 apply 循环，CPU 更低） ---
        num_cols = ["open", "close", "high", "low", "pre_close", "vol", "amount", "pct_chg", "bid", "ask"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # --- 元数据列 ---
        now = datetime.now()
        df["market"] = market
        df["collected_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
        df["version"] = int(now.timestamp() * 1000)

        # --- 只保留目标列（避免传输多余字段） ---
        target_cols = [
            "ts_code", "name", "trade_date", "trade_time",
            "open", "high", "low", "close", "pre_close",
            "vol", "amount", "num", "pct_chg",
            "bid", "ask", "bid_volume1", "ask_volume1",
            "market", "collected_at", "version",
        ]
        # NaN → None for JSON-safe output
        result = df[target_cols].where(df[target_cols].notna(), None)
        return result

    def collect_market(self, market: str) -> pd.DataFrame:
        """采集单个市场，返回标准化后的 DataFrame"""
        if market not in MARKET_QUERIES:
            return pd.DataFrame()

        queries = MARKET_QUERIES[market]

        if not queries:
            return pd.DataFrame()

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
            return pd.DataFrame()

        merged = pd.concat(dfs, ignore_index=True)
        return self._normalize(market, merged)

    def collect_markets_parallel(self, markets: List[str]) -> Dict[str, pd.DataFrame]:
        """多市场并行采集：不同 API 互不限频，充分利用网络 IO。
        
        CPU 优化（v4）：并发数限制为 2，在 2 核机器上避免 CPU 打满。
        """
        results: Dict[str, pd.DataFrame] = {}

        if len(markets) <= 1:
            for m in markets:
                try:
                    results[m] = self.collect_market(m)
                except Exception as e:
                    logger.error("market=%s failed: %s", m, e)
                    results[m] = pd.DataFrame()
            return results

        # 限制并发数为 2（2核机器保护）
        max_workers = min(2, len(markets))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mkt") as executor:
            future_map = {executor.submit(self.collect_market, m): m for m in markets}
            for future in as_completed(future_map):
                market = future_map[future]
                try:
                    results[market] = future.result()
                except Exception as e:
                    logger.error("market=%s failed: %s", market, e)
                    results[market] = pd.DataFrame()

        return results


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


def _trim_state_file(output_dir: Path) -> Path:
    return output_dir.parent / "csv_trim_state.json"


def _load_trim_state(state_file: Path) -> Dict[str, int]:
    if not state_file.exists():
        return {}
    try:
        import json
        data = json.loads(state_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        return {str(k): int(v) for k, v in data.items()}
    except Exception as e:
        logger.warning("Failed to load trim state %s: %s", state_file, e)
        return {}


def _save_trim_state(state_file: Path, state: Dict[str, int]) -> None:
    import json

    state_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_file.with_suffix(state_file.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, state_file)


def _record_trimmed_rows(output_dir: Path, csv_file: Path, dropped_rows: int) -> None:
    if dropped_rows <= 0:
        return
    state_file = _trim_state_file(output_dir)
    state = _load_trim_state(state_file)
    key = csv_file.name
    state[key] = int(state.get(key, 0)) + int(dropped_rows)
    _save_trim_state(state_file, state)


def _truncate_csv_tail(csv_file: Path, max_keep_rows: int) -> tuple[int, int]:
    from collections import deque

    with open(csv_file, "r", encoding="utf-8-sig") as f:
        header = f.readline()
        tail_lines = deque(maxlen=max_keep_rows)
        total_rows = 0
        for line in f:
            total_rows += 1
            tail_lines.append(line)

    dropped_rows = max(0, total_rows - max_keep_rows)
    if dropped_rows <= 0:
        return (0, total_rows)

    tmp_file = csv_file.with_suffix(csv_file.suffix + ".tmp")
    with open(tmp_file, "w", encoding="utf-8-sig") as f:
        f.write(header)
        f.writelines(tail_lines)
    os.replace(tmp_file, csv_file)
    return (dropped_rows, len(tail_lines))


def write_csv(output_dir: Path, data: Dict[str, pd.DataFrame], timestamp: str, append: bool,
              max_keep_rows: int = 100000) -> Dict[str, int]:
    """将各市场 DataFrame 写入 CSV，返回条数统计。

    max_keep_rows:
    - 0: 无限追加（不建议，文件会持续膨胀）
    - >0: 追加后只保留最新 N 行，同时维护 trim state，
          让推送进程能够在截断后继续按逻辑 offset 增量推送。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    stats: Dict[str, int] = {}

    for market, df in data.items():
        count = len(df)
        stats[market] = count
        if count <= 0:
            continue

        if append:
            out_file = output_dir / f"{market}.csv"
            write_header = not out_file.exists()
            df.to_csv(out_file, mode="a", header=write_header, index=False, encoding="utf-8-sig")

            if max_keep_rows > 0 and out_file.exists():
                try:
                    dropped_rows, kept_rows = _truncate_csv_tail(out_file, max_keep_rows)
                    if dropped_rows > 0:
                        _record_trimmed_rows(output_dir, out_file, dropped_rows)
                        logger.info(
                            "CSV truncated: %s dropped=%d kept=%d",
                            out_file.name, dropped_rows, kept_rows,
                        )
                except Exception as e:
                    logger.warning("CSV truncate failed for %s: %s", out_file.name, e)
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
    parser.add_argument("--max-keep-rows", type=int, default=100000,
                        help="Max rows to keep per CSV in append mode (default 100000, 0=unlimited). "
                             "超过上限后会滚动截断，并维护 trim state 以保持推送断点连续。")

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


def clear_csv_and_checkpoints(output_dir: Path, markets: List[str],
                               checkpoint_glob: str = "push_ckpt_*.json") -> None:
    """休市时清空 CSV、推送 checkpoint 和 trim state。"""
    for market in markets:
        csv_file = output_dir / f"{market}.csv"
        if csv_file.exists() and csv_file.stat().st_size > 0:
            try:
                with open(csv_file, "r", encoding="utf-8-sig") as f:
                    header = f.readline()
                with open(csv_file, "w", encoding="utf-8-sig") as f:
                    f.write(header)
                logger.info("CSV cleared (header kept): %s", csv_file.name)
            except Exception as e:
                logger.warning("Failed to clear CSV %s: %s", csv_file.name, e)

    search_dirs = [output_dir, output_dir.parent]
    for search_dir in search_dirs:
        for ckpt_file in search_dir.glob(checkpoint_glob):
            try:
                ckpt_file.write_text("{}", encoding="utf-8")
                logger.info("Checkpoint cleared: %s", ckpt_file)
            except Exception as e:
                logger.warning("Failed to clear checkpoint %s: %s", ckpt_file, e)

    trim_state_file = _trim_state_file(output_dir)
    try:
        _save_trim_state(trim_state_file, {})
        logger.info("Trim state cleared: %s", trim_state_file)
    except Exception as e:
        logger.warning("Failed to clear trim state %s: %s", trim_state_file, e)


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
    _was_idle = False  # 上一轮是否处于休市状态（用于检测 "交易中→休市" 的切换点）
    _csv_cleared_today = False  # 今天是否已经清空过 CSV（避免重复清空）
    _last_clear_date = ""  # 上次清空的日期，每天重置
    while True:
        round_no += 1
        t0 = time.monotonic()
        ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        today_str = datetime.now().strftime("%Y%m%d")

        # 每天重置清空标记
        if today_str != _last_clear_date:
            _csv_cleared_today = False

        active_markets: List[str] = []
        if args.ignore_trading_window or not args.trading_only:
            active_markets = markets
        else:
            active_markets = [m for m in markets if should_collect_market(m, ignore_trading_window=False)]
            if not active_markets:
                # --- 休市清理逻辑 ---
                # 条件：之前在交易中（_was_idle=False），现在所有市场都休市了
                # 或者：今天还没清空过（防止进程重启后遗漏）
                if (not _csv_cleared_today) and _was_idle:
                    # 已经连续两轮休市了（确认不是瞬时波动），执行清空
                    logger.info(
                        "All markets closed. Clearing CSV files and checkpoints "
                        "(data already pushed to subscriber nodes)."
                    )
                    clear_csv_and_checkpoints(output_dir, markets)
                    _csv_cleared_today = True
                    _last_clear_date = today_str

                _was_idle = True
                logger.info("round=%s outside trading window, sleep %.1fs", round_no, args.idle_sleep)
                if not args.loop:
                    break
                time.sleep(args.idle_sleep)
                continue

        _was_idle = False  # 有活跃市场，标记为交易中

        # ---- 核心优化：市场间并行采集 ----
        batch = collector.collect_markets_parallel(active_markets)

        t_collect = time.monotonic() - t0

        stats = write_csv(output_dir=output_dir, data=batch, timestamp=ts_tag, append=args.append,
                          max_keep_rows=args.max_keep_rows)
        total = sum(stats.values())

        elapsed = time.monotonic() - t0
        logger.info(
            "round=%s total=%s details=%s collect=%.2fs total=%.2fs output=%s",
            round_no, total, stats, t_collect, elapsed, output_dir,
        )

        if not args.loop:
            break
        if args.rounds > 0 and round_no >= args.rounds:
            break

        wait_s = max(0.0, float(args.interval) - elapsed)
        if wait_s > 0:
            time.sleep(wait_s)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
