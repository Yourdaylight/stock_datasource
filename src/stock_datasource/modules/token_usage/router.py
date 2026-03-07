"""Token usage API routes."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query

from ..auth.dependencies import get_current_user
from .service import TokenUsageService
from .schemas import TokenBalance, UsageHistoryResponse, UsageStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/balance", response_model=TokenBalance)
async def get_balance(current_user: dict = Depends(get_current_user)):
    """Get current user's token balance."""
    balance = await TokenUsageService.get_balance(current_user["id"])
    return balance


@router.get("/history", response_model=UsageHistoryResponse)
async def get_usage_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """Get paginated token usage history."""
    result = await TokenUsageService.get_usage_history(
        user_id=current_user["id"],
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
    )
    return result


@router.get("/stats", response_model=UsageStatsResponse)
async def get_usage_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    """Get aggregated daily usage statistics."""
    result = await TokenUsageService.get_usage_stats(
        user_id=current_user["id"],
        days=days,
    )
    return result
