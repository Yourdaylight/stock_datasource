"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from .dependencies import get_current_user, require_admin
from .schemas import (
    MessageResponse,
    RegisterResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    WhitelistEmailRequest,
    WhitelistEmailResponse,
)
from .service import AuthService, get_auth_service

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, summary="用户注册")
async def register(
    request: UserRegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """
    用户注册接口。

    - 默认不启用邮箱白名单校验；当开启开关时，邮箱必须在白名单中才能注册
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
            is_admin=user.get("is_admin", False),
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
        is_admin=current_user.get("is_admin", False),
        subscription_tier=current_user.get("subscription_tier", "free"),
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


@router.get(
    "/whitelist", response_model=list[WhitelistEmailResponse], summary="获取邮箱白名单"
)
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


@router.post(
    "/whitelist", response_model=WhitelistEmailResponse, summary="添加邮箱到白名单"
)
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


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/users", summary="获取用户列表（管理员）")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """获取所有用户列表。仅管理员。"""
    auth_service._ensure_tables()
    query = """
        SELECT id, email, username, is_active, is_admin, subscription_tier, created_at
        FROM users FINAL
        WHERE is_active = 1
        ORDER BY created_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """
    result = auth_service.client.execute(query, {"limit": limit, "offset": offset})
    return [
        {
            "id": row[0],
            "email": row[1],
            "username": row[2],
            "is_active": bool(row[3]),
            "is_admin": bool(row[4]),
            "subscription_tier": row[5] if len(row) > 5 else "free",
            "created_at": row[6] if len(row) > 6 else None,
        }
        for row in result
    ]


@router.put("/admin/users/{user_id}/tier", summary="修改用户等级（管理员）")
async def update_user_tier(
    user_id: str,
    tier: str,
    current_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """修改用户的订阅等级。仅管理员。"""
    from .service import TIER_QUOTAS, get_tier_quota

    if tier not in TIER_QUOTAS:
        raise HTTPException(400, f"无效的等级: {tier}，可选: {list(TIER_QUOTAS.keys())}")

    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    # Update tier in ClickHouse (insert new version for ReplacingMergeTree)
    from datetime import datetime
    auth_service.client.execute(
        "INSERT INTO users (id, email, username, password_hash, is_active, is_admin, subscription_tier, created_at, updated_at) "
        "VALUES (%(id)s, %(email)s, %(username)s, %(password_hash)s, %(is_active)s, %(is_admin)s, %(tier)s, %(created_at)s, %(updated_at)s)",
        {
            "id": user["id"],
            "email": user["email"],
            "username": user["username"],
            "password_hash": user["password_hash"],
            "is_active": 1 if user["is_active"] else 0,
            "is_admin": 1 if user["is_admin"] else 0,
            "tier": tier,
            "created_at": user["created_at"],
            "updated_at": datetime.now(),
        },
    )

    return {"success": True, "message": f"用户 {user['email']} 等级已更新为 {tier}"}


@router.post("/admin/users/{user_id}/reset-quota", summary="重置用户配额（管理员）")
async def reset_user_quota(
    user_id: str,
    quota: int | None = None,
    current_user: dict = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
):
    """重置用户的 token 配额。仅管理员。"""
    from .service import get_tier_quota

    user = auth_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "用户不存在")

    tier = user.get("subscription_tier", "free")
    new_quota = quota if quota is not None else get_tier_quota(tier)

    try:
        from stock_datasource.modules.token_usage.service import TokenUsageService
        await TokenUsageService.initialize_quota(user_id, new_quota)
        return {"success": True, "message": f"用户 {user['email']} 配额已重置为 {new_quota}"}
    except Exception as e:
        raise HTTPException(500, f"重置配额失败: {e}")
