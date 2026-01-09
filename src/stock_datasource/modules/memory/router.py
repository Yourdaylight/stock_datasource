"""Memory module router."""

from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class UserPreference(BaseModel):
    risk_level: str = "moderate"
    investment_style: str = "balanced"
    favorite_sectors: List[str] = []


class WatchlistItem(BaseModel):
    ts_code: str
    stock_name: str
    group_name: str = "default"
    add_reason: str = None
    target_price: float = None
    stop_loss_price: float = None
    created_at: str = None


class AddWatchlistRequest(BaseModel):
    ts_code: str
    group_name: str = "default"
    add_reason: str = None


class InteractionHistory(BaseModel):
    id: str
    intent: str
    user_input: str
    stocks_mentioned: List[str] = []
    timestamp: str


class UserProfile(BaseModel):
    active_level: str = "medium"
    expertise_level: str = "intermediate"
    focus_industries: List[str] = []
    focus_stocks: List[str] = []
    trading_style: str = "balanced"


@router.get("/preference", response_model=UserPreference)
async def get_preference():
    """Get user preference."""
    return UserPreference()


@router.put("/preference")
async def update_preference(data: UserPreference):
    """Update user preference."""
    return {"success": True}


@router.get("/watchlist", response_model=List[WatchlistItem])
async def get_watchlist(group: Optional[str] = None):
    """Get user watchlist."""
    return [
        WatchlistItem(ts_code="600519.SH", stock_name="贵州茅台", group_name="default", created_at="2024-01-01"),
        WatchlistItem(ts_code="000858.SZ", stock_name="五粮液", group_name="default", created_at="2024-01-02"),
    ]


@router.post("/watchlist")
async def add_to_watchlist(request: AddWatchlistRequest):
    """Add stock to watchlist."""
    return {"success": True}


@router.delete("/watchlist/{ts_code}")
async def remove_from_watchlist(ts_code: str):
    """Remove stock from watchlist."""
    return {"success": True}


@router.get("/history", response_model=List[InteractionHistory])
async def get_history(limit: int = Query(default=20)):
    """Get interaction history."""
    return []


@router.get("/profile", response_model=UserProfile)
async def get_profile():
    """Get user profile."""
    return UserProfile(
        focus_industries=["科技", "消费"],
        focus_stocks=["600519.SH", "000858.SZ"]
    )
