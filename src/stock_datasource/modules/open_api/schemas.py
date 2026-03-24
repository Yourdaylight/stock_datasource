"""Pydantic schemas for Open API Gateway."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- Open API response ----

class OpenApiResponse(BaseModel):
    """Unified response for open API calls."""
    status: str = "success"
    data: Any = None
    message: Optional[str] = None
    record_count: int = 0
    truncated: bool = False


# ---- Access policy schemas ----

class PolicyInfo(BaseModel):
    """Access policy info returned to admin."""
    policy_id: str
    api_path: str
    api_type: str = "http"
    is_enabled: bool = False
    rate_limit_per_min: int = 60
    rate_limit_per_day: int = 10000
    max_records: int = 5000
    description: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PolicyListResponse(BaseModel):
    policies: List[PolicyInfo]
    total: int


class UpdatePolicyRequest(BaseModel):
    is_enabled: Optional[bool] = None
    rate_limit_per_min: Optional[int] = Field(None, ge=1, le=100000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=10000000)
    max_records: Optional[int] = Field(None, ge=100, le=1000000)
    description: Optional[str] = None


class BatchToggleRequest(BaseModel):
    """Batch enable/disable multiple policies."""
    api_paths: List[str] = Field(..., min_length=1)
    is_enabled: bool


# ---- Discoverable endpoints ----

class EndpointInfo(BaseModel):
    """Info about a discoverable plugin endpoint."""
    plugin_name: str
    method_name: str
    api_path: str
    description: str = ""
    parameters: List[Dict[str, Any]] = []
    is_enabled: bool = False
    curl_example: str = ""


class EndpointListResponse(BaseModel):
    endpoints: List[EndpointInfo]
    total: int


# ---- Usage stats ----

class UsageStatItem(BaseModel):
    api_path: str
    total_calls: int = 0
    success_calls: int = 0
    error_calls: int = 0
    avg_response_ms: float = 0
    total_records: int = 0


class UsageStatsResponse(BaseModel):
    stats: List[UsageStatItem]
    period: str = ""
    total_calls: int = 0


class MessageResponse(BaseModel):
    success: bool
    message: str
