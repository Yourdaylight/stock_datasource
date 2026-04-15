"""Profile router — REST API endpoints for portfolio profile management."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class CreateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, description="账户名称")
    broker: str = Field("", max_length=50, description="券商名称")
    is_default: bool = Field(False, description="是否设为默认账户")


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50, description="账户名称")
    broker: Optional[str] = Field(None, max_length=50, description="券商名称")


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    broker: str = ""
    is_default: bool = False


# ---------------------------------------------------------------------------
# Auth dependency — reuse the same pattern as portfolio/router.py
# ---------------------------------------------------------------------------

def _get_auth_dep():
    """Lazy import to avoid circular imports."""
    from stock_datasource.modules.auth.dependencies import get_current_user
    return get_current_user


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/profiles", response_model=list[ProfileResponse], summary="获取账户列表")
async def list_profiles(current_user: dict = Depends(_get_auth_dep())):
    """获取当前用户的所有账户配置。"""
    from .service import get_profile_service

    svc = get_profile_service()
    profiles = svc.list_profiles(user_id=current_user["id"])
    return [ProfileResponse(**p) for p in profiles]


@router.post("/profiles", response_model=ProfileResponse, summary="创建账户")
async def create_profile(
    request: CreateProfileRequest,
    current_user: dict = Depends(_get_auth_dep()),
):
    """创建一个新的证券账户配置。"""
    from .service import get_profile_service

    svc = get_profile_service()
    profile = svc.create_profile(
        user_id=current_user["id"],
        name=request.name,
        broker=request.broker,
        is_default=request.is_default,
    )
    return ProfileResponse(**profile)


@router.get("/profiles/{profile_id}", response_model=ProfileResponse, summary="获取账户详情")
async def get_profile(
    profile_id: str,
    current_user: dict = Depends(_get_auth_dep()),
):
    """获取指定账户配置。"""
    from .service import get_profile_service

    svc = get_profile_service()
    profile = svc.get_profile(profile_id=profile_id, user_id=current_user["id"])
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(**profile)


@router.put("/profiles/{profile_id}", response_model=ProfileResponse, summary="更新账户")
async def update_profile(
    profile_id: str,
    request: UpdateProfileRequest,
    current_user: dict = Depends(_get_auth_dep()),
):
    """更新账户名称或券商信息。"""
    from .service import get_profile_service

    svc = get_profile_service()
    profile = svc.update_profile(
        profile_id=profile_id,
        user_id=current_user["id"],
        name=request.name,
        broker=request.broker,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileResponse(**profile)


@router.delete("/profiles/{profile_id}", summary="删除账户")
async def delete_profile(
    profile_id: str,
    current_user: dict = Depends(_get_auth_dep()),
):
    """删除账户（软删除）。不允许删除默认账户。"""
    from .service import get_profile_service

    svc = get_profile_service()
    success = svc.delete_profile(profile_id=profile_id, user_id=current_user["id"])
    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete profile (default or not found)")
    return {"success": True, "message": "Profile deleted"}
