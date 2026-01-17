"""Pydantic schemas for authentication module."""

from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserRegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码，至少6位")
    username: Optional[str] = Field(None, max_length=50, description="用户名（可选，默认使用邮箱前缀）")


class UserLoginRequest(BaseModel):
    """User login request."""
    email: EmailStr = Field(..., description="用户邮箱")
    password: str = Field(..., description="密码")


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
    created_at: datetime = Field(..., description="创建时间")


class RegisterResponse(BaseModel):
    """Registration response."""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="提示信息")
    user: Optional[UserResponse] = Field(None, description="用户信息")


class WhitelistEmailRequest(BaseModel):
    """Add email to whitelist request."""
    email: EmailStr = Field(..., description="要添加的邮箱")


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
