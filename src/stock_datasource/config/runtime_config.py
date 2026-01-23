"""Runtime configuration persistence for proxy, sync concurrency, and schedule.

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
    "schedule": {
        "enabled": False,
        "execute_time": "18:00",
        "frequency": "weekday",
        "include_optional_deps": True,
        "skip_non_trading_days": True,
        "last_run_at": None,
        "next_run_at": None,
    },
    "plugin_schedules": {},  # plugin_name -> {"schedule_enabled": bool, "full_scan_enabled": bool}
    "schedule_history": [],  # List of ScheduleExecutionRecord dicts
    "plugin_groups": [],     # List of PluginGroup dicts
}

_lock = threading.Lock()


def _read_file() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge defaults to ensure missing keys are filled
            merged = {}
            for key, default_val in DEFAULT_CONFIG.items():
                if isinstance(default_val, dict):
                    merged[key] = {**default_val, **data.get(key, {})}
                else:
                    merged[key] = data.get(key, default_val)
            return merged
    except Exception:
        return {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_CONFIG.items()}


def load_runtime_config() -> Dict[str, Any]:
    """Return runtime config (proxy + sync + schedule) with defaults applied."""
    with _lock:
        return _read_file()


def save_runtime_config(
    proxy: Optional[Dict[str, Any]] = None,
    sync: Optional[Dict[str, Any]] = None,
    schedule: Optional[Dict[str, Any]] = None,
    plugin_schedules: Optional[Dict[str, Any]] = None,
    schedule_history: Optional[list] = None,
) -> Dict[str, Any]:
    """Persist runtime config updates to disk and return merged config."""
    with _lock:
        current = _read_file()
        if proxy is not None:
            current["proxy"].update(proxy)
        if sync is not None:
            current["sync"].update(sync)
        if schedule is not None:
            current["schedule"].update(schedule)
        if plugin_schedules is not None:
            current["plugin_schedules"].update(plugin_schedules)
        if schedule_history is not None:
            current["schedule_history"] = schedule_history
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2, default=str)
        return current


def get_schedule_config() -> Dict[str, Any]:
    """Get schedule configuration."""
    config = load_runtime_config()
    return config.get("schedule", DEFAULT_CONFIG["schedule"].copy())


def get_plugin_schedule_config(plugin_name: str) -> Dict[str, Any]:
    """Get schedule config for a specific plugin."""
    config = load_runtime_config()
    plugin_schedules = config.get("plugin_schedules", {})
    return plugin_schedules.get(plugin_name, {"schedule_enabled": True, "full_scan_enabled": False})


def save_plugin_schedule_config(plugin_name: str, schedule_enabled: bool = None, full_scan_enabled: bool = None) -> Dict[str, Any]:
    """Save schedule config for a specific plugin."""
    config = load_runtime_config()
    plugin_schedules = config.get("plugin_schedules", {})
    
    if plugin_name not in plugin_schedules:
        plugin_schedules[plugin_name] = {"schedule_enabled": True, "full_scan_enabled": False}
    
    if schedule_enabled is not None:
        plugin_schedules[plugin_name]["schedule_enabled"] = schedule_enabled
    if full_scan_enabled is not None:
        plugin_schedules[plugin_name]["full_scan_enabled"] = full_scan_enabled
    
    return save_runtime_config(plugin_schedules=plugin_schedules)


def get_schedule_history(limit: int = 50) -> list:
    """Get schedule execution history."""
    config = load_runtime_config()
    history = config.get("schedule_history", [])
    return history[:limit]


def add_schedule_execution(record: Dict[str, Any]) -> None:
    """Add a schedule execution record to history."""
    config = load_runtime_config()
    history = config.get("schedule_history", [])
    history.insert(0, record)  # Add to beginning
    # Keep only last 100 records
    history = history[:100]
    save_runtime_config(schedule_history=history)


def update_schedule_execution(execution_id: str, updates: Dict[str, Any]) -> None:
    """Update a schedule execution record."""
    config = load_runtime_config()
    history = config.get("schedule_history", [])
    for record in history:
        if record.get("execution_id") == execution_id:
            record.update(updates)
            break
    save_runtime_config(schedule_history=history)


# ============ Plugin Groups Management ============

def get_plugin_groups() -> list:
    """Get all plugin groups."""
    config = load_runtime_config()
    return config.get("plugin_groups", [])


def get_plugin_group(group_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific plugin group by ID."""
    groups = get_plugin_groups()
    for group in groups:
        if group.get("group_id") == group_id:
            return group
    return None


def save_plugin_group(group: Dict[str, Any]) -> None:
    """Save or update a plugin group."""
    config = load_runtime_config()
    groups = config.get("plugin_groups", [])
    
    # Find and update existing or append new
    found = False
    for i, g in enumerate(groups):
        if g.get("group_id") == group.get("group_id"):
            groups[i] = group
            found = True
            break
    
    if not found:
        groups.append(group)
    
    _save_config(config, plugin_groups=groups)


def delete_plugin_group(group_id: str) -> bool:
    """Delete a plugin group by ID. Returns True if deleted."""
    config = load_runtime_config()
    groups = config.get("plugin_groups", [])
    
    initial_len = len(groups)
    groups = [g for g in groups if g.get("group_id") != group_id]
    
    if len(groups) < initial_len:
        _save_config(config, plugin_groups=groups)
        return True
    return False


def _save_config(config: Dict[str, Any], **updates) -> None:
    """Internal helper to save config with updates."""
    with _lock:
        for key, value in updates.items():
            config[key] = value
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2, default=str)
