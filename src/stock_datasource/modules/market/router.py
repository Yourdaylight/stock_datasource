"""Market module router."""

from fastapi import APIRouter, Query
from typing import List
import logging

from .schemas import (
    KLineRequest,
    KLineResponse,
    IndicatorRequest,
    IndicatorResponse,
    StockSearchResult
)
from .service import get_market_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/kline", response_model=KLineResponse)
async def get_kline(request: KLineRequest):
    """Get K-line data for a stock."""
    service = get_market_service()
    result = await service.get_kline(
        code=request.code,
        start_date=request.start_date,
        end_date=request.end_date,
        adjust=request.adjust
    )
    return KLineResponse(**result)


@router.post("/indicators", response_model=IndicatorResponse)
async def get_indicators(request: IndicatorRequest):
    """Get technical indicators for a stock."""
    service = get_market_service()
    result = await service.get_indicators(
        code=request.code,
        indicators=request.indicators,
        period=request.period
    )
    return IndicatorResponse(**result)


@router.get("/search", response_model=List[StockSearchResult])
async def search_stock(keyword: str = Query(..., description="Search keyword")):
    """Search stocks by keyword."""
    service = get_market_service()
    results = await service.search_stock(keyword)
    return [StockSearchResult(**r) for r in results]
