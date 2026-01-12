"""Runtime configuration persistence for proxy and sync concurrency.

Stores small JSON file alongside settings to persist user changes
from the admin UI. Safe to import anywhere; IO is guarded with a lock.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import threading

CONFIG_PATH = Path(__file__).parent / "runtime_config.json"
DEFAULT_CONFIG: Dict[str, Any] = {
    "proxy": {
        "enabled": False,
        "host": "",
        "port": 0,
        "username": None,
        "password": None,
    },
    "sync": {
        "max_concurrent_tasks": 1,
        "max_date_threads": 1,
    },
}

_lock = threading.Lock()


def _read_file() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"proxy": DEFAULT_CONFIG["proxy"].copy(), "sync": DEFAULT_CONFIG["sync"].copy()}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge defaults to ensure missing keys are filled
            merged = DEFAULT_CONFIG.copy()
            merged["proxy"] = {**DEFAULT_CONFIG["proxy"], **data.get("proxy", {})}
            merged["sync"] = {**DEFAULT_CONFIG["sync"], **data.get("sync", {})}
            return merged
    except Exception:
        return {"proxy": DEFAULT_CONFIG["proxy"].copy(), "sync": DEFAULT_CONFIG["sync"].copy()}


def load_runtime_config() -> Dict[str, Any]:
    """Return runtime config (proxy + sync) with defaults applied."""
    with _lock:
        return _read_file()


def save_runtime_config(proxy: Optional[Dict[str, Any]] = None, sync: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Persist runtime config updates to disk and return merged config."""
    with _lock:
        current = _read_file()
        if proxy is not None:
            current["proxy"].update(proxy)
        if sync is not None:
            current["sync"].update(sync)
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return current
