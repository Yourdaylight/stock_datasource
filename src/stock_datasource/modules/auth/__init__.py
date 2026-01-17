"""Authentication module for user registration and login."""

from .router import router
from .service import AuthService
from .dependencies import get_current_user, get_current_user_optional

__all__ = ["router", "AuthService", "get_current_user", "get_current_user_optional"]
