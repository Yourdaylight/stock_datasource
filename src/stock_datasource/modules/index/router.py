"""FastAPI router for Index module."""

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
import logging

from .service import get_index_service
from .schemas import (
    IndexListResponse,
    IndexInfo,
    ConstituentResponse,
    FactorResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/indices", response_model=IndexListResponse, summary="获取指数列表")
async def get_indices(
    market: Optional[str] = Query(None, description="市场筛选 (SSE/SZSE/CSI)"),
    category: Optional[str] = Query(None, description="类别筛选"),
    keyword: Optional[str] = Query(None, description="名称搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取指数列表，支持分页和筛选。"""
    service = get_index_service()
    result = service.get_indices(
        market=market,
        category=category,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/indices/{ts_code}", response_model=IndexInfo, summary="获取指数详情")
async def get_index_detail(ts_code: str):
    """获取指数详细信息。"""
    service = get_index_service()
    result = service.get_index_detail(ts_code)
    if not result:
        raise HTTPException(status_code=404, detail=f"Index {ts_code} not found")
    return result


@router.get("/indices/{ts_code}/constituents", summary="获取成分股")
async def get_constituents(
    ts_code: str,
    trade_date: Optional[str] = Query(None, description="交易日期 (YYYYMMDD)"),
    limit: int = Query(100, ge=1, le=500, description="返回数量"),
):
    """获取指数成分股及权重。"""
    service = get_index_service()
    result = service.get_constituents(ts_code, trade_date, limit)
    return result


@router.get("/indices/{ts_code}/factors", summary="获取技术因子")
async def get_factors(
    ts_code: str,
    days: int = Query(30, ge=1, le=250, description="获取天数"),
    indicators: Optional[str] = Query(None, description="指标列表，逗号分隔"),
):
    """获取指数技术因子数据。"""
    service = get_index_service()
    indicator_list = indicators.split(",") if indicators else None
    result = service.get_factors(ts_code, days, indicator_list)
    return result


@router.get("/markets", summary="获取市场列表")
async def get_markets():
    """获取所有可用市场。"""
    service = get_index_service()
    return service.get_markets()


@router.get("/categories", summary="获取类别列表")
async def get_categories():
    """获取所有可用类别。"""
    service = get_index_service()
    return service.get_categories()


@router.post("/analyze", response_model=AnalyzeResponse, summary="AI量化分析")
async def analyze_index(request: AnalyzeRequest):
    """使用AI进行指数量化分析，支持多轮对话记忆。
    
    - 同一个ts_code + user_id组合会保持对话上下文
    - 设置clear_history=true可清空历史重新开始
    - 历史消息会在1小时后自动过期
    """
    service = get_index_service()
    try:
        result = await service.analyze_index(
            ts_code=request.ts_code,
            question=request.question,
            user_id=request.user_id,
            clear_history=request.clear_history,
        )
        return result
    except Exception as e:
        logger.error(f"Analysis failed for {request.ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indices/{ts_code}/quick-analysis", summary="快速量化分析")
async def get_quick_analysis(ts_code: str):
    """获取快速量化分析（不使用AI，直接数据分析）。"""
    service = get_index_service()
    result = service.get_quick_analysis(ts_code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
