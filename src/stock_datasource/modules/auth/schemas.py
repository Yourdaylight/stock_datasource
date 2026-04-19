"""Pydantic schemas for authentication module."""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, TypeAdapter, field_validator

LOCAL_EMAIL_PATTERN = re.compile(r"^[^@\s]+@localhost$", re.IGNORECASE)
EMAIL_ADAPTER = TypeAdapter(EmailStr)


def _normalize_auth_email(value: str) -> str:
    """Allow standard emails and the seeded local admin address."""
    email = value.strip().lower()
    if LOCAL_EMAIL_PATTERN.match(email):
        return email
    return str(EMAIL_ADAPTER.validate_python(email))


class UserRegisterRequest(BaseModel):
    """User registration request."""

    email: str = Field(..., description="用户邮箱")
    password: str = Field(
        ..., min_length=6, max_length=128, description="密码，至少6位"
    )
    username: str | None = Field(
        None, max_length=50, description="用户名（可选，默认使用邮箱前缀）"
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_auth_email(value)


class UserLoginRequest(BaseModel):
    """User login request."""

    email: str = Field(..., description="用户邮箱")
    password: str = Field(..., description="密码")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_auth_email(value)


class TokenResponse(BaseModel):
    """Token response after login."""

    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class UserResponse(BaseModel):
    """User information response."""

    id: str = Field(..., description="用户ID")
    email: str = Field(..., description="用户邮箱")
    username: str = Field(..., description="用户名")
    is_active: bool = Field(..., description="是否激活")
    is_admin: bool = Field(default=False, description="是否管理员")
    subscription_tier: str = Field(default="free", description="订阅等级: free/pro/admin")
    created_at: datetime = Field(..., description="创建时间")


class RegisterResponse(BaseModel):
    """Registration response."""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    user: UserResponse | None = Field(None, description="用户信息")


class WhitelistEmailRequest(BaseModel):
    """Add email to whitelist request."""

    email: str = Field(..., description="要添加的邮箱")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _normalize_auth_email(value)


class WhitelistEmailResponse(BaseModel):
    """Whitelist email response."""

    id: str = Field(..., description="记录ID")
    email: str = Field(..., description="邮箱")
    added_by: str = Field(..., description="添加者")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")


class MessageResponse(BaseModel):
    """Generic message response."""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
