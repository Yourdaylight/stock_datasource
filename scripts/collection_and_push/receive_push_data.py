#!/usr/bin/env python3
"""Standalone cloud push receiver with spool + SQLite snapshot storage."""

from __future__ import annotations

import argparse
import atexit
import csv
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import fcntl

logger = logging.getLogger("receive_push_data")

VALID_MARKETS = {"a_stock", "etf", "index", "hk"}
VALID_SCHEMA_VERSIONS = {"v2"}
VALID_MODES = {"raw_tick_batch"}


@dataclass
class ReceiverConfig:
    host: str = "0.0.0.0"
    port: int = 9100
    token: str = ""
    push_token: str = ""
    policy_token: str = ""
    jwt_public_key_path: str = ""
    data_dir: str = "data/received_push"
    spool_dir: str = ""
    snapshot_dir: str = ""
    sqlite_path: str = ""
    save_csv: bool = False
    flush_interval_seconds: int = 3
    flush_max_items: int = 2000
    subscription_step_seconds: int = 3
    log_level: str = "INFO"
    debug: bool = False


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if not symbol or "." not in symbol:
        raise ValueError(f"invalid symbol: {value}")
    return symbol


def normalize_market(value: str) -> str:
    market = str(value or "").strip().upper()
    alias = {
        "A_STOCK": "CN",
        "ASTOCK": "CN",
        "CN": "CN",
        "STOCK": "CN",
        "ETF": "CN",
        "INDEX": "CN",
        "HK": "HK",
    }
    return alias.get(market, market)


def detect_symbol_market(symbol: str) -> str:
    symbol = normalize_symbol(symbol)
    return "HK" if symbol.endswith(".HK") else "CN"


def parse_symbol_list(raw: str) -> List[str]:
    values = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        values.append(normalize_symbol(item))
    return values


def parse_symbol_items(raw_items: Iterable[Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    symbols: List[str] = []
    rejected: List[Dict[str, str]] = []
    for item in raw_items:
        try:
            symbols.append(normalize_symbol(str(item or "")))
        except ValueError as exc:
            rejected.append({"symbol": str(item), "reason": str(exc)})
    return symbols, rejected


def load_public_key(path: str) -> bytes:
    if not path:
        raise ValueError("jwt public key path is required")
    key_path = Path(path)
    if not key_path.exists():
        raise ValueError(f"jwt public key not found: {key_path}")
    return key_path.read_bytes()


def verify_subscription_token(token: str, public_key_path: str) -> Tuple[bool, Dict[str, Any], str]:
    if not token:
        return False, {}, "missing token"
    try:
        import jwt as pyjwt

        public_key = load_public_key(public_key_path)
        claims = pyjwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_iss": False,
                "verify_aud": False,
            },
        )
        scope = claims.get("scope") or {}
        if not isinstance(scope, dict):
            return False, {}, "invalid scope"
        scope_type = scope.get("type", "")
        if scope_type not in ("realtime_stock", "") and "markets" not in scope:
            return False, {}, f"invalid token scope type: {scope_type}"
        return True, claims, ""
    except ImportError:
        return False, {}, "PyJWT is required for subscription auth"
    except Exception as exc:
        name = type(exc).__name__
        if "ExpiredSignature" in name:
            return False, {}, "token expired"
        return False, {}, f"invalid token: {exc}"


def build_effective_subscription_scope(claims: Dict[str, Any], policy: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    scope = claims.get("scope") or {}
    token_markets = {normalize_market(item) for item in scope.get("markets", []) if item}
    token_levels = {str(item).upper() for item in scope.get("levels", []) if item}
    token_symbols = scope.get("symbols") or {}
    token_symbol_mode = str(token_symbols.get("mode", "all") or "all").lower()
    token_symbol_list = {normalize_symbol(item) for item in token_symbols.get("list", []) if item}
    token_quota = scope.get("quota") or {}
    token_max_subs = int(token_quota.get("max_subs", 0) or 0)

    if not policy:
        return {
            "user_id": str(claims.get("sub") or claims.get("username") or "").strip(),
            "markets": token_markets,
            "levels": token_levels,
            "max_subs": token_max_subs,
            "symbol_mode": token_symbol_mode,
            "symbol_list": token_symbol_list,
            "revision": int(claims.get("rev", 0) or 0),
        }

    policy_markets = {normalize_market(item) for item in policy.get("markets", []) if item}
    policy_levels = {str(item).upper() for item in policy.get("levels", []) if item}
    policy_max_subs = int(policy.get("max_subs", 0) or 0)
    policy_symbols = policy.get("symbols") or {}
    policy_symbol_mode = str(policy_symbols.get("mode", "all") or "all").lower()
    policy_symbol_list = {normalize_symbol(item) for item in policy_symbols.get("list", []) if item}

    markets = token_markets & policy_markets if token_markets and policy_markets else token_markets or policy_markets
    levels = token_levels & policy_levels if token_levels and policy_levels else token_levels or policy_levels
    max_subs = min(token_max_subs, policy_max_subs) if token_max_subs and policy_max_subs else token_max_subs or policy_max_subs

    symbol_mode = token_symbol_mode
    symbol_list = set(token_symbol_list)
    if policy_symbol_mode == "list":
        symbol_mode = "list"
        symbol_list = symbol_list & policy_symbol_list if symbol_list else set(policy_symbol_list)

    return {
        "user_id": str(claims.get("sub") or claims.get("username") or "").strip(),
        "markets": markets,
        "levels": levels,
        "max_subs": max_subs,
        "symbol_mode": symbol_mode,
        "symbol_list": symbol_list,
        "revision": max(int(claims.get("rev", 0) or 0), int(policy.get("revision", 0) or 0)),
    }


def validate_subscription_symbols(symbols: List[str], effective_scope: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, str]]]:
    max_subs = int(effective_scope.get("max_subs", 0) or 0)
    markets = set(effective_scope.get("markets", set()))
    symbol_mode = effective_scope.get("symbol_mode", "all")
    symbol_list = set(effective_scope.get("symbol_list", set()))

    unique_symbols: List[str] = []
    seen = set()
    rejected: List[Dict[str, str]] = []

    for symbol in symbols:
        if symbol in seen:
            continue
        seen.add(symbol)
        market = detect_symbol_market(symbol)
        if markets and market not in markets:
            rejected.append({"symbol": symbol, "reason": "market_not_allowed"})
            continue
        if symbol_mode == "list" and symbol_list and symbol not in symbol_list:
            rejected.append({"symbol": symbol, "reason": "symbol_not_allowed"})
            continue
        unique_symbols.append(symbol)

    if max_subs > 0 and len(unique_symbols) > max_subs:
        overflow = unique_symbols[max_subs:]
        unique_symbols = unique_symbols[:max_subs]
        for symbol in overflow:
            rejected.append({"symbol": symbol, "reason": "quota_exceeded"})

    return unique_symbols, rejected


def validate_payload(payload: Dict[str, Any]) -> Optional[str]:
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


@contextmanager
def locked_file(path: Path, mode: str, lock_type: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode) as handle:
        fcntl.flock(handle.fileno(), lock_type)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class PushDataStore:
    def __init__(self, cfg: ReceiverConfig):
        self._cfg = cfg
        self._base_dir = Path(cfg.data_dir)
        self._spool_dir = Path(cfg.spool_dir) if cfg.spool_dir else self._base_dir / "spool"
        self._snapshot_dir = Path(cfg.snapshot_dir) if cfg.snapshot_dir else self._base_dir / "snapshot"
        self._db_path = Path(cfg.sqlite_path) if cfg.sqlite_path else self._snapshot_dir / "rt_snapshot.db"
        self._builder_lock_path = self._snapshot_dir / ".builder.lock"
        self._stop_event = threading.Event()
        self._builder_thread: Optional[threading.Thread] = None

        self._spool_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def start_builder(self) -> None:
        if self._builder_thread is not None:
            return
        self._builder_thread = threading.Thread(target=self._builder_loop, name="rt-snapshot-builder", daemon=True)
        self._builder_thread.start()

    def stop_builder(self) -> None:
        self._stop_event.set()
        if self._builder_thread is not None:
            self._builder_thread.join(timeout=max(1, self._cfg.flush_interval_seconds + 1))
            self._builder_thread = None

    def _builder_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                result = self.process_spool_once(max_items=self._cfg.flush_max_items)
                if result.get("processed", 0):
                    logger.info(
                        "Flushed spool to SQLite processed=%d upserts=%d",
                        result.get("processed", 0),
                        result.get("upserts", 0),
                    )
            except Exception as exc:
                logger.error("Snapshot builder failed: %s", exc, exc_info=True)
            self._stop_event.wait(self._cfg.flush_interval_seconds)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS latest_ticks (
                    market TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    source_api TEXT NOT NULL DEFAULT '',
                    batch_seq INTEGER NOT NULL DEFAULT 0,
                    event_time TEXT NOT NULL DEFAULT '',
                    received_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (market, ts_code)
                );

                CREATE INDEX IF NOT EXISTS idx_latest_ticks_ts_code ON latest_ticks(ts_code);

                CREATE TABLE IF NOT EXISTS ingest_offsets (
                    file_path TEXT PRIMARY KEY,
                    offset INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS user_policies (
                    user_id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS user_subscriptions (
                    user_id TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (user_id, ts_code)
                );

                CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user_id
                    ON user_subscriptions(user_id);

                CREATE TABLE IF NOT EXISTS runtime_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                """
            )

    def _spool_file_path(self, market: str, received_at: str) -> Path:
        date_key = received_at[:10].replace("-", "")
        return self._spool_dir / market / f"{date_key}.jsonl"

    def store_batch(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        market = payload["market"]
        items = payload.get("items", [])
        batch_seq = int(payload.get("batch_seq", 0) or 0)
        event_time = str(payload.get("event_time", "") or "")
        source_api = str(payload.get("source_api", "") or "")
        received_at = utc_now_iso()
        spool_path = self._spool_file_path(market, received_at)

        records: List[Dict[str, Any]] = []
        for item in items:
            ts_code = str(item.get("ts_code", "") or "").strip().upper()
            tick = item.get("tick") or {}
            if not ts_code or not isinstance(tick, dict):
                continue
            tick.setdefault("ts_code", ts_code)
            tick.setdefault("market", market)
            records.append(
                {
                    "received_at": received_at,
                    "market": market,
                    "batch_seq": batch_seq,
                    "event_time": event_time,
                    "source_api": source_api,
                    "stream_id": str(item.get("stream_id", "") or ""),
                    "ts_code": ts_code,
                    "shard_id": item.get("shard_id"),
                    "tick": tick,
                }
            )

        if records:
            payload_bytes = b"".join(
                (json.dumps(record, ensure_ascii=False, default=str) + "\n").encode("utf-8")
                for record in records
            )
            with locked_file(spool_path, "ab", fcntl.LOCK_EX) as handle:
                handle.write(payload_bytes)
                handle.flush()

        return {
            "status": "ok",
            "code": 0,
            "ack_seq": batch_seq,
            "accepted_count": len(records),
            "rejected_count": max(0, len(items) - len(records)),
        }

    def _iter_spool_files(self) -> Iterable[Path]:
        for market_dir in sorted(path for path in self._spool_dir.iterdir() if path.is_dir()):
            for spool_file in sorted(market_dir.glob("*.jsonl")):
                yield spool_file

    def _read_offset(self, conn: sqlite3.Connection, file_path: str) -> int:
        row = conn.execute("SELECT offset FROM ingest_offsets WHERE file_path = ?", (file_path,)).fetchone()
        return int(row[0]) if row else 0

    def process_spool_once(self, max_items: Optional[int] = None) -> Dict[str, int]:
        processed = 0
        updates: Dict[Tuple[str, str], Dict[str, Any]] = {}
        new_offsets: Dict[str, int] = {}
        touched_markets = set()

        try:
            with locked_file(self._builder_lock_path, "a+", fcntl.LOCK_EX | fcntl.LOCK_NB):
                with self._connect() as conn:
                    stop = False
                    for spool_file in self._iter_spool_files():
                        file_key = str(spool_file.resolve())
                        offset = self._read_offset(conn, file_key)
                        new_offset = offset
                        with open(spool_file, "rb") as handle:
                            handle.seek(offset)
                            while True:
                                line_start = handle.tell()
                                line = handle.readline()
                                if not line:
                                    break
                                if not line.endswith(b"\n"):
                                    new_offset = line_start
                                    break
                                new_offset = handle.tell()
                                record = json.loads(line.decode("utf-8"))
                                market = str(record.get("market", "") or "").strip()
                                ts_code = str(record.get("ts_code", "") or "").strip().upper()
                                tick = record.get("tick") or {}
                                if not market or not ts_code or not isinstance(tick, dict):
                                    continue
                                tick.setdefault("ts_code", ts_code)
                                tick.setdefault("market", market)
                                payload_json = json.dumps(tick, ensure_ascii=False, default=str)
                                updates[(market, ts_code)] = {
                                    "market": market,
                                    "ts_code": ts_code,
                                    "payload_json": payload_json,
                                    "source_api": str(record.get("source_api", "") or ""),
                                    "batch_seq": int(record.get("batch_seq", 0) or 0),
                                    "event_time": str(record.get("event_time", "") or ""),
                                    "received_at": str(record.get("received_at", "") or ""),
                                    "updated_at": utc_now_iso(),
                                }
                                touched_markets.add(market)
                                processed += 1
                                if max_items and processed >= max_items:
                                    stop = True
                                    break
                        if new_offset != offset:
                            new_offsets[file_key] = new_offset
                        if stop:
                            break

                    if not new_offsets and not updates:
                        return {"processed": 0, "upserts": 0}

                    now = utc_now_iso()
                    with conn:
                        if updates:
                            conn.executemany(
                                """
                                INSERT INTO latest_ticks (
                                    market, ts_code, payload_json, source_api, batch_seq, event_time, received_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                ON CONFLICT(market, ts_code) DO UPDATE SET
                                    payload_json = excluded.payload_json,
                                    source_api = excluded.source_api,
                                    batch_seq = excluded.batch_seq,
                                    event_time = excluded.event_time,
                                    received_at = excluded.received_at,
                                    updated_at = excluded.updated_at
                                """,
                                [
                                    (
                                        row["market"],
                                        row["ts_code"],
                                        row["payload_json"],
                                        row["source_api"],
                                        row["batch_seq"],
                                        row["event_time"],
                                        row["received_at"],
                                        row["updated_at"],
                                    )
                                    for row in updates.values()
                                ],
                            )
                        if new_offsets:
                            conn.executemany(
                                """
                                INSERT INTO ingest_offsets (file_path, offset, updated_at)
                                VALUES (?, ?, ?)
                                ON CONFLICT(file_path) DO UPDATE SET
                                    offset = excluded.offset,
                                    updated_at = excluded.updated_at
                                """,
                                [(path, offset, now) for path, offset in new_offsets.items()],
                            )
                        conn.executemany(
                            """
                            INSERT INTO runtime_meta (key, value, updated_at)
                            VALUES (?, ?, ?)
                            ON CONFLICT(key) DO UPDATE SET
                                value = excluded.value,
                                updated_at = excluded.updated_at
                            """,
                            [
                                ("last_flush_at", now, now),
                                ("last_flush_items", str(processed), now),
                            ],
                        )

                if self._cfg.save_csv and touched_markets:
                    self._export_snapshot_csv(touched_markets)
                return {"processed": processed, "upserts": len(updates)}
        except BlockingIOError:
            return {"processed": 0, "upserts": 0}

    def _export_snapshot_csv(self, markets: Iterable[str]) -> None:
        for market in sorted(set(markets)):
            rows = self._query_rows(
                "SELECT payload_json FROM latest_ticks WHERE market = ? ORDER BY ts_code",
                (market,),
            )
            payloads = [json.loads(row["payload_json"]) for row in rows]
            if not payloads:
                continue
            header: List[str] = []
            seen = set()
            for payload in payloads:
                for key in payload.keys():
                    if key not in seen:
                        header.append(key)
                        seen.add(key)
            tmp_path = self._snapshot_dir / f"{market}_latest.csv.tmp"
            final_path = self._snapshot_dir / f"{market}_latest.csv"
            with open(tmp_path, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header, extrasaction="ignore")
                writer.writeheader()
                for payload in payloads:
                    writer.writerow(payload)
            os.replace(tmp_path, final_path)

    def _query_rows(self, sql: str, params: Tuple[Any, ...] = ()) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(sql, params).fetchall()

    def get_stats(self) -> Dict[str, Any]:
        with self._connect() as conn:
            latest_counts = {
                row["market"]: row["count"]
                for row in conn.execute(
                    "SELECT market, COUNT(*) AS count FROM latest_ticks GROUP BY market ORDER BY market"
                ).fetchall()
            }
            offset_count = conn.execute("SELECT COUNT(*) FROM ingest_offsets").fetchone()[0]
            policy_count = conn.execute("SELECT COUNT(*) FROM user_policies").fetchone()[0]
            subscription_rows = conn.execute("SELECT COUNT(*) FROM user_subscriptions").fetchone()[0]
            subscription_users = conn.execute("SELECT COUNT(DISTINCT user_id) FROM user_subscriptions").fetchone()[0]
            meta = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM runtime_meta").fetchall()
            }
        return {
            "latest_counts": latest_counts,
            "offset_files": offset_count,
            "policy_count": policy_count,
            "subscription_rows": subscription_rows,
            "subscription_users": subscription_users,
            "flush_interval_seconds": self._cfg.flush_interval_seconds,
            "last_flush_at": meta.get("last_flush_at", ""),
            "last_flush_items": int(meta.get("last_flush_items", 0) or 0),
        }

    def get_latest(self, market: Optional[str] = None, ts_code: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
        limit = max(1, min(int(limit or 100), 2000))
        if ts_code:
            sql = "SELECT market, payload_json FROM latest_ticks WHERE ts_code = ?"
            params: Tuple[Any, ...] = (ts_code,)
            if market:
                sql += " AND market = ?"
                params = (ts_code, market)
            rows = self._query_rows(sql + " LIMIT 1", params)
        elif market:
            rows = self._query_rows(
                "SELECT market, payload_json FROM latest_ticks WHERE market = ? ORDER BY updated_at DESC LIMIT ?",
                (market, limit),
            )
        else:
            rows = self._query_rows(
                "SELECT market, payload_json FROM latest_ticks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            )
        data = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload.setdefault("market", row["market"])
            data.append(payload)
        return {"count": len(data), "data": data}

    def apply_policies(self, payload: Dict[str, Any]) -> int:
        users = payload.get("users", []) if isinstance(payload, dict) else []
        applied = 0
        now = utc_now_iso()
        rows = []
        for item in users:
            user_id = str(item.get("user_id", "") or "").strip()
            if not user_id:
                continue
            rows.append((user_id, json.dumps(item, ensure_ascii=False, default=str), int(item.get("revision", 0) or 0), now))
            applied += 1
        if rows:
            with self._connect() as conn:
                with conn:
                    conn.executemany(
                        """
                        INSERT INTO user_policies (user_id, payload_json, revision, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET
                            payload_json = excluded.payload_json,
                            revision = excluded.revision,
                            updated_at = excluded.updated_at
                        """,
                        rows,
                    )
        return applied

    def get_policy(self, user_id: str) -> Optional[Dict[str, Any]]:
        rows = self._query_rows("SELECT payload_json FROM user_policies WHERE user_id = ? LIMIT 1", (user_id,))
        if not rows:
            return None
        return json.loads(rows[0]["payload_json"])

    def get_user_subscriptions(self, user_id: str) -> List[str]:
        rows = self._query_rows(
            "SELECT ts_code FROM user_subscriptions WHERE user_id = ? ORDER BY updated_at, ts_code",
            (user_id,),
        )
        return [str(row["ts_code"] or "").strip().upper() for row in rows if row["ts_code"]]

    def replace_user_subscriptions(self, user_id: str, symbols: List[str]) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            with conn:
                conn.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
                if symbols:
                    conn.executemany(
                        "INSERT INTO user_subscriptions (user_id, ts_code, updated_at) VALUES (?, ?, ?)",
                        [(user_id, symbol, now) for symbol in symbols],
                    )

    def sync_user_subscriptions(self, user_id: str, symbols: List[str], effective_scope: Dict[str, Any], mode: str = "replace") -> Dict[str, Any]:
        current_symbols = self.get_user_subscriptions(user_id)
        current_set = set(current_symbols)
        normalized_symbols, invalid = parse_symbol_items(symbols)

        if mode == "add":
            candidate_symbols = list(current_symbols)
            for symbol in normalized_symbols:
                if symbol not in current_set:
                    candidate_symbols.append(symbol)
                    current_set.add(symbol)
        elif mode == "remove":
            remove_set = set(normalized_symbols)
            candidate_symbols = [symbol for symbol in current_symbols if symbol not in remove_set]
        else:
            candidate_symbols = normalized_symbols

        accepted_symbols, rejected_symbols = validate_subscription_symbols(candidate_symbols, effective_scope)
        rejected_symbols = invalid + rejected_symbols
        self.replace_user_subscriptions(user_id, accepted_symbols)
        return {
            "user_id": user_id,
            "mode": mode,
            "accepted_symbols": accepted_symbols,
            "rejected_symbols": rejected_symbols,
            "current_subscriptions": len(accepted_symbols),
            "max_subs": int(effective_scope.get("max_subs", 0) or 0),
            "revision": int(effective_scope.get("revision", 0) or 0),
        }

    def get_subscription_snapshot(self, symbols: List[str], step_seconds: int) -> Dict[str, Any]:
        ordered_symbols = []
        seen = set()
        for symbol in symbols:
            if symbol in seen:
                continue
            seen.add(symbol)
            ordered_symbols.append(symbol)

        payloads: Dict[str, Dict[str, Any]] = {}
        for chunk_start in range(0, len(ordered_symbols), 200):
            chunk = ordered_symbols[chunk_start:chunk_start + 200]
            placeholders = ",".join("?" for _ in chunk)
            rows = self._query_rows(
                f"SELECT market, ts_code, payload_json FROM latest_ticks WHERE ts_code IN ({placeholders})",
                tuple(chunk),
            )
            for row in rows:
                payload = json.loads(row["payload_json"])
                payload.setdefault("market", row["market"])
                payload.setdefault("ts_code", row["ts_code"])
                payloads[row["ts_code"]] = payload

        data = [payloads[symbol] for symbol in ordered_symbols if symbol in payloads]
        missing = [symbol for symbol in ordered_symbols if symbol not in payloads]
        return {
            "count": len(data),
            "step_seconds": step_seconds,
            "data": data,
            "missing": missing,
        }


def create_app(cfg: ReceiverConfig) -> Any:
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        print("[ERROR] Flask is required. Install it with: pip install flask")
        sys.exit(1)

    app = Flask(__name__)
    store = PushDataStore(cfg)
    store.start_builder()
    atexit.register(store.stop_builder)
    app.config["push_data_store"] = store

    def authenticate_subscription_request() -> Tuple[str, Dict[str, Any]]:
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.startswith("Bearer ") else auth.strip()
        if not cfg.jwt_public_key_path:
            raise ValueError("jwt_public_key_path is not configured")

        valid, claims, err = verify_subscription_token(token, cfg.jwt_public_key_path)
        if not valid:
            raise PermissionError(err)

        user_id = str(claims.get("sub") or claims.get("username") or "").strip()
        if not user_id:
            raise PermissionError("token missing subject")

        policy = store.get_policy(user_id)
        return user_id, build_effective_subscription_scope(claims, policy)

    @app.before_request
    def check_auth():
        if request.path in ("/health", "/stats", "/"):
            return None

        auth = request.headers.get("Authorization", "")
        bearer = auth[7:].strip() if auth.startswith("Bearer ") else auth.strip()

        if request.path == "/api/v1/rt-kline/push":
            expected = cfg.push_token or cfg.token
            if expected:
                if not bearer:
                    return jsonify({"status": "error", "code": 401, "message": "missing Authorization header"}), 401
                if bearer != expected:
                    return jsonify({"status": "error", "code": 403, "message": "invalid push token"}), 403
            return None

        if request.path == "/api/v1/rt-kline/policies/apply":
            if cfg.policy_token:
                if not bearer:
                    return jsonify({"status": "error", "code": 401, "message": "missing Authorization header"}), 401
                if bearer != cfg.policy_token:
                    return jsonify({"status": "error", "code": 403, "message": "invalid policy token"}), 403
            return None

        return None

    @app.route("/api/v1/rt-kline/push", methods=["POST"])
    def receive_push():
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
        except Exception as exc:
            logger.error("Receive push error: %s", exc, exc_info=True)
            return jsonify({
                "status": "retryable",
                "code": 500,
                "ack_seq": 0,
                "accepted_count": 0,
                "rejected_count": 0,
            }), 500

    @app.route("/api/v1/rt-kline/latest", methods=["GET"])
    def query_latest():
        market = request.args.get("market")
        ts_code = request.args.get("ts_code")
        limit = int(request.args.get("limit", 100))
        return jsonify(store.get_latest(market=market, ts_code=ts_code, limit=limit)), 200

    @app.route("/api/v1/rt-kline/policies/apply", methods=["POST"])
    def apply_policies():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "code": 400, "message": "payload must be a JSON object"}), 400
        applied = store.apply_policies(payload)
        return jsonify({"status": "ok", "code": 0, "applied": applied}), 200

    @app.route("/api/v1/rt-kline/subscription/sync", methods=["POST"])
    def sync_subscription_symbols():
        try:
            user_id, effective_scope = authenticate_subscription_request()
        except ValueError as exc:
            return jsonify({"status": "error", "code": 500, "message": str(exc)}), 500
        except PermissionError as exc:
            return jsonify({"status": "error", "code": 401, "message": str(exc)}), 401

        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"status": "error", "code": 400, "message": "payload must be a JSON object"}), 400

        mode = str(payload.get("mode", "replace") or "replace").strip().lower()
        if mode not in {"replace", "add", "remove"}:
            return jsonify({"status": "error", "code": 400, "message": "mode must be replace, add, or remove"}), 400

        raw_symbols = payload.get("symbols", [])
        if not isinstance(raw_symbols, list):
            return jsonify({"status": "error", "code": 400, "message": "symbols must be an array"}), 400

        result = store.sync_user_subscriptions(user_id, raw_symbols, effective_scope, mode=mode)
        result.update({"status": "ok", "code": 0})
        return jsonify(result), 200

    @app.route("/api/v1/rt-kline/subscription/list", methods=["GET"])
    def list_subscription_symbols():
        try:
            user_id, effective_scope = authenticate_subscription_request()
        except ValueError as exc:
            return jsonify({"status": "error", "code": 500, "message": str(exc)}), 500
        except PermissionError as exc:
            return jsonify({"status": "error", "code": 401, "message": str(exc)}), 401

        stored_symbols = store.get_user_subscriptions(user_id)
        effective_symbols, rejected = validate_subscription_symbols(stored_symbols, effective_scope)
        return jsonify(
            {
                "status": "ok",
                "code": 0,
                "user_id": user_id,
                "revision": effective_scope.get("revision", 0),
                "max_subs": effective_scope.get("max_subs", 0),
                "stored_count": len(stored_symbols),
                "current_subscriptions": len(effective_symbols),
                "subscribed_symbols": effective_symbols,
                "rejected_symbols": rejected,
            }
        ), 200

    @app.route("/api/v1/rt-kline/subscription/latest", methods=["GET"])
    def query_subscription_latest():
        try:
            user_id, effective_scope = authenticate_subscription_request()
        except ValueError as exc:
            return jsonify({"status": "error", "code": 500, "message": str(exc)}), 500
        except PermissionError as exc:
            return jsonify({"status": "error", "code": 401, "message": str(exc)}), 401

        stored_symbols = store.get_user_subscriptions(user_id)
        requested_raw = request.args.get("symbols", "")
        rejected: List[Dict[str, str]] = []

        if requested_raw.strip():
            try:
                requested_symbols = parse_symbol_list(requested_raw)
            except ValueError as exc:
                return jsonify({"status": "error", "code": 400, "message": str(exc)}), 400
            stored_set = set(stored_symbols)
            symbols = []
            for symbol in requested_symbols:
                if symbol in stored_set:
                    symbols.append(symbol)
                else:
                    rejected.append({"symbol": symbol, "reason": "not_subscribed"})
        else:
            symbols = stored_symbols

        allowed_symbols, policy_rejected = validate_subscription_symbols(symbols, effective_scope)
        rejected.extend(policy_rejected)
        result = store.get_subscription_snapshot(allowed_symbols, cfg.subscription_step_seconds)
        result.update({
            "status": "ok",
            "code": 0,
            "user_id": user_id,
            "revision": effective_scope.get("revision", 0),
            "max_subs": effective_scope.get("max_subs", 0),
            "registered_symbols": stored_symbols,
            "accepted_symbols": allowed_symbols,
            "rejected_symbols": rejected,
        })
        return jsonify(result), 200

    @app.route("/stats", methods=["GET"])
    def get_stats():
        return jsonify(store.get_stats()), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "timestamp": utc_now_iso()}), 200

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "push-data-receiver",
            "version": "2.0.0",
            "storage": {
                "spool_dir": str(store._spool_dir),
                "sqlite_path": str(store._db_path),
                "flush_interval_seconds": cfg.flush_interval_seconds,
                "flush_max_items": cfg.flush_max_items,
            },
            "endpoints": {
                "POST /api/v1/rt-kline/push": "接收推送数据并追加写入 spool",
                "POST /api/v1/rt-kline/policies/apply": "接收实时订阅 policy 快照",
                "POST /api/v1/rt-kline/subscription/sync": "按 JWT + policy 同步当前用户的批量订阅清单",
                "GET  /api/v1/rt-kline/subscription/list": "查看当前用户已登记的订阅 symbols",
                "GET  /api/v1/rt-kline/latest": "从 SQLite 快照查询最新行情（?market=&ts_code=&limit=）",
                "GET  /api/v1/rt-kline/subscription/latest": "按 JWT + 已登记订阅查询最新快照（可选 ?symbols=000001.SZ,600519.SH）",
                "GET  /stats": "查看 spool / SQLite 刷盘状态",
                "GET  /health": "健康检查",
            },
        }), 200

    return app


def build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Receive push data with spool append-only ingest and SQLite snapshot queries."
    )
    parser.add_argument("--host", default="0.0.0.0", help="监听地址（默认 0.0.0.0）")
    parser.add_argument("--port", type=int, default=9100, help="监听端口（默认 9100）")
    parser.add_argument("--token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""), help="兼容旧参数，等同 --push-token")
    parser.add_argument("--push-token", default=os.getenv("RT_KLINE_CLOUD_PUSH_TOKEN", ""), help="Push 写入 Bearer Token（为空则 push 接口不鉴权）")
    parser.add_argument("--policy-token", default=os.getenv("RT_STOCK_POLICY_TOKEN", ""), help="接收 policy 快照的 Bearer Token")
    parser.add_argument("--jwt-public-key-path", default=os.getenv("RT_STOCK_JWT_PUBLIC_KEY_PATH", ""), help="实时订阅 JWT 公钥路径")
    parser.add_argument("--data-dir", default="data/received_push", help="数据目录（默认 data/received_push）")
    parser.add_argument("--spool-dir", default=os.getenv("RT_KLINE_SPOOL_DIR", ""), help="spool 追加写目录，默认 <data-dir>/spool")
    parser.add_argument("--snapshot-dir", default=os.getenv("RT_KLINE_SNAPSHOT_DIR", ""), help="SQLite/CSV 快照目录，默认 <data-dir>/snapshot")
    parser.add_argument("--sqlite-path", default=os.getenv("RT_KLINE_SQLITE_PATH", ""), help="SQLite 快照文件路径，默认 <snapshot-dir>/rt_snapshot.db")
    parser.add_argument("--save-csv", action="store_true", help="每次刷盘后导出市场级最新快照 CSV")
    parser.add_argument("--flush-interval-seconds", type=int, default=3, help="builder 批量刷 SQLite 的时间间隔，默认 3 秒")
    parser.add_argument("--flush-max-items", type=int, default=2000, help="单次 builder 最多处理的 spool 记录数，默认 2000")
    parser.add_argument("--subscription-step-seconds", type=int, default=3, help="订阅查询返回的时间步长，默认 3 秒")
    parser.add_argument("--log-level", default="INFO", help="日志级别: DEBUG/INFO/WARNING/ERROR")
    parser.add_argument("--debug", action="store_true", help="Flask debug 模式（开发用）")
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
        push_token=(args.push_token or args.token).strip(),
        policy_token=args.policy_token.strip(),
        jwt_public_key_path=args.jwt_public_key_path.strip(),
        data_dir=args.data_dir,
        spool_dir=args.spool_dir,
        snapshot_dir=args.snapshot_dir,
        sqlite_path=args.sqlite_path,
        save_csv=args.save_csv,
        flush_interval_seconds=max(1, int(args.flush_interval_seconds)),
        flush_max_items=max(100, int(args.flush_max_items)),
        subscription_step_seconds=max(1, int(args.subscription_step_seconds)),
        log_level=args.log_level,
        debug=args.debug,
    )

    print(f"""
╔══════════════════════════════════════════════════╗
║      Push Data Receiver + SQLite Snapshot       ║
╠══════════════════════════════════════════════════╣
║  Listen      : {cfg.host}:{cfg.port:<27s}║
║  Push URL    : /api/v1/rt-kline/push            ║
║  Policy API  : /api/v1/rt-kline/policies/apply  ║
║  Skills API  : /api/v1/rt-kline/subscription/latest║
║  Data Dir    : {cfg.data_dir:<31s}║
║  Flush Every : {str(cfg.flush_interval_seconds) + 's':<31s}║
╚══════════════════════════════════════════════════╝
""")

    app = create_app(cfg)
    app.run(host=cfg.host, port=cfg.port, debug=cfg.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())