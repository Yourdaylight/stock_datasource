"""Memory module router - 真实读写MemoryStore.

API端点:
- /preference - 用户偏好读写
- /watchlist - 自选股管理
- /history - 交互历史
- /profile - 用户画像
- /facts - Memory Facts CRUD
- /conclusions - 历史结论查询
"""

import hashlib
import logging
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from .models import FactCategory, FactItem
from .store import MemoryStore, get_memory_store

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class UserPreference(BaseModel):
    risk_level: str = "moderate"
    investment_style: str = "balanced"
    favorite_sectors: list[str] = []


class WatchlistItem(BaseModel):
    ts_code: str
    stock_name: str = ""
    group_name: str = "default"
    add_reason: str | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    created_at: str | None = None


class AddWatchlistRequest(BaseModel):
    ts_code: str
    group_name: str = "default"
    add_reason: str | None = None


class InteractionHistory(BaseModel):
    id: str
    intent: str
    user_input: str
    stocks_mentioned: list[str] = []
    timestamp: str


class UserProfile(BaseModel):
    active_level: str = "medium"
    expertise_level: str = "intermediate"
    focus_industries: list[str] = []
    focus_stocks: list[str] = []
    trading_style: str = "balanced"


class FactInput(BaseModel):
    content: str
    category: FactCategory = "conclusion"
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source: str = ""


class FactOutput(BaseModel):
    id: str
    content: str
    category: FactCategory
    confidence: float
    source: str = ""
    created_at: float = 0
    reinforced_at: list[float] = []
    contradicted_at: list[float] = []


class ConclusionOutput(BaseModel):
    id: str
    data: dict[str, Any]
    stored_at: float = 0


def _get_store() -> MemoryStore:
    return get_memory_store()


def _content_hash(content: str) -> str:
    """Deterministic short hash for fact ID suffix.

    Uses MD5 instead of Python's hash() because hash() is randomized
    across processes (PYTHONHASHSEED), making IDs unstable for delete.
    """
    return hashlib.md5(content.encode()).hexdigest()[:8]


def _fact_to_output(fact_id: str, fact: FactItem) -> FactOutput:
    return FactOutput(
        id=fact_id,
        content=fact.content,
        category=fact.category,
        confidence=fact.confidence,
        source=fact.source,
        created_at=fact.created_at,
        reinforced_at=fact.reinforced_at,
        contradicted_at=fact.contradicted_at,
    )


# ---------------------------------------------------------------------------
# Preference API
# ---------------------------------------------------------------------------


@router.get("/preference", response_model=UserPreference)
async def get_preference(current_user: dict = Depends(get_current_user)):
    """Get user preference from MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    profile = store.get_profile(user_id)

    return UserPreference(
        risk_level=profile.get("risk_level", "moderate"),
        investment_style=profile.get("investment_style", "balanced"),
        favorite_sectors=profile.get("favorite_sectors", []),
    )


@router.put("/preference")
async def update_preference(data: UserPreference, current_user: dict = Depends(get_current_user)):
    """Update user preference in MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    store.put_profile_entry(user_id, "risk_level", data.risk_level)
    store.put_profile_entry(user_id, "investment_style", data.investment_style)
    store.put_profile_entry(user_id, "favorite_sectors", data.favorite_sectors)
    return {"success": True}


# ---------------------------------------------------------------------------
# Watchlist API
# ---------------------------------------------------------------------------


@router.get("/watchlist", response_model=list[WatchlistItem])
async def get_watchlist(group: str | None = None, current_user: dict = Depends(get_current_user)):
    """Get user watchlist from MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    facts = store.search_facts(user_id, limit=50, min_confidence=0.5)

    watchlist_items = []
    for fact in facts:
        if fact.category == "stock_opinion" and ("关注" in fact.content or "持有" in fact.content):
            code_match = re.search(r"(\d{6}\.[A-Z]{2})", fact.content)
            if code_match:
                watchlist_items.append(
                    WatchlistItem(
                        ts_code=code_match.group(1),
                        stock_name="",
                        group_name="default",
                        add_reason=fact.content[:100],
                        created_at=time.strftime("%Y-%m-%d", time.localtime(fact.created_at)),
                    )
                )

    # Filter by group if specified
    if group:
        watchlist_items = [w for w in watchlist_items if w.group_name == group]

    return watchlist_items[:20]


@router.post("/watchlist")
async def add_to_watchlist(request: AddWatchlistRequest, current_user: dict = Depends(get_current_user)):
    """Add stock to watchlist (creates a stock_opinion fact)."""
    user_id = current_user["id"]
    store = _get_store()
    fact = FactItem(
        content=f"关注股票 {request.ts_code}" + (f"，原因: {request.add_reason}" if request.add_reason else ""),
        category="stock_opinion",
        confidence=0.8,
        source="watchlist",
    )
    fact_id = f"wl_{int(time.time() * 1000)}_{_content_hash(fact.content)}"
    store.put_fact(user_id, fact_id, fact)
    return {"success": True}


@router.delete("/watchlist/{ts_code}")
async def remove_from_watchlist(ts_code: str, current_user: dict = Depends(get_current_user)):
    """Remove stock from watchlist (delete matching facts)."""
    user_id = current_user["id"]
    store = _get_store()
    facts = store.search_facts(user_id, limit=50)
    for fact in facts:
        if ts_code in fact.content and fact.category == "stock_opinion":
            # Find the fact_id by matching content - approximate
            fact_id = f"wl_{int(fact.created_at * 1000)}_{_content_hash(fact.content)}"
            store.delete_fact(user_id, fact_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# History API
# ---------------------------------------------------------------------------


@router.get("/history", response_model=list[InteractionHistory])
async def get_history(limit: int = Query(default=20), current_user: dict = Depends(get_current_user)):
    """Get interaction history from MemoryStore conclusions."""
    user_id = current_user["id"]
    store = _get_store()
    conclusions = store.search_conclusions(user_id, limit=limit)

    history_items = []
    for i, c in enumerate(conclusions):
        history_items.append(
            InteractionHistory(
                id=f"hist_{i}",
                intent=c.get("intent", "unknown"),
                user_input=c.get("user_message", "")[:200],
                stocks_mentioned=c.get("stocks", []),
                timestamp=time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.localtime(c.get("stored_at", time.time())),
                ),
            )
        )
    return history_items


# ---------------------------------------------------------------------------
# Profile API
# ---------------------------------------------------------------------------


@router.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile from MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    profile = store.get_profile(user_id)

    # Build profile from facts if profile entries are sparse
    facts = store.search_facts(user_id, limit=20)

    focus_industries = profile.get("focus_industries", [])
    focus_stocks = profile.get("focus_stocks", [])
    trading_style = profile.get("trading_style", "balanced")

    # Extract from facts
    for fact in facts:
        if fact.category == "sector_focus" and fact.confidence >= 0.7:
            focus_industries.append(fact.content[:20])
        if fact.category == "stock_opinion" and fact.confidence >= 0.7:
            code_match = re.search(r"(\d{6}\.[A-Z]{2})", fact.content)
            if code_match:
                focus_stocks.append(code_match.group(1))
        if fact.category == "trading_style":
            trading_style = fact.content[:20]

    return UserProfile(
        active_level=profile.get("active_level", "medium"),
        expertise_level=profile.get("expertise_level", "intermediate"),
        focus_industries=focus_industries[:10],
        focus_stocks=focus_stocks[:10],
        trading_style=trading_style,
    )


# ---------------------------------------------------------------------------
# Facts API (NEW)
# ---------------------------------------------------------------------------


@router.get("/facts", response_model=list[FactOutput])
async def get_facts(
    category: FactCategory | None = None,
    limit: int = Query(default=15, ge=1, le=50),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0),
    current_user: dict = Depends(get_current_user),
):
    """Get user facts from MemoryStore, optionally filtered by category."""
    user_id = current_user["id"]
    store = _get_store()
    facts = store.search_facts(user_id, limit=limit, min_confidence=min_confidence)

    if category:
        facts = [f for f in facts if f.category == category]

    # Generate stable IDs for facts
    result = []
    for fact in facts:
        fact_id = f"fact_{int(fact.created_at * 1000)}_{_content_hash(fact.content)}"
        result.append(_fact_to_output(fact_id, fact))

    return result


@router.post("/facts", response_model=FactOutput)
async def create_fact(input_data: FactInput, current_user: dict = Depends(get_current_user)):
    """Manually create a fact in MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    fact = FactItem(
        content=input_data.content,
        category=input_data.category,
        confidence=input_data.confidence,
        source=input_data.source or "manual",
    )
    fact_id = f"fact_{int(time.time() * 1000)}_{_content_hash(fact.content)}"
    store.put_fact(user_id, fact_id, fact)
    return _fact_to_output(fact_id, fact)


@router.delete("/facts/{fact_id}")
async def delete_fact(fact_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a fact from MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    store.delete_fact(user_id, fact_id)
    return {"success": True}


# ---------------------------------------------------------------------------
# Conclusions API (NEW)
# ---------------------------------------------------------------------------


@router.get("/conclusions", response_model=list[ConclusionOutput])
async def get_conclusions(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """Get historical analysis conclusions from MemoryStore."""
    user_id = current_user["id"]
    store = _get_store()
    conclusions = store.search_conclusions(user_id, limit=limit)

    result = []
    for i, c in enumerate(conclusions):
        result.append(
            ConclusionOutput(
                id=f"concl_{i}",
                data=c,
                stored_at=c.get("stored_at", 0),
            )
        )
    return result
