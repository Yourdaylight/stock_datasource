"""Pydantic schemas for MCP usage tracking."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UsageRecord(BaseModel):
    id: str
    user_id: str
    api_key_id: str = ""
    tool_name: str
    service_prefix: str = ""
    table_name: str = ""
    arguments: str = ""
    record_count: int = 0
    duration_ms: int = 0
    is_error: bool = False
    error_message: str = ""
    created_at: datetime


class UsageHistoryResponse(BaseModel):
    records: List[UsageRecord]
    total: int
    page: int
    page_size: int


class DailyStat(BaseModel):
    date: str
    call_count: int
    total_records: int


class TopTool(BaseModel):
    tool_name: str
    table_name: str = ""
    call_count: int
    total_records: int


class UsageStatsResponse(BaseModel):
    daily_stats: List[DailyStat]
    total_calls: int
    total_records: int
    avg_daily_calls: float
    top_tools: List[TopTool]
