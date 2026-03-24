"""Authentication dependencies for Open API Gateway.

Reuses MCP API Key (sk-xxx) validation. Supports:
- Header: Authorization: Bearer sk-xxx
- Query:  ?api_key=sk-xxx
"""

import logging
import time
from collections import defaultdict
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# HTTP Bearer (auto_error=False so we can fall back to query param)
_bearer_scheme = HTTPBearer(auto_error=False)


async def _extract_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    api_key: Optional[str] = Query(None, alias="api_key", include_in_schema=False),
) -> str:
    """Extract API key from header or query parameter.

    Priority: Authorization header > query param.
    """
    raw_key: Optional[str] = None

    if credentials and credentials.credentials:
        raw_key = credentials.credentials
    elif api_key:
        raw_key = api_key

    if not raw_key or not raw_key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少有效的 API Key。请在 Header 中添加 Authorization: Bearer sk-xxx 或使用 ?api_key=sk-xxx",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return raw_key


async def require_api_key(
    raw_key: str = Depends(_extract_api_key),
) -> Tuple[dict, str]:
    """Validate API key and return (user_dict, api_key_id).

    Reuses McpApiKeyService.validate_api_key().
    """
    from stock_datasource.modules.mcp_api_key.service import get_mcp_api_key_service

    service = get_mcp_api_key_service()
    is_valid, user, api_key_id = service.validate_api_key(raw_key)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效、已过期或已被撤销",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user, api_key_id


# ---------------------------------------------------------------------------
# In-process sliding-window rate limiter
# ---------------------------------------------------------------------------

class _SlidingWindowRateLimiter:
    """Simple in-process sliding-window rate limiter.

    Keyed by (api_key_id, api_path). Tracks per-minute and per-day windows.
    For multi-instance deployments, replace with Redis-backed implementation.
    """

    def __init__(self):
        # {key: [timestamp, ...]}
        self._minute_windows: dict[str, list[float]] = defaultdict(list)
        self._day_windows: dict[str, list[float]] = defaultdict(list)

    def check(
        self,
        api_key_id: str,
        api_path: str,
        limit_per_min: int,
        limit_per_day: int,
    ) -> Tuple[bool, str]:
        """Check rate limit. Returns (allowed, error_message)."""
        now = time.time()
        key = f"{api_key_id}:{api_path}"

        # --- per-minute ---
        minute_ago = now - 60
        window = self._minute_windows[key]
        # Prune old entries
        window[:] = [t for t in window if t > minute_ago]
        if len(window) >= limit_per_min:
            return False, f"超过每分钟速率限制 ({limit_per_min}/min)"
        window.append(now)

        # --- per-day ---
        day_ago = now - 86400
        day_window = self._day_windows[key]
        day_window[:] = [t for t in day_window if t > day_ago]
        if len(day_window) >= limit_per_day:
            return False, f"超过每日速率限制 ({limit_per_day}/day)"
        day_window.append(now)

        return True, ""

    def cleanup(self):
        """Remove stale entries (call periodically if needed)."""
        now = time.time()
        day_ago = now - 86400
        for key in list(self._minute_windows.keys()):
            self._minute_windows[key] = [
                t for t in self._minute_windows[key] if t > now - 60
            ]
            if not self._minute_windows[key]:
                del self._minute_windows[key]
        for key in list(self._day_windows.keys()):
            self._day_windows[key] = [
                t for t in self._day_windows[key] if t > day_ago
            ]
            if not self._day_windows[key]:
                del self._day_windows[key]


# Global singleton
rate_limiter = _SlidingWindowRateLimiter()
