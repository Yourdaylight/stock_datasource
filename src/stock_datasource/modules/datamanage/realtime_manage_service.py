"""Realtime data management service.

Provides centralized control for all realtime plugins (tushare_rt_*),
including global on/off switch, per-plugin enable/disable, and
watchlist monitoring integration.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from stock_datasource.config.runtime_config import (
    get_realtime_config,
    save_realtime_config,
    get_realtime_plugin_config,
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


def _get_plugin_config_data(config_path: Path) -> Dict[str, Any]:
    """Read a plugin's config.json."""
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


class RealtimeManageService:
    """Service for managing realtime data plugins and watchlist integration."""

    _instance: Optional["RealtimeManageService"] = None

    def __new__(cls) -> "RealtimeManageService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._plugins_dir = (
            Path(__file__).parent.parent.parent / "plugins"
        )

    # ---- Config CRUD ----

    def get_config(self) -> Dict[str, Any]:
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
        enabled: Optional[bool] = None,
        watchlist_monitor_enabled: Optional[bool] = None,
        collect_freq: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update global realtime configuration.

        When enabling realtime, also enables watchlist monitoring by default.
        When disabling, also disables watchlist monitoring.
        Controls the APScheduler collection job via pause/resume.
        """
        if collect_freq and collect_freq.upper() not in VALID_FREQS:
            raise ValueError(f"Invalid freq: {collect_freq}. Valid: {VALID_FREQS}")

        kwargs: Dict[str, Any] = {}
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

    def update_plugin_config(self, plugin_name: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a specific realtime plugin."""
        save_realtime_plugin_config(plugin_name, enabled)
        logger.info(f"Realtime plugin '{plugin_name}' {'enabled' if enabled else 'disabled'}")
        return self.get_config()

    # ---- Plugin discovery ----

    def get_realtime_plugins(self) -> List[Dict[str, Any]]:
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
            plugins.append({
                "plugin_name": cfg.get("plugin_name", plugin_dir.name),
                "display_name": cfg.get("display_name", plugin_dir.name),
                "description": cfg.get("description", ""),
                "api_name": cfg.get("api_name", ""),
                "category": cfg.get("category", ""),
                "tags": cfg.get("tags", []),
                "enabled": rt_pc.get("enabled", False),
            })

        return plugins

    @staticmethod
    def is_realtime_plugin(plugin_name: str) -> bool:
        """Check if a plugin is a realtime plugin by reading its config."""
        plugins_dir = Path(__file__).parent.parent.parent / "plugins"
        config_path = plugins_dir / plugin_name / "config.json"
        return _is_realtime_plugin(config_path)

    # ---- Watchlist integration ----

    def get_watchlist_codes(self) -> List[str]:
        """Read watchlist codes from memory agent store."""
        try:
            from stock_datasource.agents.memory_agent import _memory_store
            watchlist = _memory_store.get("watchlist", {})
            codes: List[str] = []
            for group_codes in watchlist.values():
                codes.extend(c for c in group_codes if c not in codes)
            return codes
        except Exception as e:
            logger.warning(f"Failed to read watchlist: {e}")
            return []

    def _sync_watchlist_to_collector(self) -> None:
        """Sync watchlist codes to the realtime_minute collector's in-memory config."""
        cfg = get_realtime_config()
        if not cfg.get("watchlist_monitor_enabled"):
            return

        codes = self.get_watchlist_codes()
        if not codes:
            logger.info("No watchlist codes to sync")
            return

        logger.info(f"Syncing {len(codes)} watchlist codes to realtime collector memory")
        try:
            from stock_datasource.modules.realtime_minute import config as rt_cfg

            # Merge watchlist codes into ASTOCK_BATCHES (avoid duplicates)
            existing_codes = set()
            for batch in rt_cfg.ASTOCK_BATCHES:
                existing_codes.update(batch)

            new_codes = [c for c in codes if c not in existing_codes and c.endswith(('.SH', '.SZ'))]
            if new_codes:
                # Add as a new batch
                batch_size = 100
                for i in range(0, len(new_codes), batch_size):
                    rt_cfg.ASTOCK_BATCHES.append(new_codes[i:i + batch_size])
                logger.info(f"Injected {len(new_codes)} watchlist codes into ASTOCK_BATCHES")
            else:
                logger.debug("All watchlist codes already in ASTOCK_BATCHES")
        except Exception as e:
            logger.warning(f"Failed to inject watchlist codes: {e}")

    def get_realtime_status(self) -> Dict[str, Any]:
        """Get current realtime system status summary."""
        cfg = self.get_config()
        plugins = self.get_realtime_plugins()
        enabled_count = sum(1 for p in plugins if p.get("enabled"))
        watchlist_codes = self.get_watchlist_codes()

        # Check scheduler state
        collection_paused = True
        try:
            from stock_datasource.modules.realtime_minute.scheduler import is_collection_paused
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
