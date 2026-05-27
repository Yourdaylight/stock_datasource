"""Timing API Router — 择时服务接口"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user
from .schemas import (
    PipelineResult,
    RegimeResponse,
    RunPipelineRequest,
    SignalItem,
    TimingHistoryItem,
)
from .service import TimingService

logger = logging.getLogger(__name__)
router = APIRouter()

_service: TimingService | None = None


def get_service() -> TimingService:
    global _service
    if _service is None:
        _service = TimingService()
    return _service


@router.post("/run", response_model=PipelineResult)
async def run_pipeline(
    request: RunPipelineRequest,
    current_user: dict = Depends(get_current_user),
):
    """手动触发今日择时 pipeline"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()

    watchlist = request.watchlist if request.watchlist else None

    result = await service.run_daily_pipeline(
        user_id, request.account_id, watchlist
    )
    return result


@router.get("/regime", response_model=RegimeResponse)
async def get_regime(
    current_user: dict = Depends(get_current_user),
):
    """获取当前市场状态"""
    service = get_service()
    regime = await service.get_current_regime()

    return RegimeResponse(
        regime=regime.regime,
        position_level=regime.position_level,
        confidence=regime.confidence,
        reason=regime.reason,
        signal_date=regime.signal_date,
        indicators=regime.indicators,
    )


@router.get("/signals", response_model=list[SignalItem])
async def get_signals(
    account_id: str = Query(..., description="模拟盘账户ID"),
    current_user: dict = Depends(get_current_user),
):
    """获取最新择时信号（不执行交易）"""
    user_id = current_user.get("user_id", current_user.get("sub", "anonymous"))
    service = get_service()
    return await service.get_latest_signals(user_id, account_id)


@router.get("/history", response_model=list[TimingHistoryItem])
async def get_history(
    days: int = Query(default=30, ge=7, le=180),
    current_user: dict = Depends(get_current_user),
):
    """获取历史 regime 变化记录"""
    service = get_service()
    return await service.get_regime_history(days)
