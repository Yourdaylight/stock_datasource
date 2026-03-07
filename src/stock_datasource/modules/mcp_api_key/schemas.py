"""Pydantic schemas for MCP API Key management."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class CreateApiKeyRequest(BaseModel):
    key_name: str = Field("", max_length=100, description="API Key 名称/标签")
    expires_days: Optional[int] = Field(None, ge=1, le=365, description="过期天数 (null=永不过期)")


class CreateApiKeyResponse(BaseModel):
    success: bool
    message: str
    api_key: Optional[str] = None
    key_id: Optional[str] = None
    key_name: str = ""
    api_key_prefix: str = ""
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ApiKeyInfo(BaseModel):
    id: str
    key_name: str = ""
    api_key_prefix: str = ""
    is_active: bool = True
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime


class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyInfo]
    total: int


class RevokeApiKeyRequest(BaseModel):
    key_id: str = Field(..., description="要撤销的 API Key ID")


class MessageResponse(BaseModel):
    success: bool
    message: str
