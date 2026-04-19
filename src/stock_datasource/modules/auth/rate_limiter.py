"""Redis-based sliding window rate limiter for API requests.

Uses sorted sets to implement a sliding window counter per user.
"""

import logging
import time

from fastapi import Depends, HTTPException, status

from .dependencies import get_current_user
from .service import TIER_RATE_LIMITS

logger = logging.getLogger(__name__)


def _get_redis():
    """Get Redis client (lazy import to avoid circular deps)."""
    try:
        from stock_datasource.services.cache_service import CacheService

        cache = CacheService()
        return cache._redis  # noqa: SLF001 — internal access for rate limiting
    except Exception:
        return None


async def check_rate_limit(user_id: str, tier: str) -> bool:
    """Check if the user is within their rate limit.

    Uses a Redis sorted set with timestamps as scores.
    Returns True if allowed, False if rate limited.
    """
    redis = _get_redis()
    if redis is None:
        # Redis unavailable — allow request (fail open)
        return True

    max_requests, window_seconds = TIER_RATE_LIMITS.get(
        tier, TIER_RATE_LIMITS["free"]
    )

    key = f"rate_limit:{user_id}"
    now = time.time()
    window_start = now - window_seconds

    try:
        pipe = redis.pipeline()
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count remaining entries in window
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {f"{now}:{id(now)}": now})
        # Set TTL to auto-cleanup
        pipe.expire(key, window_seconds + 10)
        results = pipe.execute()

        current_count = results[1]
        return current_count < max_requests
    except Exception as e:
        logger.warning(f"Rate limit check failed for {user_id}: {e}")
        return True  # Fail open


async def rate_limit_guard(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI dependency that enforces rate limiting.

    Use on resource-intensive endpoints (chat, AI analysis).
    Returns the current_user dict if allowed.
    Raises HTTP 429 if rate limited.
    """
    tier = current_user.get("subscription_tier", "free")

    # Admin users bypass rate limiting
    if tier == "admin":
        return current_user

    allowed = await check_rate_limit(current_user["id"], tier)
    if not allowed:
        max_requests, window = TIER_RATE_LIMITS.get(tier, TIER_RATE_LIMITS["free"])
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"请求频率超限，当前等级({tier})限制 {max_requests}次/{window}秒",
            headers={"Retry-After": str(window)},
        )

    return current_user
