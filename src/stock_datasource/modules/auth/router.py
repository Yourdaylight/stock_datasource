"""Authentication API routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status

from .schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    RegisterResponse,
    WhitelistEmailRequest,
    WhitelistEmailResponse,
    MessageResponse,
)
from .service import AuthService, get_auth_service
from .dependencies import get_current_user

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, summary="用户注册")
async def register(
    request: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户注册接口。
    
    - 邮箱必须在白名单中才能注册
    - 密码至少6位
    - 用户名可选，默认使用邮箱前缀
    """
    success, message, user = auth_service.register_user(
        email=request.email,
        password=request.password,
        username=request.username,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    
    return RegisterResponse(
        success=True,
        message=message,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            username=user["username"],
            is_active=user["is_active"],
            created_at=user["created_at"],
        ),
    )


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(
    request: UserLoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户登录接口。
    
    - 使用邮箱和密码登录
    - 返回 JWT Token，有效期 7 天
    """
    success, message, token_info = auth_service.login_user(
        email=request.email,
        password=request.password,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=message,
        )
    
    return TokenResponse(
        access_token=token_info["access_token"],
        token_type=token_info["token_type"],
        expires_in=token_info["expires_in"],
    )


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    """
    获取当前登录用户的信息。
    
    需要在请求头中携带 Authorization: Bearer <token>
    """
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )


@router.post("/logout", response_model=MessageResponse, summary="退出登录")
async def logout(
    current_user: dict = Depends(get_current_user),
):
    """
    退出登录。
    
    由于使用 JWT，服务端无需处理，前端清除本地 Token 即可。
    """
    return MessageResponse(
        success=True,
        message="退出登录成功",
    )


@router.get("/whitelist", response_model=List[WhitelistEmailResponse], summary="获取邮箱白名单")
async def get_whitelist(
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    获取邮箱白名单列表。
    
    需要登录认证。
    """
    entries = auth_service.get_whitelist(limit=limit, offset=offset)
    
    return [
        WhitelistEmailResponse(
            id=entry["id"],
            email=entry["email"],
            added_by=entry["added_by"],
            is_active=entry["is_active"],
            created_at=entry["created_at"],
        )
        for entry in entries
    ]


@router.post("/whitelist", response_model=WhitelistEmailResponse, summary="添加邮箱到白名单")
async def add_to_whitelist(
    request: WhitelistEmailRequest,
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    添加邮箱到白名单。
    
    需要登录认证。
    """
    success, message, entry = auth_service.add_email_to_whitelist(
        email=request.email,
        added_by=current_user["email"],
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )
    
    return WhitelistEmailResponse(
        id=entry["id"],
        email=entry["email"],
        added_by=entry["added_by"],
        is_active=entry["is_active"],
        created_at=entry["created_at"],
    )
