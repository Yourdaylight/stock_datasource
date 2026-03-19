#!/usr/bin/env python3
"""Standalone CSV -> Cloud Push script.

特点：
1) 不依赖 Redis / ClickHouse / FastAPI
2) 从 collect_tushare_to_csv.py 产出的 CSV 目录中增量读取
3) 按 RawTickBatchPayload v2 协议推送到云端
4) 支持循环监控模式（--loop），持续监控 CSV 文件增量
5) 支持断点续传（记录每个文件已推送行数）
6) 市场间并行推送，DataFrame 向量化转换
7) 支持多目标推送：一份数据序列化一次，并行推送到多个节点（省进程+CPU）

性能优化（v2 → v3）：
- chunksize 流式迭代器：一次打开 CSV 顺序读取，消灭 skiprows O(N²) 回扫
- orjson 加速 JSON 序列化（fallback 到 stdlib json）
- 向量化 NaN 清洗 + numpy→python 批量转换，消灭逐字段 isinstance 循环
- 读/推流水线：读下一批的同时推当前批（可选 --pipeline）
- gzip 压缩（可选 --compress）：降低带宽占用 60%+
- 多目标推送：--push-url 支持逗号分隔多个 URL，一次序列化并行推送，省掉重复进程
- _df_to_items_vectorized 去掉 df.copy()，原地操作减少内存和 CPU
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

# 优先使用 orjson（C 实现，比 json 快 6-10x），否则回退到标准库
try:
    import orjson

    def _json_dumps(obj: Any) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS)

    _HAS_ORJSON = True
except ImportError:
    def _json_dumps(obj: Any) -> bytes:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    _HAS_ORJSON = False


logger = logging.getLogger("push_csv_to_cloud")

# ---------------------------------------------------------------------------
# 市场识别
# ---------------------------------------------------------------------------

MARKET_FILE_PREFIXES = {
    "a_stock": "a_stock",
    "etf": "etf",
    "index": "index",
    "hk": "hk",
}

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
    push_urls: List[str]      # 支持多目标 URL（逗号分隔输入，合并推送）
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
    pipeline: bool            # 读/推流水线
    compress: bool            # gzip 压缩


# ---------------------------------------------------------------------------
# Checkpoint — 记录每个 CSV 文件已推送的行数偏移
# ---------------------------------------------------------------------------

class CheckpointStore:
    """JSON-file based checkpoint for tracking pushed row offsets per CSV file.

    优化：延迟写入，flush() 时才落盘，减少高频 IO。
    """

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._data: Dict[str, int] = {}
        self._dirty = False
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load checkpoint %s: %s, starting fresh", self._filepath, e)
                self._data = {}

    def flush(self) -> None:
        """将脏数据落盘"""
        with self._lock:
            if not self._dirty:
                return
            try:
                tmp = self._filepath + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2)
                os.replace(tmp, self._filepath)
                self._dirty = False
            except OSError as e:
                logger.error("Failed to save checkpoint: %s", e)

    def get_offset(self, csv_file: str) -> int:
        with self._lock:
            return self._data.get(csv_file, 0)

    def set_offset(self, csv_file: str, offset: int) -> None:
        with self._lock:
            self._data[csv_file] = offset
            self._dirty = True


# ---------------------------------------------------------------------------
# Cloud Pusher
# ---------------------------------------------------------------------------

class CSVCloudPusher:
    """Read CSV files incrementally and push to cloud endpoint(s)."""

    def __init__(self, cfg: PushConfig):
        self.cfg = cfg
        self._session = requests.Session()
        # 连接池优化：增大池大小 + 启用 keep-alive
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=max(4, len(cfg.push_urls) * 2),
            pool_maxsize=max(8, len(cfg.push_urls) * 4),
            max_retries=0,  # 我们自己控制重试
        )
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
        self._checkpoint = CheckpointStore(cfg.checkpoint_file)
        self._batch_seq: Dict[str, int] = {}
        self._batch_seq_lock = threading.Lock()
        # 多目标并行推送线程池（复用于所有推送）
        self._multi_push_pool = ThreadPoolExecutor(
            max_workers=max(2, len(cfg.push_urls)),
            thread_name_prefix="multi-push",
        )
        # 流水线用的线程池（读一批+推一批并行）
        if cfg.pipeline:
            self._pipe_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pipe")
        else:
            self._pipe_pool = None

    def tick(self) -> Dict[str, int]:
        """One round: scan CSV dir, read new rows, push batches in parallel.
        Returns {market: pushed_count}.
        """
        markets = self.cfg.markets

        if len(markets) <= 1:
            stats: Dict[str, int] = {}
            for m in markets:
                stats[m] = self._tick_market(m)
            self._checkpoint.flush()
            return stats

        # 多市场并行推送
        stats: Dict[str, int] = {}
        with ThreadPoolExecutor(max_workers=len(markets), thread_name_prefix="push") as executor:
            future_map = {executor.submit(self._tick_market, m): m for m in markets}
            for future in as_completed(future_map):
                market = future_map[future]
                try:
                    stats[market] = future.result()
                except Exception as e:
                    logger.error("push market=%s failed: %s", market, e)
                    stats[market] = 0

        self._checkpoint.flush()
        return stats

    def _tick_market(self, market: str) -> int:
        """Push all new data for a single market. Returns total pushed count."""
        csv_files = self._find_csv_files(market)
        if not csv_files:
            return 0

        total_pushed = 0
        for csv_file in csv_files:
            pushed = self._process_csv(market, csv_file)
            total_pushed += pushed
        return total_pushed

    def _find_csv_files(self, market: str) -> List[str]:
        """Find all CSV files for given market in csv_dir."""
        csv_dir = Path(self.cfg.csv_dir)
        if not csv_dir.exists():
            return []

        prefix = MARKET_FILE_PREFIXES.get(market, market)
        return [str(f) for f in sorted(csv_dir.glob(f"{prefix}*.csv"))]

    def _process_csv(self, market: str, csv_file: str) -> int:
        """流式读取 CSV 并推送。

        核心优化：使用 pd.read_csv(chunksize=N) 返回迭代器，
        文件只打开一次、顺序读取，彻底消灭 skiprows 回扫。
        对于已推送的 offset，用迭代器 skip 跳过（O(N) 顺序扫描，只扫一次）。

        v7 简化（配合采集器休市清理）：
        - 采集器在休市时自动清空 CSV（只留 header）和 checkpoint 文件。
        - 开盘时 CSV 从 0 行开始追加，checkpoint 也从 0 开始，不会卡住。
        - 保留 offset > total_lines 的安全检测（应对进程重启等边缘情况）。
        - **CSV 并发读写保护**：使用 on_bad_lines='skip' 容忍并发写入的脏行。
        """
        offset = int(self._checkpoint.get_offset(csv_file))

        # --- 探测 CSV 实际行数 ---
        try:
            total_lines = sum(1 for _ in open(csv_file, "rb")) - 1  # 减去 header
            if total_lines < 0:
                total_lines = 0
        except OSError:
            total_lines = 0

        # Checkpoint 越界保护：如果 offset > CSV 行数（CSV 被清空/截断），重置到 0
        if offset > total_lines:
            logger.warning(
                "Checkpoint offset=%d > CSV lines=%d for %s (CSV was cleared). "
                "Resetting offset to 0.",
                offset, total_lines, Path(csv_file).name,
            )
            offset = 0
            self._checkpoint.set_offset(csv_file, 0)
            self._checkpoint.flush()

        # 没有新数据
        if offset >= total_lines:
            return 0

        # 用 chunksize 迭代器流式读取，on_bad_lines='skip' 容忍并发写入的脏行
        try:
            reader = pd.read_csv(
                csv_file,
                encoding="utf-8-sig",
                chunksize=self.cfg.batch_size,
                on_bad_lines="skip",
            )
        except Exception as e:
            logger.error("Failed to open CSV reader %s: %s", csv_file, e)
            return 0

        pushed = 0
        current_offset = 0
        pending_future: Optional[Future] = None  # 流水线模式：上一批推送的 future

        try:
            for chunk_df in reader:
                chunk_len = len(chunk_df)

                # 跳过已推送的行（顺序 skip，只扫一次，不回头）
                if current_offset + chunk_len <= offset:
                    current_offset += chunk_len
                    continue

                # 部分跳过（offset 落在 chunk 中间）
                if current_offset < offset:
                    skip_rows = offset - current_offset
                    chunk_df = chunk_df.iloc[skip_rows:]
                    current_offset = offset
                    chunk_len = len(chunk_df)

                if chunk_df.empty:
                    current_offset += chunk_len
                    continue

                items = self._df_to_items_vectorized(chunk_df, market)
                if not items:
                    current_offset += chunk_len
                    continue

                payload_bytes = self._build_payload_bytes(market, items)

                # ---------- 流水线模式 ----------
                if self._pipe_pool is not None and pending_future is not None:
                    # 等上一批推送完成
                    prev_ok, prev_count, prev_offset = pending_future.result()
                    if prev_ok:
                        self._checkpoint.set_offset(csv_file, prev_offset)
                        pushed += prev_count
                    else:
                        logger.error("Push failed (pipeline), stopping market=%s file=%s at offset=%d",
                                     market, Path(csv_file).name, prev_offset - prev_count)
                        break

                new_offset = current_offset + chunk_len

                if self._pipe_pool is not None:
                    # 异步提交推送，同时迭代器继续读下一批
                    pending_future = self._pipe_pool.submit(
                        self._push_and_report, market, payload_bytes, len(items), new_offset, csv_file
                    )
                else:
                    # 同步模式
                    success = self._push_bytes_to_all(market, payload_bytes)
                    if success:
                        self._checkpoint.set_offset(csv_file, new_offset)
                        pushed += len(items)
                        logger.info(
                            "Pushed market=%s file=%s rows=%d offset=%d",
                            market, Path(csv_file).name, len(items), new_offset,
                        )
                    else:
                        logger.error(
                            "Push failed, stopping market=%s file=%s at offset=%d",
                            market, Path(csv_file).name, current_offset,
                        )
                        break

                current_offset = new_offset

            # 处理流水线中最后一批
            if pending_future is not None:
                prev_ok, prev_count, prev_offset = pending_future.result()
                if prev_ok:
                    self._checkpoint.set_offset(csv_file, prev_offset)
                    pushed += prev_count
                else:
                    logger.error("Push failed (pipeline tail), market=%s file=%s", market, Path(csv_file).name)

        except Exception as e:
            logger.error("Error processing CSV %s: %s", csv_file, e)

        return pushed

    def _push_and_report(self, market: str, payload_bytes: bytes,
                         count: int, new_offset: int, csv_file: str) -> tuple:
        """流水线推送回调。返回 (success, count, new_offset)。"""
        success = self._push_bytes_to_all(market, payload_bytes)
        if success:
            logger.info("Pushed market=%s file=%s rows=%d offset=%d",
                        market, Path(csv_file).name, count, new_offset)
        return (success, count, new_offset)

    # ------------------------------------------------------------------
    # 向量化 DataFrame → items 转换（替代逐字段 isinstance 循环）
    # ------------------------------------------------------------------

    def _df_to_items_vectorized(self, df: pd.DataFrame, market: str) -> List[Dict[str, Any]]:
        """向量化 DataFrame → items。

        CPU 优化（v4）：
        - 去掉逐列 dtype 检查循环（最大 CPU 热点），直接用 .values.tolist() 转原生类型
        - NaN 清洗放在 DataFrame 层面用 where() 一次搞定
        - items 构造合并进同一个循环，减少一次遍历
        """
        if df.empty:
            return []

        # 确保 market 列
        if "market" not in df.columns:
            df["market"] = market
        else:
            df["market"] = df["market"].fillna(market)

        # 向量化清洗：inf → NaN，NaN → None（一次操作）
        df = df.replace([np.inf, -np.inf], np.nan).where(df.notna(), None)

        # 直接转 records — pandas 会自动将 numpy 类型转为 Python 原生类型
        # NaN 已被替换为 None，无需逐字段检查
        records = df.to_dict("records")

        # 生成 items（合并 tick 清洗和 items 构造到同一个循环）
        base_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        shards = self.cfg.shards

        items: List[Dict[str, Any]] = []
        for i, tick in enumerate(records):
            ts_code = tick.get("ts_code") or ""
            version = tick.get("version")
            if version is None:
                version = str(base_ms)

            items.append({
                "stream_id": f"{base_ms}-{i}",
                "ts_code": ts_code,
                "version": str(version),
                "shard_id": (hash(ts_code) % shards) if ts_code else 0,
                "tick": tick,
            })

        return items

    def _next_batch_seq(self, market: str) -> int:
        """线程安全地获取下一个 batch_seq"""
        with self._batch_seq_lock:
            self._batch_seq.setdefault(market, 0)
            self._batch_seq[market] += 1
            return self._batch_seq[market]

    def _build_payload_bytes(self, market: str, items: List[Dict[str, Any]]) -> bytes:
        """Build RawTickBatchPayload v2 并直接序列化为 bytes（避免二次序列化）。"""
        seq = self._next_batch_seq(market)
        event_time = datetime.now(timezone.utc).isoformat()

        first_stream_id = items[0]["stream_id"] if items else "0-0"
        last_stream_id = items[-1]["stream_id"] if items else "0-0"

        payload = {
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

        return _json_dumps(payload)

    def _push_bytes_to_all(self, market: str, payload_bytes: bytes) -> bool:
        """Push pre-serialized payload bytes to ALL configured URLs.

        多目标并行推送：一份数据同时推到多个节点。
        只要任一目标失败就返回 False（保证数据一致性）。
        """
        urls = self.cfg.push_urls
        if not urls:
            logger.warning("No push URL configured, skipping")
            return True

        if len(urls) == 1:
            return self._push_bytes_with_retry(market, payload_bytes, urls[0])

        # 多目标并行推送
        futures = {
            self._multi_push_pool.submit(
                self._push_bytes_with_retry, market, payload_bytes, url
            ): url
            for url in urls
        }

        all_ok = True
        for future in as_completed(futures):
            url = futures[future]
            try:
                if not future.result():
                    logger.error("Push failed to url=%s market=%s", url, market)
                    all_ok = False
            except Exception as e:
                logger.error("Push exception to url=%s market=%s: %s", url, market, e)
                all_ok = False

        return all_ok

    def _push_bytes_with_retry(self, market: str, payload_bytes: bytes, url: str) -> bool:
        """Push pre-serialized payload bytes to a single URL with retry logic.

        直接发送 bytes 避免 requests 内部 json.dumps 二次序列化。
        可选 gzip 压缩降低带宽。
        """
        if not url:
            logger.warning("No push URL configured, skipping")
            return True

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.cfg.push_token:
            headers["Authorization"] = f"Bearer {self.cfg.push_token}"

        body = payload_bytes
        if self.cfg.compress:
            import gzip
            body = gzip.compress(payload_bytes, compresslevel=1)  # 快速压缩
            headers["Content-Encoding"] = "gzip"

        for attempt in range(1, self.cfg.max_retry + 1):
            try:
                t0 = time.monotonic()
                resp = self._session.post(url, data=body, headers=headers, timeout=self.cfg.timeout)
                latency_ms = (time.monotonic() - t0) * 1000

                if resp.status_code == 200:
                    result = self._check_ack(resp)
                    if result == "ok":
                        logger.debug(
                            "Push OK market=%s url=%s latency=%.0fms size=%.1fKB",
                            market, url, latency_ms, len(body) / 1024,
                        )
                        return True
                    if result == "failed":
                        logger.error(
                            "Push ACK non-retryable market=%s url=%s resp=%s",
                            market, url, resp.text[:200],
                        )
                        return False

                elif resp.status_code not in _RETRYABLE_HTTP_STATUS:
                    logger.error(
                        "Push HTTP non-retryable market=%s url=%s status=%d body=%s",
                        market, url, resp.status_code, resp.text[:200],
                    )
                    return False

                logger.warning(
                    "Push retryable market=%s url=%s status=%d attempt=%d/%d latency=%.0fms",
                    market, url, resp.status_code, attempt, self.cfg.max_retry, latency_ms,
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
        try:
            code = int(ack.get("code", 0))
        except (TypeError, ValueError):
            code = -1

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
    parser.add_argument("--markets", default="a_stock",
                        help="要推送的市场，逗号分隔（默认仅 a_stock）")

    # 推送目标
    parser.add_argument("--push-url", default=os.getenv("RT_KLINE_CLOUD_PUSH_URL", ""),
                        help="云端推送 URL（支持逗号分隔多个 URL，同时推送到多个节点）")
    parser.add_argument("--push-token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""),
                        help="推送鉴权 Token（所有目标共用）")

    # 批量/重试
    parser.add_argument("--batch-size", type=int, default=3000,
                        help="每批推送条数（越大越少HTTP请求，速率越高）")
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
    parser.add_argument("--interval", type=float, default=0.0,
                        help="循环间隔(秒)，0 表示推完立即推下一轮（最大速率）")
    parser.add_argument("--rounds", type=int, default=0,
                        help="最大循环轮次，0 表示无限")

    # 断点
    parser.add_argument("--checkpoint-file", default="data/push_checkpoint.json",
                        help="断点记录文件路径")

    # 性能优化选项
    parser.add_argument("--pipeline", action="store_true",
                        help="启用读/推流水线：读下一批时同时推当前批")
    parser.add_argument("--compress", action="store_true",
                        help="启用 gzip 压缩推送（降低带宽，略增CPU）")

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

    logger.info("orjson available: %s | pipeline: %s | compress: %s",
                _HAS_ORJSON, args.pipeline, args.compress)

    if not args.push_url:
        print("[ERROR] missing --push-url or env RT_KLINE_CLOUD_PUSH_URL")
        return 1

    # 解析多目标 URL（逗号分隔）
    push_urls = [u.strip() for u in args.push_url.split(",") if u.strip()]
    if not push_urls:
        print("[ERROR] --push-url is empty after parsing")
        return 1

    logger.info("Push targets: %d URL(s) — %s", len(push_urls), push_urls)

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
        push_urls=push_urls,
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
        pipeline=args.pipeline,
        compress=args.compress,
    )

    pusher = CSVCloudPusher(cfg)

    round_no = 0
    while True:
        round_no += 1
        t0 = time.monotonic()

        stats = pusher.tick()
        total = sum(stats.values())
        elapsed = time.monotonic() - t0

        if total > 0:
            rate = total / elapsed if elapsed > 0 else 0
            logger.info("round=%d pushed=%d details=%s elapsed=%.2fs rate=%.0f/s",
                        round_no, total, stats, elapsed, rate)
        else:
            logger.debug("round=%d no new data elapsed=%.2fs", round_no, elapsed)

        if not args.loop:
            break
        if args.rounds > 0 and round_no >= args.rounds:
            break

        wait_s = max(0.0, args.interval - elapsed)
        if wait_s > 0:
            time.sleep(wait_s)

    logger.info("Done. Total rounds=%d", round_no)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
