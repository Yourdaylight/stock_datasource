"""Open API Gateway admin router — /api/open-api-admin/*

All endpoints require admin authentication.
"""

import logging

from fastapi import APIRouter, Depends, Query

from stock_datasource.modules.auth.dependencies import require_admin

from .schemas import (
    BatchToggleRequest,
    EndpointInfo,
    EndpointListResponse,
    MessageResponse,
    PolicyInfo,
    PolicyListResponse,
    UpdatePolicyRequest,
    UsageStatItem,
    UsageStatsResponse,
)
from .service import get_open_api_service

logger = logging.getLogger(__name__)

admin_router = APIRouter()


# ------------------------------------------------------------------
# Policy management
# ------------------------------------------------------------------


@admin_router.get("/policies", response_model=PolicyListResponse)
async def list_policies(
    _admin: dict = Depends(require_admin),
):
    """List all access policies."""
    svc = get_open_api_service()
    policies = svc.get_all_policies()
    return PolicyListResponse(
        policies=[PolicyInfo(**p) for p in policies],
        total=len(policies),
    )


@admin_router.put("/policies/{api_path:path}", response_model=MessageResponse)
async def update_policy(
    api_path: str,
    body: UpdatePolicyRequest,
    _admin: dict = Depends(require_admin),
):
    """Update access policy for a specific api_path."""
    svc = get_open_api_service()
    ok, msg = svc.upsert_policy(
        api_path=api_path,
        is_enabled=body.is_enabled,
        rate_limit_per_min=body.rate_limit_per_min,
        rate_limit_per_day=body.rate_limit_per_day,
        max_records=body.max_records,
        description=body.description,
    )
    return MessageResponse(success=ok, message=msg)


@admin_router.post("/policies/batch-toggle", response_model=MessageResponse)
async def batch_toggle_policies(
    body: BatchToggleRequest,
    _admin: dict = Depends(require_admin),
):
    """Batch enable/disable multiple policies."""
    svc = get_open_api_service()
    ok, msg = svc.batch_toggle(body.api_paths, body.is_enabled)
    return MessageResponse(success=ok, message=msg)


@admin_router.post("/policies/sync", response_model=MessageResponse)
async def sync_policies(
    _admin: dict = Depends(require_admin),
):
    """Discover plugin endpoints and create default policies for new ones.

    Existing policies are not overwritten.
    New endpoints default to disabled (safe).
    """
    svc = get_open_api_service()
    created, existing = svc.sync_policies_from_plugins()
    return MessageResponse(
        success=True,
        message=f"同步完成: 新增 {created} 个策略，已有 {existing} 个",
    )


# ------------------------------------------------------------------
# Endpoint discovery
# ------------------------------------------------------------------


@admin_router.get("/endpoints", response_model=EndpointListResponse)
async def list_endpoints(
    _admin: dict = Depends(require_admin),
):
    """Discover all available plugin endpoints (with their policy status)."""
    svc = get_open_api_service()
    endpoints = svc.discover_endpoints()
    result = []
    for ep in endpoints:
        policy = svc.get_policy(ep["api_path"])
        is_enabled = bool(policy and policy.get("is_enabled"))
        result.append(
            EndpointInfo(
                plugin_name=ep["plugin_name"],
                method_name=ep["method_name"],
                api_path=ep["api_path"],
                description=ep.get("description", ""),
                parameters=ep.get("parameters", []),
                is_enabled=is_enabled,
            )
        )
    return EndpointListResponse(endpoints=result, total=len(result))


# ------------------------------------------------------------------
# Usage statistics
# ------------------------------------------------------------------


@admin_router.get("/usage", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = Query(7, ge=1, le=365),
    api_path: str | None = Query(None),
    api_key_id: str | None = Query(None),
    _admin: dict = Depends(require_admin),
):
    """Get aggregated usage statistics."""
    svc = get_open_api_service()
    stats = svc.get_usage_stats(days=days, api_path=api_path, api_key_id=api_key_id)
    total_calls = sum(s["total_calls"] for s in stats)
    return UsageStatsResponse(
        stats=[UsageStatItem(**s) for s in stats],
        period=f"最近 {days} 天",
        total_calls=total_calls,
    )
