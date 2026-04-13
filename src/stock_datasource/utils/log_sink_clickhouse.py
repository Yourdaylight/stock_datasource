"""JSONL → ClickHouse batch importer for structured logs.

Watches the logs directory for rotated `.jsonl.N` files, reads them in
batches, transforms each JSONL record into a ClickHouse row, and bulk-inserts.
On success the source file is deleted; on failure it is kept for the next retry.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from stock_datasource.config.settings import settings

_import_lock = threading.Lock()


def _get_db_client():
    """Lazy import to avoid circular imports at module load time."""
    try:
        from stock_datasource.models.database import db_client
        return db_client
    except Exception:
        return None


def _transform_record(record: dict) -> dict:
    """Transform a Loguru JSON record into a ClickHouse row dict."""
    extra = record.get("extra", {})
    return {
        "timestamp": record.get("timestamp", ""),
        "level": (record.get("level") or "INFO").upper(),
        "request_id": record.get("request_id") or extra.get("request_id", "-"),
        "user_id": record.get("user_id") or extra.get("user_id", "-"),
        "module": record.get("module", ""),
        "function": record.get("function", ""),
        "line": int(record.get("line", 0)),
        "message": record.get("message", ""),
        "exception": record.get("exception") or None,
        "middleware_trace_id": record.get("middleware_trace_id") or extra.get("middleware_trace_id", "-"),
        "extra": json.dumps(extra, ensure_ascii=False, default=str),
    }


def _flush_batch(batch: List[Dict]) -> None:
    """Insert a batch of records into ClickHouse."""
    if not batch:
        return
    db = _get_db_client()
    if db is None:
        return
    try:
        import pandas as pd
        df = pd.DataFrame(batch)
        db.insert_dataframe("system_structured_logs", df)
    except Exception:
        # Non-critical: will retry on next scan
        pass


def _import_file(filepath: Path) -> bool:
    """Read a JSONL file, batch-import into ClickHouse, delete on success.

    Returns True if file was successfully imported (and deleted), False otherwise.
    """
    batch: List[Dict] = []
    batch_size = settings.LOG_CH_SINK_BATCH_SIZE
    imported = 0

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                batch.append(_transform_record(record))
                if len(batch) >= batch_size:
                    _flush_batch(batch)
                    imported += len(batch)
                    batch = []

        # Flush remaining
        if batch:
            _flush_batch(batch)
            imported += len(batch)

        # Delete file on success
        if imported > 0:
            filepath.unlink(missing_ok=True)
        else:
            # Empty or all-malformed file — also delete to avoid reprocessing
            filepath.unlink(missing_ok=True)
        return True

    except Exception:
        return False


def _rotate_active_jsonl(logs_dir: Path) -> Optional[Path]:
    """Rename the active JSONL file into an importable snapshot.

    The logger writes one line at a time and reopens the file per write, so an
    atomic rename is safe and lets the watcher ingest logs without waiting for a
    process restart or an unsupported Loguru rotation callback.
    """
    active_file = logs_dir / "stock_datasource.jsonl"
    if not active_file.exists() or active_file.stat().st_size == 0:
        return None

    rotated_file = logs_dir / (
        f"stock_datasource.jsonl.{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}.jsonl"
    )
    active_file.rename(rotated_file)
    return rotated_file


def import_pending_files(logs_dir: Path) -> int:
    """Scan for pending `.jsonl.N` files and import them.

    Called once at startup to clean up files from previous runs.

    Returns:
        Number of files successfully imported.
    """
    if not logs_dir.exists():
        return 0

    count = 0
    with _import_lock:
        _rotate_active_jsonl(logs_dir)

    for filepath in sorted(logs_dir.glob("*.jsonl.*")):
        with _import_lock:
            if _import_file(filepath):
                count += 1
    return count


def start_ch_sink_watcher(logs_dir: Path, interval: float = 30.0) -> threading.Thread:
    """Start a daemon thread that periodically scans for rotated JSONL files.

    Args:
        logs_dir: Directory containing log files.
        interval: Scan interval in seconds.

    Returns:
        The started daemon thread.
    """
    def _watcher():
        while True:
            try:
                time.sleep(interval)
                import_pending_files(logs_dir)
            except Exception:
                pass  # Keep thread alive

    t = threading.Thread(target=_watcher, daemon=True, name="ch-sink-watcher")
    t.start()
    return t
