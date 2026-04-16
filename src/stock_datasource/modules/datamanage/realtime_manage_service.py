"""Realtime data management service.

Provides centralized control for all realtime plugins (tushare_rt_*),
including global on/off switch, per-plugin enable/disable, and
watchlist monitoring integration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from stock_datasource.config.runtime_config import (
    get_realtime_config,
    get_realtime_plugin_config,
    save_realtime_config,
    save_realtime_plugin_config,
)

logger = logging.getLogger(__name__)

# Valid collect frequencies
VALID_FREQS = ["1MIN", "5MIN", "15MIN", "30MIN", "60MIN"]


def _is_realtime_plugin(config_path: Path) -> bool:
    """Check if a plugin config.json marks it as realtime."""
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("update_schedule") == "realtime"
    except Exception:
        return False


def _get_plugin_config_data(config_path: Path) -> dict[str, Any]:
    """Read a plugin's config.json."""
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class RealtimeManageService:
    """Service for managing realtime data plugins and watchlist integration."""

    _instance: RealtimeManageService | None = None

    def __new__(cls) -> RealtimeManageService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._plugins_dir = Path(__file__).parent.parent.parent / "plugins"

    # ---- Config CRUD ----

    def get_config(self) -> dict[str, Any]:
        """Get full realtime configuration."""
        cfg = get_realtime_config()
        # Ensure all realtime plugins have an entry in plugin_configs
        plugins = self.get_realtime_plugins()
        pc = cfg.setdefault("plugin_configs", {})
        for p in plugins:
            name = p["plugin_name"]
            if name not in pc:
                pc[name] = {"enabled": False}
        return cfg

    def update_config(
        self,
        enabled: bool | None = None,
        watchlist_monitor_enabled: bool | None = None,
        collect_freq: str | None = None,
    ) -> dict[str, Any]:
        """Update global realtime configuration.

        When enabling realtime, also enables watchlist monitoring by default.
        When disabling, also disables watchlist monitoring.
        Controls the APScheduler collection job via pause/resume.
        """
        if collect_freq and collect_freq.upper() not in VALID_FREQS:
            raise ValueError(f"Invalid freq: {collect_freq}. Valid: {VALID_FREQS}")

        kwargs: dict[str, Any] = {}
        if enabled is not None:
            kwargs["enabled"] = enabled
            # Auto-link watchlist monitoring
            if enabled and watchlist_monitor_enabled is None:
                kwargs["watchlist_monitor_enabled"] = True
            elif not enabled and watchlist_monitor_enabled is None:
                kwargs["watchlist_monitor_enabled"] = False
        if watchlist_monitor_enabled is not None:
            kwargs["watchlist_monitor_enabled"] = watchlist_monitor_enabled
        if collect_freq is not None:
            kwargs["collect_freq"] = collect_freq.upper()

        rt = save_realtime_config(**kwargs)

        # ---- Link to APScheduler collection job ----
        if enabled is not None:
            self._toggle_collection(enabled)

        if kwargs.get("enabled") or kwargs.get("watchlist_monitor_enabled"):
            self._sync_watchlist_to_collector()

        logger.info(f"Realtime config updated: {kwargs}")
        return rt

    @staticmethod
    def _toggle_collection(enabled: bool) -> None:
        """Pause or resume the realtime minute collection APScheduler job."""
        try:
            from stock_datasource.modules.realtime_minute.scheduler import (
                pause_collection,
                resume_collection,
            )

            if enabled:
                resume_collection()
            else:
                pause_collection()
        except Exception as e:
            logger.warning(f"Failed to toggle collection job: {e}")

    def update_plugin_config(self, plugin_name: str, enabled: bool) -> dict[str, Any]:
        """Enable or disable a specific realtime plugin."""
        save_realtime_plugin_config(plugin_name, enabled)
        logger.info(
            f"Realtime plugin '{plugin_name}' {'enabled' if enabled else 'disabled'}"
        )
        return self.get_config()

    # ---- Plugin discovery ----

    def get_realtime_plugins(self) -> list[dict[str, Any]]:
        """Discover all realtime plugins by scanning plugin directories."""
        plugins = []
        if not self._plugins_dir.exists():
            return plugins

        for plugin_dir in sorted(self._plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            config_path = plugin_dir / "config.json"
            if not config_path.exists():
                continue
            if not _is_realtime_plugin(config_path):
                continue

            cfg = _get_plugin_config_data(config_path)
            rt_pc = get_realtime_plugin_config(cfg.get("plugin_name", plugin_dir.name))
            plugins.append(
                {
                    "plugin_name": cfg.get("plugin_name", plugin_dir.name),
                    "display_name": cfg.get("display_name", plugin_dir.name),
                    "description": cfg.get("description", ""),
                    "api_name": cfg.get("api_name", ""),
                    "category": cfg.get("category", ""),
                    "tags": cfg.get("tags", []),
                    "enabled": rt_pc.get("enabled", False),
                }
            )

        return plugins

    @staticmethod
    def is_realtime_plugin(plugin_name: str) -> bool:
        """Check if a plugin is a realtime plugin by reading its config."""
        plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        config_path = plugins_dir / plugin_name / "config.json"
        return _is_realtime_plugin(config_path)

    # ---- Watchlist integration ----

    def get_watchlist_codes(self) -> list[str]:
        """Read watchlist codes from user portfolio positions + memory store.

        Priority:
        1. user_positions table (ClickHouse) — the user's actual holdings
        2. MemoryStore watchlist — user-added watchlist codes
        """
        codes: list[str] = []

        # 1. From user_positions (actual holdings)
        try:
            from stock_datasource.models.database import db_client

            query = "SELECT DISTINCT ts_code FROM user_positions"
            df = db_client.execute_query(query)
            if not df.empty:
                codes.extend(df["ts_code"].tolist())
        except Exception as e:
            logger.warning(f"Failed to read watchlist from user_positions: {e}")

        # 2. From MemoryStore watchlist (user-added codes)
        try:
            from stock_datasource.modules.memory.store import get_memory_store

            store = get_memory_store()
            # Search across all users for watchlist entries
            results = store.raw_store.search(("users",), limit=200)
            for item in results:
                if item.value and isinstance(item.value, dict):
                    # Check if this looks like a watchlist entry
                    if item.key == "watchlist" and isinstance(item.value, dict):
                        for group_codes in item.value.values():
                            if isinstance(group_codes, list):
                                for c in group_codes:
                                    if c not in codes:
                                        codes.append(c)
        except Exception as e:
            logger.warning(f"Failed to read watchlist from MemoryStore: {e}")

        return codes

    def _sync_watchlist_to_collector(self) -> None:
        """Sync watchlist codes (from portfolio positions + memory) to the realtime_minute collector's in-memory config."""
        cfg = get_realtime_config()
        if not cfg.get("watchlist_monitor_enabled"):
            return

        codes = self.get_watchlist_codes()
        if not codes:
            logger.info("No watchlist/position codes to sync")
            return

        logger.info(
            f"Syncing {len(codes)} watchlist/position codes to realtime collector memory"
        )
        try:
            from stock_datasource.modules.realtime_minute import config as rt_cfg

            # All A-share/ETF/index codes go to ASTOCK_BATCHES (same rt_min API)
            # HK codes go to HK_CODES
            cn_new = [c for c in codes if not c.endswith(".HK")]
            hk_new = [c for c in codes if c.endswith(".HK")]

            # Merge into ASTOCK_BATCHES
            existing_cn = set()
            for batch in rt_cfg.ASTOCK_BATCHES:
                existing_cn.update(batch)
            # Also exclude codes already in HOT_ETF_CODES or INDEX_CODES
            existing_cn.update(rt_cfg.HOT_ETF_CODES)
            existing_cn.update(rt_cfg.INDEX_CODES)
            new_cn = [c for c in cn_new if c not in existing_cn]
            if new_cn:
                batch_size = 100
                for i in range(0, len(new_cn), batch_size):
                    rt_cfg.ASTOCK_BATCHES.append(new_cn[i : i + batch_size])
                logger.info(f"Injected {len(new_cn)} CN codes into ASTOCK_BATCHES")

            # Merge into HK_CODES
            existing_hk = set(rt_cfg.HK_CODES)
            new_hk = [c for c in hk_new if c not in existing_hk]
            if new_hk:
                rt_cfg.HK_CODES.extend(new_hk)
                logger.info(f"Injected {len(new_hk)} HK codes into HK_CODES")

        except Exception as e:
            logger.warning(f"Failed to inject watchlist codes: {e}")

    def get_realtime_status(self) -> dict[str, Any]:
        """Get current realtime system status summary."""
        cfg = self.get_config()
        plugins = self.get_realtime_plugins()
        enabled_count = sum(1 for p in plugins if p.get("enabled"))
        watchlist_codes = self.get_watchlist_codes()

        # Check scheduler state
        collection_paused = True
        try:
            from stock_datasource.modules.realtime_minute.scheduler import (
                is_collection_paused,
            )

            collection_paused = is_collection_paused()
        except Exception:
            pass

        return {
            "global_enabled": cfg.get("enabled", False),
            "watchlist_monitor_enabled": cfg.get("watchlist_monitor_enabled", False),
            "collect_freq": cfg.get("collect_freq", "1MIN"),
            "total_plugins": len(plugins),
            "enabled_plugins": enabled_count,
            "watchlist_count": len(watchlist_codes),
            "watchlist_codes": watchlist_codes[:20],  # Return first 20 for display
            "collection_active": not collection_paused,
        }


# Singleton instance
realtime_manage_service = RealtimeManageService()
