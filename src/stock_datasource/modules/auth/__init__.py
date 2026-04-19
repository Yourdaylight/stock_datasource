"""Authentication module for user registration and login."""

from .dependencies import get_current_user, get_current_user_optional
from .router import router
from .service import AuthService

__all__ = ["AuthService", "get_current_user", "get_current_user_optional", "router"]
