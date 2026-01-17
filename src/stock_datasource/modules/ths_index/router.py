"""FastAPI router for THS Index module."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Path
import logging

from .service import get_ths_index_service
from .schemas import (
    THSIndexListResponse,
    THSDailyResponse,
    THSRankingResponse,
    THSSearchResponse,
    THSStatsResponse,
    THSIndexItem,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/list", response_model=THSIndexListResponse, summary="获取板块指数列表")
async def get_index_list(
    exchange: Optional[str] = Query(None, description="市场类型: A-A股, HK-港股, US-美股"),
    type: Optional[str] = Query(None, description="指数类型: N-概念, I-行业, R-地域, S-特色, ST-风格, TH-主题, BB-宽基"),
    limit: int = Query(100, ge=1, le=1000, description="返回数量"),
    offset: int = Query(0, ge=0, description="分页偏移"),
):
    """获取同花顺板块指数列表，支持按市场和类型筛选。"""
    service = get_ths_index_service()
    result = service.get_index_list(
        exchange=exchange,
        index_type=type,
        limit=limit,
        offset=offset,
    )
    return result


@router.get("/search", response_model=THSSearchResponse, summary="搜索板块指数")
async def search_index(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
):
    """按名称关键词搜索板块指数。"""
    service = get_ths_index_service()
    result = service.search_index(keyword=keyword, limit=limit)
    return result


@router.get("/ranking", response_model=THSRankingResponse, summary="获取板块涨跌排行")
async def get_ranking(
    date: Optional[str] = Query(None, description="交易日期 (YYYYMMDD)，默认最新"),
    type: Optional[str] = Query(None, description="指数类型筛选: N-概念, I-行业, R-地域等"),
    sort_by: str = Query("pct_change", description="排序字段: pct_change-涨跌幅, vol-成交量, turnover_rate-换手率"),
    order: str = Query("desc", description="排序方向: desc-降序, asc-升序"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """获取板块指数涨跌排行榜。"""
    # Validate sort_by
    valid_sort_fields = {"pct_change", "vol", "turnover_rate", "close"}
    if sort_by not in valid_sort_fields:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid sort_by value. Must be one of: {', '.join(valid_sort_fields)}"
        )
    
    # Validate order
    if order.lower() not in {"desc", "asc"}:
        raise HTTPException(status_code=400, detail="Invalid order value. Must be 'desc' or 'asc'")
    
    service = get_ths_index_service()
    result = service.get_ranking(
        date=date,
        index_type=type,
        sort_by=sort_by,
        order=order.lower(),
        limit=limit,
    )
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/stats", response_model=THSStatsResponse, summary="获取板块指数统计")
async def get_stats():
    """获取板块指数按类型和市场的统计信息。"""
    service = get_ths_index_service()
    result = service.get_stats()
    return result


@router.get("/{ts_code}", response_model=THSIndexItem, summary="获取板块指数详情")
async def get_index_detail(
    ts_code: str = Path(..., description="板块指数代码，如 885001.TI"),
):
    """获取单个板块指数的详细信息。"""
    service = get_ths_index_service()
    result = service.get_index_by_code(ts_code)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Index {ts_code} not found")
    
    return result


@router.get("/{ts_code}/daily", response_model=THSDailyResponse, summary="获取板块指数日线数据")
async def get_daily_data(
    ts_code: str = Path(..., description="板块指数代码，如 885001.TI"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYYMMDD)"),
    limit: int = Query(30, ge=1, le=365, description="默认返回最近N条记录"),
):
    """获取板块指数的日线行情数据。"""
    service = get_ths_index_service()
    result = service.get_daily_data(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return result
