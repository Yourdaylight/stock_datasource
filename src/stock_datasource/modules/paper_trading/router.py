"""Paper Trading API Router"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user
from .schemas import (
    AccountSummary,
    CreateAccountRequest,
    EquityPoint,
    PerformanceMetrics,
    Position,
    TradeRecord,
)
from .service import PaperTradingService

logger = logging.getLogger(__name__)
router = APIRouter()

_service: PaperTradingService | None = None


def get_service() -> PaperTradingService:
    global _service
    if _service is None:
        _service = PaperTradingService()
    return _service


@router.post("/accounts", response_model=AccountSummary)
async def create_account(
    request: CreateAccountRequest,
    current_user: dict = Depends(get_current_user),
):
    """创建模拟账户"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.create_account(user_id, request)


@router.get("/accounts", response_model=list[AccountSummary])
async def list_accounts(
    current_user: dict = Depends(get_current_user),
):
    """列出所有模拟账户"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_accounts(user_id)


@router.get("/accounts/{account_id}", response_model=AccountSummary)
async def get_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取账户详情"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    account = await service.get_account(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    return account


@router.get("/accounts/{account_id}/positions", response_model=list[Position])
async def get_positions(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取持仓列表"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_positions(user_id, account_id)


@router.get("/accounts/{account_id}/trades", response_model=list[TradeRecord])
async def get_trades(
    account_id: str,
    days: int = Query(default=30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
):
    """获取交易记录"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_trades(user_id, account_id, days)


@router.get("/accounts/{account_id}/performance", response_model=PerformanceMetrics)
async def get_performance(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取绩效指标"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_performance(user_id, account_id)


@router.get("/accounts/{account_id}/equity-curve", response_model=list[EquityPoint])
async def get_equity_curve(
    account_id: str,
    days: int = Query(default=90, ge=7, le=365),
    current_user: dict = Depends(get_current_user),
):
    """获取净值曲线"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_equity_curve(user_id, account_id, days)


@router.post("/accounts/{account_id}/pause")
async def pause_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """暂停账户"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    account = await service.get_account(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    await service.update_account_status(user_id, account_id, "paused")
    return {"message": "账户已暂停", "account_id": account_id}


@router.post("/accounts/{account_id}/resume")
async def resume_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
):
    """恢复账户"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    account = await service.get_account(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="账户不存在")
    await service.update_account_status(user_id, account_id, "active")
    return {"message": "账户已恢复", "account_id": account_id}
