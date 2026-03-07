"""MCP API Key management routes."""

import logging
from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from .schemas import (
    CreateApiKeyRequest,
    CreateApiKeyResponse,
    ApiKeyListResponse,
    ApiKeyInfo,
    RevokeApiKeyRequest,
    MessageResponse,
)
from .service import get_mcp_api_key_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/create", response_model=CreateApiKeyResponse)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new MCP API Key. The full key is returned only once."""
    service = get_mcp_api_key_service()
    success, message, info = service.create_api_key(
        user_id=current_user["id"],
        key_name=request.key_name,
        expires_days=request.expires_days,
    )
    return CreateApiKeyResponse(
        success=success,
        message=message,
        api_key=info.get("api_key"),
        key_id=info.get("key_id"),
        key_name=info.get("key_name", ""),
        api_key_prefix=info.get("api_key_prefix", ""),
        created_at=info.get("created_at"),
        expires_at=info.get("expires_at"),
    )


@router.get("/list", response_model=ApiKeyListResponse)
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
):
    """List all active MCP API Keys for the current user."""
    service = get_mcp_api_key_service()
    keys = service.list_api_keys(current_user["id"])
    return ApiKeyListResponse(
        keys=[ApiKeyInfo(**k) for k in keys],
        total=len(keys),
    )


@router.post("/revoke", response_model=MessageResponse)
async def revoke_api_key(
    request: RevokeApiKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Revoke an MCP API Key."""
    service = get_mcp_api_key_service()
    success, message = service.revoke_api_key(current_user["id"], request.key_id)
    return MessageResponse(success=success, message=message)
