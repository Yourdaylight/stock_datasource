#!/usr/bin/env python3
"""Standalone Cloud Push Receiver — 接收 push_csv_to_cloud.py 推送的实时行情数据。

特点：
1) 纯 Python，仅依赖 Flask（轻量 HTTP 服务）
2) 完全兼容 RawTickBatchPayload v2 协议
3) 支持 Bearer Token 鉴权
4) 数据落地到 JSON Lines 文件（每个 market 一个文件）
5) 可选转存到 CSV 文件（方便分析）
6) 支持去重（基于 stream_id）
7) 提供查询接口：最新数据、统计信息

用法示例：
  # 启动接收服务（默认 0.0.0.0:9100）
  python scripts/collection_and_push/receive_push_data.py

  # 指定端口和 Token 鉴权
  python scripts/collection_and_push/receive_push_data.py --port 9100 --token my_secret_token

  # 数据同时存 CSV
  python scripts/collection_and_push/receive_push_data.py --save-csv

  # 使用环境变量
  export RT_KLINE_CLOUD_PUSH_TOKEN=my_secret_token
  python scripts/collection_and_push/receive_push_data.py
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("receive_push_data")

# ---------------------------------------------------------------------------
# 协议常量（与 push_csv_to_cloud.py 保持一致）
# ---------------------------------------------------------------------------

VALID_MARKETS = {"a_stock", "etf", "index", "hk"}
VALID_SCHEMA_VERSIONS = {"v2"}
VALID_MODES = {"raw_tick_batch"}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class ReceiverConfig:
    host: str = "0.0.0.0"
    port: int = 9100
    token: str = ""                       # Bearer Token，空表示不鉴权
    data_dir: str = "data/received_push"  # 数据落地目录
    save_csv: bool = False                # 是否同时转存 CSV
    max_dedup_window: int = 100000        # 去重窗口（保留最近 N 个 stream_id）
    log_level: str = "INFO"
    debug: bool = False                   # Flask debug 模式


# ---------------------------------------------------------------------------
# 数据存储
# ---------------------------------------------------------------------------

class PushDataStore:
    """Thread-safe store for received push data."""

    def __init__(self, cfg: ReceiverConfig):
        self._cfg = cfg
        self._lock = threading.Lock()
        self._data_dir = Path(cfg.data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 统计
        self._stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "total_batches": 0,
            "total_items": 0,
            "last_batch_seq": 0,
            "last_event_time": "",
            "first_received_at": "",
            "last_received_at": "",
        })

        # 去重：每个 market 保留最近的 stream_id 集合
        self._seen_ids: Dict[str, Set[str]] = defaultdict(set)
        self._seen_order: Dict[str, list] = defaultdict(list)

        # 最新数据快照：market -> {ts_code -> tick}
        self._latest: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    def store_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Store a push batch. Returns ACK info."""
        market = payload["market"]
        items = payload.get("items", [])
        batch_seq = payload.get("batch_seq", 0)
        event_time = payload.get("event_time", "")
        now = datetime.now(timezone.utc).isoformat()

        accepted = 0
        rejected = 0
        new_items: List[Dict[str, Any]] = []

        with self._lock:
            for item in items:
                stream_id = item.get("stream_id", "")

                # 去重
                if stream_id and stream_id in self._seen_ids[market]:
                    rejected += 1
                    continue

                # 记录 stream_id（滑动窗口去重）
                if stream_id:
                    self._seen_ids[market].add(stream_id)
                    self._seen_order[market].append(stream_id)
                    # 超过窗口大小则淘汰最早的
                    while len(self._seen_order[market]) > self._cfg.max_dedup_window:
                        old_id = self._seen_order[market].pop(0)
                        self._seen_ids[market].discard(old_id)

                # 更新最新快照
                ts_code = item.get("ts_code", "")
                tick = item.get("tick", {})
                if ts_code and tick:
                    self._latest[market][ts_code] = tick

                new_items.append(item)
                accepted += 1

            # 更新统计
            stats = self._stats[market]
            if not stats["first_received_at"]:
                stats["first_received_at"] = now
            stats["last_received_at"] = now
            stats["total_batches"] += 1
            stats["total_items"] += accepted
            stats["last_batch_seq"] = batch_seq
            stats["last_event_time"] = event_time

        # 异步写磁盘（不阻塞响应）
        if new_items:
            threading.Thread(
                target=self._persist,
                args=(market, payload, new_items),
                daemon=True,
            ).start()

        return {
            "status": "ok",
            "code": 0,
            "ack_seq": batch_seq,
            "accepted_count": accepted,
            "rejected_count": rejected,
        }

    def _persist(self, market: str, payload: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
        """Write items to JSONL file (and optionally CSV)."""
        try:
            # JSON Lines 文件
            jsonl_path = self._data_dir / f"{market}.jsonl"
            with open(jsonl_path, "a", encoding="utf-8") as f:
                for item in items:
                    record = {
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "batch_seq": payload.get("batch_seq", 0),
                        "market": market,
                        "source_api": payload.get("source_api", ""),
                        **item,
                    }
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            # 可选 CSV
            if self._cfg.save_csv:
                self._persist_csv(market, items)

        except Exception as e:
            logger.error("Persist failed market=%s: %s", market, e)

    def _persist_csv(self, market: str, items: List[Dict[str, Any]]) -> None:
        """Append tick data to CSV file, organized by date.

        CSV 文件按日期分片: {market}_{YYYYMMDD}.csv
        每行包含元信息列(received_at, stream_id, ts_code, shard_id) + tick 所有字段。
        自动扩展列头：遇到新字段时重写 CSV 文件头。
        """
        all_ticks = [item.get("tick", {}) for item in items if item.get("tick")]
        if not all_ticks:
            return

        # 按日期分组（从 tick 中提取日期，回退用当前日期）
        date_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        today_str = datetime.now().strftime("%Y%m%d")

        for item in items:
            tick = item.get("tick", {})
            if not tick:
                continue
            # 尝试从 tick 中获取日期：trade_date > datetime > 当天
            trade_date = tick.get("trade_date") or tick.get("datetime", "")
            if isinstance(trade_date, str) and len(trade_date) >= 8:
                date_key = trade_date[:8].replace("-", "")
            else:
                date_key = today_str
            date_groups[date_key].append(item)

        for date_key, group_items in date_groups.items():
            self._write_csv_group(market, date_key, group_items)

    def _write_csv_group(self, market: str, date_key: str, items: List[Dict[str, Any]]) -> None:
        """Write a group of items to the dated CSV file."""
        csv_path = self._data_dir / f"{market}_{date_key}.csv"
        is_new = not csv_path.exists()

        # 元信息列（固定在最前面）
        meta_cols = ["received_at", "stream_id", "ts_code", "shard_id"]

        # 收集本批所有 tick 字段（合并，保序）
        tick_cols: List[str] = []
        seen_cols: set = set()
        for item in items:
            for col in item.get("tick", {}).keys():
                if col not in seen_cols and col not in meta_cols:
                    tick_cols.append(col)
                    seen_cols.add(col)

        # 如果文件已存在，读取已有列头并合并
        existing_cols: List[str] = []
        if not is_new:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header_row = next(reader, None)
                    if header_row:
                        existing_cols = header_row
            except Exception:
                existing_cols = []

        if existing_cols:
            # 合并：保留已有顺序，末尾追加新字段
            existing_set = set(existing_cols)
            new_cols = [c for c in tick_cols if c not in existing_set]
            if new_cols:
                # 有新字段：需要重写整个 CSV 文件
                final_header = existing_cols + new_cols
                self._rewrite_csv_with_new_header(csv_path, final_header)
            else:
                final_header = existing_cols
        else:
            final_header = meta_cols + tick_cols

        now_str = datetime.now(timezone.utc).isoformat()

        with open(csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=final_header, extrasaction="ignore")
            if is_new or not existing_cols:
                writer.writeheader()
            for item in items:
                tick = item.get("tick", {})
                row = {
                    "received_at": now_str,
                    "stream_id": item.get("stream_id", ""),
                    "ts_code": item.get("ts_code", ""),
                    "shard_id": item.get("shard_id", ""),
                    **tick,
                }
                writer.writerow(row)

    @staticmethod
    def _rewrite_csv_with_new_header(csv_path: Path, new_header: List[str]) -> None:
        """Rewrite existing CSV file with expanded header (add new columns)."""
        try:
            rows = []
            with open(csv_path, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(row)

            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=new_header, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
        except Exception as e:
            logger.error("Failed to rewrite CSV %s: %s", csv_path, e)

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregated stats."""
        with self._lock:
            return {
                "markets": dict(self._stats),
                "latest_counts": {
                    market: len(ticks) for market, ticks in self._latest.items()
                },
            }

    def get_latest(self, market: Optional[str] = None, ts_code: Optional[str] = None,
                   limit: int = 100) -> Dict[str, Any]:
        """Query latest tick snapshots."""
        with self._lock:
            if ts_code:
                # 查单只
                for mkt, ticks in self._latest.items():
                    if market and mkt != market:
                        continue
                    if ts_code in ticks:
                        return {"count": 1, "data": [ticks[ts_code]]}
                return {"count": 0, "data": []}

            if market:
                ticks = self._latest.get(market, {})
                data = list(ticks.values())[:limit]
                return {"count": len(data), "data": data}

            # 全部
            data = []
            for mkt in sorted(self._latest.keys()):
                for tick in self._latest[mkt].values():
                    data.append(tick)
                    if len(data) >= limit:
                        break
                if len(data) >= limit:
                    break
            return {"count": len(data), "data": data}


# ---------------------------------------------------------------------------
# Payload 校验
# ---------------------------------------------------------------------------

def validate_payload(payload: Dict[str, Any], require_token: str = "") -> Optional[str]:
    """Validate incoming push payload. Returns error message or None."""
    if not isinstance(payload, dict):
        return "payload must be a JSON object"

    schema_version = payload.get("schema_version")
    if schema_version not in VALID_SCHEMA_VERSIONS:
        return f"unsupported schema_version: {schema_version}, expected: {VALID_SCHEMA_VERSIONS}"

    mode = payload.get("mode")
    if mode not in VALID_MODES:
        return f"unsupported mode: {mode}, expected: {VALID_MODES}"

    market = payload.get("market")
    if market not in VALID_MARKETS:
        return f"invalid market: {market}, valid: {VALID_MARKETS}"

    items = payload.get("items")
    if not isinstance(items, list):
        return "items must be an array"

    count = payload.get("count")
    if count is not None and count != len(items):
        return f"count mismatch: declared {count}, actual {len(items)}"

    batch_seq = payload.get("batch_seq")
    if batch_seq is None:
        return "missing batch_seq"

    return None


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

def create_app(cfg: ReceiverConfig) -> Any:
    """Create Flask application."""
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        print("[ERROR] Flask is required. Install it with: pip install flask")
        sys.exit(1)

    app = Flask(__name__)
    store = PushDataStore(cfg)

    @app.before_request
    def check_auth():
        """Check Bearer token if configured."""
        if not cfg.token:
            return None

        # 跳过非推送接口的鉴权
        if request.path in ("/health", "/stats", "/"):
            return None

        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"status": "error", "code": 401, "message": "missing Authorization header"}), 401

        token = auth[7:].strip()
        if token != cfg.token:
            return jsonify({"status": "error", "code": 403, "message": "invalid token"}), 403

        return None

    # ---- 推送接收接口 ----

    @app.route("/api/v1/rt-kline/push", methods=["POST"])
    def receive_push():
        """接收 push_csv_to_cloud.py 推送的数据。"""
        try:
            payload = request.get_json(silent=True)
            if payload is None:
                return jsonify({
                    "status": "error",
                    "code": 400,
                    "ack_seq": 0,
                    "accepted_count": 0,
                    "rejected_count": 0,
                }), 400

            # 校验
            err = validate_payload(payload)
            if err:
                logger.warning("Invalid payload: %s", err)
                return jsonify({
                    "status": "error",
                    "code": 400,
                    "message": err,
                    "ack_seq": payload.get("batch_seq", 0),
                    "accepted_count": 0,
                    "rejected_count": payload.get("count", 0),
                }), 400

            # 存储
            ack = store.store_batch(payload)

            logger.info(
                "Received market=%s batch_seq=%d count=%d accepted=%d rejected=%d",
                payload.get("market"),
                payload.get("batch_seq", 0),
                payload.get("count", 0),
                ack["accepted_count"],
                ack["rejected_count"],
            )

            return jsonify(ack), 200

        except Exception as e:
            logger.error("Receive push error: %s", e, exc_info=True)
            return jsonify({
                "status": "retryable",
                "code": 500,
                "ack_seq": 0,
                "accepted_count": 0,
                "rejected_count": 0,
            }), 500

    # ---- 查询接口 ----

    @app.route("/api/v1/rt-kline/latest", methods=["GET"])
    def query_latest():
        """查询最新行情快照。"""
        market = request.args.get("market")
        ts_code = request.args.get("ts_code")
        limit = int(request.args.get("limit", 100))
        result = store.get_latest(market=market, ts_code=ts_code, limit=limit)
        return jsonify(result), 200

    @app.route("/stats", methods=["GET"])
    def get_stats():
        """查看统计信息。"""
        return jsonify(store.get_stats()), 200

    @app.route("/health", methods=["GET"])
    def health():
        """健康检查。"""
        return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}), 200

    @app.route("/", methods=["GET"])
    def index():
        """首页。"""
        return jsonify({
            "service": "push-data-receiver",
            "version": "1.0.0",
            "endpoints": {
                "POST /api/v1/rt-kline/push": "接收推送数据（RawTickBatchPayload v2）",
                "GET  /api/v1/rt-kline/latest": "查询最新行情快照（?market=&ts_code=&limit=）",
                "GET  /stats": "统计信息",
                "GET  /health": "健康检查",
            },
        }), 200

    return app


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive push data from push_csv_to_cloud.py (RawTickBatchPayload v2 protocol)."
    )

    parser.add_argument("--host", default="0.0.0.0",
                        help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=9100,
                        help="监听端口（默认 9100）")
    parser.add_argument("--token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""),
                        help="Bearer Token 鉴权（为空则不鉴权）")
    parser.add_argument("--data-dir", default="data/received_push",
                        help="数据落地目录（默认 data/received_push）")
    parser.add_argument("--save-csv", action="store_true",
                        help="同时将 tick 数据转存为 CSV 文件")
    parser.add_argument("--max-dedup-window", type=int, default=100000,
                        help="去重滑动窗口大小（默认 100000）")
    parser.add_argument("--log-level", default="INFO",
                        help="日志级别: DEBUG/INFO/WARNING/ERROR")
    parser.add_argument("--debug", action="store_true",
                        help="Flask debug 模式（开发用）")

    return parser.parse_args()


def main() -> int:
    args = build_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    cfg = ReceiverConfig(
        host=args.host,
        port=args.port,
        token=args.token.strip(),
        data_dir=args.data_dir,
        save_csv=args.save_csv,
        max_dedup_window=max(1000, args.max_dedup_window),
        log_level=args.log_level,
        debug=args.debug,
    )

    # 打印启动信息
    print(f"""
╔══════════════════════════════════════════════════╗
║          Push Data Receiver v1.0.0               ║
╠══════════════════════════════════════════════════╣
║  Listen   : {cfg.host}:{cfg.port:<30s}  ║
║  Push URL : /api/v1/rt-kline/push                ║
║  Auth     : {'Token Required' if cfg.token else 'No Auth (open)':<33s} ║
║  Data Dir : {cfg.data_dir:<33s}  ║
║  Save CSV : {str(cfg.save_csv):<33s}  ║
╚══════════════════════════════════════════════════╝
""")

    app = create_app(cfg)
    app.run(host=cfg.host, port=cfg.port, debug=cfg.debug)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
