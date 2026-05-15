"""FastAPI router for the sentinel system."""

import logging
from typing import Any

from fastapi import APIRouter, Query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sentinel"])


@router.post("/scan")
async def trigger_scan() -> dict[str, Any]:
    """Manually trigger a full sentinel scan cycle."""
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()
        result = await registry.run_scan_cycle()
        return {
            "status": "ok",
            "message": "Scan cycle completed",
            "result": result,
        }
    except Exception as e:
        logger.error("Manual scan trigger failed: %s", e, exc_info=True)
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Get sentinel system status."""
    try:
        from .core.registry import get_sentinel_registry

        registry = get_sentinel_registry()
        status = registry.get_status()
        return {
            "status": "ok",
            "data": status,
        }
    except Exception as e:
        logger.error("Failed to get status: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": {
                "is_running": False,
                "sentinels_active": 0,
                "analysts_active": 0,
            },
        }


@router.get("/decisions")
async def get_decisions(
    limit: int = Query(default=10, ge=1, le=50, description="Number of recent decisions"),
) -> dict[str, Any]:
    """Get recent investment decisions."""
    try:
        from .persistence.store import get_sentinel_store

        store = get_sentinel_store()
        decisions = store.get_recent_decisions(limit=limit)
        return {
            "status": "ok",
            "count": len(decisions),
            "data": decisions,
        }
    except Exception as e:
        logger.error("Failed to get decisions: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(default=50, ge=1, le=200, description="Number of recent alerts"),
    sentinel_type: str | None = Query(default=None, description="Filter by sentinel type"),
) -> dict[str, Any]:
    """Get recent sentinel alerts."""
    try:
        from .persistence.store import get_sentinel_store

        store = get_sentinel_store()
        alerts = store.get_recent_alerts(limit=limit, sentinel_type=sentinel_type)
        return {
            "status": "ok",
            "count": len(alerts),
            "data": alerts,
        }
    except Exception as e:
        logger.error("Failed to get alerts: %s", e)
        return {
            "status": "error",
            "message": str(e),
            "data": [],
        }
