"""Pydantic schemas for token usage module."""

from datetime import datetime

from pydantic import BaseModel


class TokenBalance(BaseModel):
    """User's token balance info."""

    user_id: str
    total_quota: int = 1000000
    used_tokens: int = 0
    remaining_tokens: int = 1000000
    usage_percent: float = 0.0


class UsageRecord(BaseModel):
    """Single token usage log entry."""

    id: str
    user_id: str
    session_id: str = ""
    message_id: str = ""
    agent_name: str = ""
    model_name: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    created_at: datetime
    session_title: str | None = None


class UsageHistoryResponse(BaseModel):
    """Paginated usage history response."""

    records: list[UsageRecord]
    total: int
    page: int
    page_size: int


class DailyUsageStat(BaseModel):
    """Daily aggregated usage statistics."""

    date: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageStatsResponse(BaseModel):
    """Usage statistics response."""

    daily_stats: list[DailyUsageStat]
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    avg_daily_tokens: float = 0.0
