#!/usr/bin/env python3
"""Standalone CSV -> Cloud Push script.

特点：
1) 不依赖 Redis / ClickHouse / FastAPI
2) 从 collect_tushare_to_csv.py 产出的 CSV 目录中增量读取
3) 按 RawTickBatchPayload v2 协议推送到云端
4) 支持循环监控模式（--loop），持续监控 CSV 文件增量
5) 支持断点续传（记录每个文件已推送行数）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger("push_csv_to_cloud")

# ---------------------------------------------------------------------------
# 市场识别
# ---------------------------------------------------------------------------

# CSV 文件名 -> market 映射（和 collect_tushare_to_csv.py 的 write_csv 一致）
MARKET_FILE_PREFIXES = {
    "a_stock": "a_stock",
    "etf": "etf",
    "index": "index",
    "hk": "hk",
}

# market -> source_api 映射
MARKET_API_MAP = {
    "a_stock": "tushare_rt_k",
    "etf": "tushare_rt_etf_k",
    "index": "tushare_rt_idx_k",
    "hk": "tushare_rt_hk_k",
}

# ACK 状态码判断
_SUCCESS_ACK_STATUS = {"ok", "success", "accepted", ""}
_SUCCESS_ACK_CODES = {0, 200, 202}
_RETRYABLE_ACK_STATUS = {"retryable", "throttle", "busy", "timeout", "temporarily_unavailable"}
_RETRYABLE_ACK_CODES = {408, 409, 425, 429, 500, 502, 503, 504, 1001, 1002, 1003}
_RETRYABLE_HTTP_STATUS = {408, 425, 429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PushConfig:
    push_url: str
    push_token: str
    csv_dir: str
    markets: List[str]
    batch_size: int
    max_retry: int
    retry_backoff_base: float
    retry_backoff_max: float
    timeout: int
    shards: int
    checkpoint_file: str


# ---------------------------------------------------------------------------
# Checkpoint — 记录每个 CSV 文件已推送的行数偏移
# ---------------------------------------------------------------------------

class CheckpointStore:
    """JSON-file based checkpoint for tracking pushed row offsets per CSV file."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._data: Dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load checkpoint %s: %s, starting fresh", self._filepath, e)
                self._data = {}

    def _save(self) -> None:
        try:
            tmp = self._filepath + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._filepath)
        except OSError as e:
            logger.error("Failed to save checkpoint: %s", e)

    def get_offset(self, csv_file: str) -> int:
        return self._data.get(csv_file, 0)

    def set_offset(self, csv_file: str, offset: int) -> None:
        self._data[csv_file] = offset
        self._save()


# ---------------------------------------------------------------------------
# Cloud Pusher
# ---------------------------------------------------------------------------

class CSVCloudPusher:
    """Read CSV files incrementally and push to cloud endpoint."""

    def __init__(self, cfg: PushConfig):
        self.cfg = cfg
        self._session = requests.Session()
        self._checkpoint = CheckpointStore(cfg.checkpoint_file)
        self._batch_seq: Dict[str, int] = {}

    def tick(self) -> Dict[str, int]:
        """One round: scan CSV dir, read new rows, push batches. Returns {market: pushed_count}."""
        stats: Dict[str, int] = {}

        for market in self.cfg.markets:
            csv_files = self._find_csv_files(market)
            if not csv_files:
                stats[market] = 0
                continue

            total_pushed = 0
            for csv_file in csv_files:
                pushed = self._process_csv(market, csv_file)
                total_pushed += pushed

            stats[market] = total_pushed

        return stats

    def _find_csv_files(self, market: str) -> List[str]:
        """Find all CSV files for given market in csv_dir."""
        csv_dir = Path(self.cfg.csv_dir)
        if not csv_dir.exists():
            return []

        result = []
        prefix = MARKET_FILE_PREFIXES.get(market, market)

        for f in sorted(csv_dir.glob(f"{prefix}*.csv")):
            result.append(str(f))

        return result

    def _process_csv(self, market: str, csv_file: str) -> int:
        """Read new rows from csv_file and push. Returns count of pushed rows."""
        offset = self._checkpoint.get_offset(csv_file)

        try:
            df = pd.read_csv(csv_file, encoding="utf-8-sig")
        except Exception as e:
            logger.error("Failed to read CSV %s: %s", csv_file, e)
            return 0

        total_rows = len(df)
        if offset >= total_rows:
            return 0

        new_rows = df.iloc[offset:]
        pushed = 0

        for chunk_start in range(0, len(new_rows), self.cfg.batch_size):
            chunk_df = new_rows.iloc[chunk_start:chunk_start + self.cfg.batch_size]
            rows = self._df_to_rows(chunk_df, market)

            if not rows:
                continue

            payload = self._build_payload(market, rows)
            success = self._push_with_retry(market, payload)

            if success:
                advanced = offset + chunk_start + len(chunk_df)
                self._checkpoint.set_offset(csv_file, advanced)
                pushed += len(rows)
                logger.info(
                    "Pushed market=%s file=%s rows=%d offset=%d/%d",
                    market, Path(csv_file).name, len(rows), advanced, total_rows,
                )
            else:
                logger.error(
                    "Push failed, stopping market=%s file=%s at offset=%d",
                    market, Path(csv_file).name, offset + chunk_start,
                )
                break

        return pushed

    @staticmethod
    def _safe_value(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return v

    def _df_to_rows(self, df: pd.DataFrame, market: str) -> List[Dict[str, Any]]:
        """Convert DataFrame chunk to list of tick dicts."""
        rows: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            tick: Dict[str, Any] = {}
            for col in df.columns:
                tick[col] = self._safe_value(row.get(col))

            # Ensure market field
            if "market" not in tick or tick["market"] is None:
                tick["market"] = market

            rows.append(tick)
        return rows

    def _build_payload(self, market: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build RawTickBatchPayload v2 dict from rows."""
        self._batch_seq.setdefault(market, 0)
        self._batch_seq[market] += 1
        seq = self._batch_seq[market]

        now = datetime.now(timezone.utc)
        event_time = now.isoformat()

        # Generate pseudo stream_id from timestamp + index
        base_ms = int(now.timestamp() * 1000)
        items: List[Dict[str, Any]] = []

        for i, tick in enumerate(rows):
            ts_code = tick.get("ts_code", "")
            shard_id = (hash(ts_code) % self.cfg.shards) if ts_code else 0
            stream_id = f"{base_ms}-{i}"

            # version: use tick's version if present, else generate
            version = tick.get("version")
            if version is None:
                version = str(base_ms)

            items.append({
                "stream_id": stream_id,
                "ts_code": ts_code,
                "version": str(version),
                "shard_id": shard_id,
                "tick": tick,
            })

        first_stream_id = items[0]["stream_id"] if items else f"{base_ms}-0"
        last_stream_id = items[-1]["stream_id"] if items else f"{base_ms}-0"

        return {
            "schema_version": "v2",
            "mode": "raw_tick_batch",
            "batch_seq": seq,
            "event_time": event_time,
            "market": market,
            "source_api": MARKET_API_MAP.get(market, ""),
            "count": len(items),
            "first_stream_id": first_stream_id,
            "last_stream_id": last_stream_id,
            "items": items,
        }

    def _push_with_retry(self, market: str, payload: Dict[str, Any]) -> bool:
        """Push payload with retry logic. Returns True on success."""
        url = self.cfg.push_url
        if not url:
            logger.warning("No push URL configured, skipping")
            return True

        headers = {"Content-Type": "application/json"}
        if self.cfg.push_token:
            headers["Authorization"] = f"Bearer {self.cfg.push_token}"

        for attempt in range(1, self.cfg.max_retry + 1):
            try:
                t0 = time.monotonic()
                resp = self._session.post(url, json=payload, headers=headers, timeout=self.cfg.timeout)
                latency_ms = (time.monotonic() - t0) * 1000

                if resp.status_code == 200:
                    result = self._check_ack(resp)
                    if result == "ok":
                        logger.debug(
                            "Push OK market=%s seq=%d count=%d latency=%.0fms",
                            market, payload.get("batch_seq", 0), payload.get("count", 0), latency_ms,
                        )
                        return True
                    if result == "failed":
                        logger.error(
                            "Push ACK non-retryable market=%s resp=%s",
                            market, resp.text[:200],
                        )
                        return False
                    # retryable: fall through to retry

                elif resp.status_code not in _RETRYABLE_HTTP_STATUS:
                    logger.error(
                        "Push HTTP non-retryable market=%s status=%d body=%s",
                        market, resp.status_code, resp.text[:200],
                    )
                    return False

                # retryable status
                logger.warning(
                    "Push retryable market=%s status=%d attempt=%d/%d",
                    market, resp.status_code, attempt, self.cfg.max_retry,
                )

            except requests.exceptions.Timeout:
                logger.warning("Push timeout market=%s attempt=%d/%d", market, attempt, self.cfg.max_retry)
            except requests.exceptions.ConnectionError as e:
                logger.warning("Push connection error market=%s attempt=%d/%d: %s", market, attempt, self.cfg.max_retry, e)
            except Exception as e:
                logger.error("Push unexpected error market=%s attempt=%d/%d: %s", market, attempt, self.cfg.max_retry, e)

            if attempt < self.cfg.max_retry:
                backoff = min(self.cfg.retry_backoff_max, self.cfg.retry_backoff_base * (2 ** (attempt - 1)))
                time.sleep(backoff)

        return False

    def _check_ack(self, resp: requests.Response) -> str:
        """Parse ACK response. Returns 'ok', 'retryable', or 'failed'."""
        if not resp.content:
            return "ok"

        try:
            ack = resp.json()
        except (json.JSONDecodeError, ValueError):
            logger.warning("Invalid ACK JSON: %s", resp.text[:200])
            return "retryable"

        status = str(ack.get("status", "")).strip().lower()
        code = int(ack.get("code", 0))

        if status in _SUCCESS_ACK_STATUS and code in _SUCCESS_ACK_CODES:
            return "ok"
        if status in _RETRYABLE_ACK_STATUS or code in _RETRYABLE_ACK_CODES:
            return "retryable"

        return "failed"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_markets(raw: str) -> List[str]:
    markets = [m.strip() for m in raw.split(",") if m.strip()]
    valid = set(MARKET_FILE_PREFIXES.keys())
    invalid = [m for m in markets if m not in valid]
    if invalid:
        raise ValueError(f"invalid markets={invalid}, valid={sorted(valid)}")
    return markets


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Push CSV realtime data to cloud endpoint (standalone, no Redis/ClickHouse)."
    )

    # 数据源
    parser.add_argument("--csv-dir", default=os.getenv("CSV_DIR", "data/tushare_csv"),
                        help="CSV 文件目录（collect_tushare_to_csv.py 的输出目录）")
    parser.add_argument("--markets", default="a_stock,etf,index,hk",
                        help="要推送的市场，逗号分隔")

    # 推送目标
    parser.add_argument("--push-url", default=os.getenv("RT_KLINE_CLOUD_PUSH_URL", ""),
                        help="云端推送 URL")
    parser.add_argument("--push-token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""),
                        help="推送鉴权 Token")

    # 批量/重试
    parser.add_argument("--batch-size", type=int, default=1000,
                        help="每批推送条数")
    parser.add_argument("--max-retry", type=int, default=3,
                        help="单批最大重试次数")
    parser.add_argument("--retry-backoff-base", type=float, default=1.0,
                        help="重试退避基数(秒)")
    parser.add_argument("--retry-backoff-max", type=float, default=10.0,
                        help="重试退避上限(秒)")
    parser.add_argument("--timeout", type=int, default=15,
                        help="HTTP 超时(秒)")
    parser.add_argument("--shards", type=int, default=4,
                        help="分片数（shard_id 标记）")

    # 循环模式
    parser.add_argument("--loop", action="store_true",
                        help="持续循环监控 CSV 目录增量推送")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="循环间隔(秒)")
    parser.add_argument("--rounds", type=int, default=0,
                        help="最大循环轮次，0 表示无限")

    # 断点
    parser.add_argument("--checkpoint-file", default="data/push_checkpoint.json",
                        help="断点记录文件路径")

    # 日志
    parser.add_argument("--log-level", default="INFO",
                        help="日志级别: DEBUG/INFO/WARNING/ERROR")

    return parser.parse_args()


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if not args.push_url:
        print("[ERROR] missing --push-url or env RT_KLINE_CLOUD_PUSH_URL")
        return 1

    try:
        markets = parse_markets(args.markets)
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1

    csv_dir = Path(args.csv_dir)
    if not csv_dir.exists():
        print(f"[ERROR] CSV directory does not exist: {csv_dir}")
        return 1

    # 确保 checkpoint 文件目录存在
    ckpt_path = Path(args.checkpoint_file)
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)

    cfg = PushConfig(
        push_url=args.push_url.strip(),
        push_token=args.push_token.strip(),
        csv_dir=str(csv_dir),
        markets=markets,
        batch_size=max(1, args.batch_size),
        max_retry=max(1, args.max_retry),
        retry_backoff_base=max(0.1, args.retry_backoff_base),
        retry_backoff_max=max(args.retry_backoff_base, args.retry_backoff_max),
        timeout=max(1, args.timeout),
        shards=max(1, args.shards),
        checkpoint_file=str(ckpt_path),
    )

    pusher = CSVCloudPusher(cfg)

    round_no = 0
    while True:
        round_no += 1
        t0 = time.monotonic()

        stats = pusher.tick()
        total = sum(stats.values())

        if total > 0:
            logger.info("round=%d pushed=%d details=%s", round_no, total, stats)
        else:
            logger.debug("round=%d no new data", round_no)

        if not args.loop:
            break
        if args.rounds > 0 and round_no >= args.rounds:
            break

        elapsed = time.monotonic() - t0
        wait_s = max(0.0, args.interval - elapsed)
        if wait_s > 0:
            time.sleep(wait_s)

    logger.info("Done. Total rounds=%d", round_no)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
