"""FastAPI router for Overview module."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
import logging

from .service import get_overview_service
from .schemas import (
    DailyOverviewResponse,
    HotEtfResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    QuickAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/daily", response_model=DailyOverviewResponse, summary="获取每日市场概览")
async def get_daily_overview(
    date: Optional[str] = Query(None, description="交易日期 (YYYYMMDD)，默认最新"),
):
    """获取每日市场概览，包括主要指数、市场统计、热门ETF。"""
    service = get_overview_service()
    result = service.get_daily_overview(date)
    return result


@router.get("/hot-etfs", response_model=HotEtfResponse, summary="获取热门ETF")
async def get_hot_etfs(
    date: Optional[str] = Query(None, description="交易日期 (YYYYMMDD)，默认最新"),
    sort_by: str = Query("amount", description="排序字段 (amount=成交额, pct_chg=涨跌幅)"),
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
):
    """获取热门ETF列表。"""
    if sort_by not in ["amount", "pct_chg"]:
        raise HTTPException(status_code=400, detail="Invalid sort_by value")
    
    service = get_overview_service()
    result = service.get_hot_etfs(date, sort_by, limit)
    return result


@router.get("/indices", summary="获取主要指数行情")
async def get_indices(
    date: Optional[str] = Query(None, description="交易日期 (YYYYMMDD)，默认最新"),
):
    """获取主要指数行情数据。"""
    service = get_overview_service()
    result = service.get_indices(date)
    return result


@router.post("/analyze", response_model=AnalyzeResponse, summary="市场AI分析")
async def analyze_market(request: AnalyzeRequest):
    """使用AI进行市场分析，支持多轮对话记忆。
    
    - 同一个user_id + date组合会保持对话上下文
    - 设置clear_history=true可清空历史重新开始
    """
    service = get_overview_service()
    try:
        result = await service.analyze_market(
            question=request.question,
            user_id=request.user_id,
            date=request.date,
            clear_history=request.clear_history,
        )
        return result
    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick-analysis", summary="市场快速分析")
async def get_quick_analysis(
    date: Optional[str] = Query(None, description="分析日期 (YYYYMMDD)，默认最新"),
):
    """获取市场快速分析（不使用AI，直接数据分析）。"""
    service = get_overview_service()
    result = service.get_quick_analysis(date)
    return result
