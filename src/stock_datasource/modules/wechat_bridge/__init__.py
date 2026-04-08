"""WeChat Bridge module for picoclash integration."""

from fastapi import APIRouter

from .router import router as wechat_bridge_router

__all__ = ["router", "wechat_bridge_router"]
