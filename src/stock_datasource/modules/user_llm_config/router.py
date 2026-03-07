"""User LLM configuration API routes."""

import logging
from fastapi import APIRouter, Depends, HTTPException

from ..auth.dependencies import get_current_user
from .service import UserLlmConfigService
from .schemas import (
    LlmConfigCreate,
    LlmConfigResponse,
    LlmConfigListResponse,
    LlmConfigTestRequest,
    LlmConfigTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/configs", response_model=LlmConfigListResponse)
async def get_llm_configs(current_user: dict = Depends(get_current_user)):
    """Get current user's LLM configurations."""
    configs = await UserLlmConfigService.get_configs(current_user["id"])
    return {"configs": configs}


@router.post("/configs", response_model=LlmConfigResponse)
async def save_llm_config(
    body: LlmConfigCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create or update a LLM configuration."""
    try:
        result = await UserLlmConfigService.save_config(
            user_id=current_user["id"],
            provider=body.provider,
            api_key=body.api_key,
            base_url=body.base_url or "",
            model_name=body.model_name or "",
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/configs/{provider}")
async def delete_llm_config(
    provider: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a LLM configuration."""
    ok = await UserLlmConfigService.delete_config(current_user["id"], provider)
    if not ok:
        raise HTTPException(status_code=500, detail="删除失败")
    return {"success": True}


@router.post("/test", response_model=LlmConfigTestResponse)
async def test_llm_config(
    body: LlmConfigTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Test an LLM configuration by making a simple API call."""
    result = await UserLlmConfigService.test_config(
        api_key=body.api_key,
        base_url=body.base_url or "",
        model_name=body.model_name or "",
        provider=body.provider,
    )
    return result
