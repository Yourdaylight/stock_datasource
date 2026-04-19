"""Signal Aggregator router - 信号聚合API路由."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth.dependencies import get_current_user

from .schemas import (
    SignalAggregationResponse,
    SignalTimelineResponse,
    SignalWeightsConfig,
    StockSignalSummary,
)
from .service import SignalAggregator, get_signal_aggregator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/aggregate", response_model=SignalAggregationResponse)
async def aggregate_signals(
    ts_codes: str = Query(..., description="逗号分隔的股票代码, 如 600519.SH,000858.SZ"),
    signal_date: str | None = Query(None, description="信号日期 YYYYMMDD, 默认今天"),
    current_user: dict = Depends(get_current_user),
):
    """获取多只股票的信号聚合评分."""
    codes = [c.strip().upper() for c in ts_codes.split(",") if c.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="请提供至少一个股票代码")
    if len(codes) > 20:
        raise HTTPException(status_code=400, detail="一次最多查询20只股票")

    aggregator = get_signal_aggregator()
    return await aggregator.aggregate_for_stocks(codes, signal_date)


@router.get("/aggregate/{ts_code}", response_model=StockSignalSummary)
async def aggregate_single_stock(
    ts_code: str,
    signal_date: str | None = Query(None, description="信号日期 YYYYMMDD, 默认今天"),
    current_user: dict = Depends(get_current_user),
):
    """获取单只股票的信号聚合评分."""
    aggregator = get_signal_aggregator()
    result = await aggregator.aggregate_for_stock(ts_code.upper(), signal_date)
    if result is None:
        raise HTTPException(status_code=404, detail=f"无法为 {ts_code} 生成信号评分")

    return StockSignalSummary(
        ts_code=result.ts_code,
        stock_name=result.stock_name,
        composite_score=result.composite_score,
        composite_direction=result.composite_direction,
        news_score=result.news_score.score,
        capital_score=result.capital_score.score,
        tech_score=result.tech_score.score,
        news_detail=result.news_score.detail,
        capital_detail=result.capital_score.detail,
        tech_detail=result.tech_score.detail,
        signal_date=result.signal_date,
    )


@router.get("/timeline/{ts_code}", response_model=SignalTimelineResponse)
async def get_signal_timeline(
    ts_code: str,
    days: int = Query(30, ge=1, le=365, description="回溯天数"),
    current_user: dict = Depends(get_current_user),
):
    """获取某只股票的信号时序追踪数据."""
    aggregator = get_signal_aggregator()
    return await aggregator.get_signal_timeline(ts_code.upper(), days)


@router.put("/weights")
async def update_weights(config: SignalWeightsConfig, current_user: dict = Depends(get_current_user)):
    """更新信号权重配置(运行时)."""
    aggregator = get_signal_aggregator(config)
    return {"success": True, "weights": config.model_dump()}
