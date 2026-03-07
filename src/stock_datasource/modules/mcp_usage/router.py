"""MCP tool usage tracking routes."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..auth.dependencies import get_current_user
from .schemas import UsageHistoryResponse, UsageStatsResponse
from .service import McpUsageService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    tool_name: Optional[str] = Query(None, description="Filter by tool name"),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated MCP tool usage history."""
    result = await McpUsageService.get_usage_history(
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        tool_name=tool_name,
    )
    return result


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    """Get aggregated daily MCP usage statistics."""
    result = await McpUsageService.get_usage_stats(
        user_id=current_user["id"],
        days=days,
    )
    return result
