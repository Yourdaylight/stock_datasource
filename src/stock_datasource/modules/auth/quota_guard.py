"""Token quota guard — blocks requests when user's token balance is exhausted.

Use as a FastAPI dependency on AI-consuming endpoints (chat, sentiment analysis, agents).
NOT needed on pure data query endpoints (news list, market data).
"""

import logging

from fastapi import Depends, HTTPException, status

from .dependencies import get_current_user

logger = logging.getLogger(__name__)


async def require_quota(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """FastAPI dependency that checks token balance before allowing AI requests.

    - Admin users bypass quota checks.
    - Returns the current_user dict if quota is available.
    - Raises HTTP 403 if quota is exhausted.
    """
    tier = current_user.get("subscription_tier", "free")

    # Admin bypass
    if tier == "admin":
        return current_user

    try:
        from stock_datasource.modules.token_usage.service import TokenUsageService

        balance = await TokenUsageService.get_balance(current_user["id"])

        if balance.get("remaining_tokens", 0) <= 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token 配额已用完，请联系管理员升级账户等级",
                headers={"X-Quota-Exhausted": "true"},
            )

        return current_user
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Quota check failed for {current_user['id']}: {e}")
        # Fail open — don't block users if quota service is down
        return current_user
