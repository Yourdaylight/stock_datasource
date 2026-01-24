"""FastAPI router for ETF module."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
import logging

from .service import get_etf_service
from .schemas import (
    EtfListResponse,
    EtfInfo,
    EtfDailyResponse,
    EtfKLineResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    QuickAnalysisResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/etfs", response_model=EtfListResponse, summary="获取ETF列表")
async def get_etfs(
    market: Optional[str] = Query(None, description="交易所筛选 (E=上交所, Z=深交所)"),
    fund_type: Optional[str] = Query(None, description="ETF类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选 (L=上市, D=退市, P=待上市)"),
    invest_type: Optional[str] = Query(None, description="投资类型筛选"),
    keyword: Optional[str] = Query(None, description="名称/代码搜索关键词"),
    trade_date: Optional[str] = Query(None, description="交易日期筛选 (YYYYMMDD)"),
    manager: Optional[str] = Query(None, description="基金管理人筛选"),
    tracking_index: Optional[str] = Query(None, description="跟踪指数代码筛选"),
    fee_min: Optional[float] = Query(None, ge=0, description="最小管理费率 (%)"),
    fee_max: Optional[float] = Query(None, ge=0, description="最大管理费率 (%)"),
    amount_min: Optional[float] = Query(None, ge=0, description="最小成交额 (万元)"),
    pct_chg_min: Optional[float] = Query(None, description="最小涨跌幅 (%)"),
    pct_chg_max: Optional[float] = Query(None, description="最大涨跌幅 (%)"),
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_order: str = Query("desc", description="排序方向 (asc/desc)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取ETF列表（包含指定日期行情），支持分页和筛选。"""
    service = get_etf_service()
    
    # Map frontend parameter names to backend field names
    exchange_map = {'E': 'SH', 'Z': 'SZ'}
    exchange = exchange_map.get(market, market) if market else None
    
    result = service.get_etfs(
        exchange=exchange,
        etf_type=fund_type,
        list_status=status,
        keyword=keyword,
        trade_date=trade_date,
        manager=manager,
        tracking_index=tracking_index,
        fee_min=fee_min,
        fee_max=fee_max,
        amount_min=amount_min,
        pct_chg_min=pct_chg_min,
        pct_chg_max=pct_chg_max,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return result


@router.get("/etfs/{ts_code}", response_model=EtfInfo, summary="获取ETF详情")
async def get_etf_detail(ts_code: str):
    """获取ETF详细信息。"""
    service = get_etf_service()
    result = service.get_etf_detail(ts_code)
    if not result:
        raise HTTPException(status_code=404, detail=f"ETF {ts_code} not found")
    return result


@router.get("/etfs/{ts_code}/daily", response_model=EtfDailyResponse, summary="获取ETF日线数据")
async def get_etf_daily(
    ts_code: str,
    days: int = Query(30, ge=1, le=250, description="获取天数"),
):
    """获取ETF日线行情数据。"""
    service = get_etf_service()
    result = service.get_daily(ts_code, days)
    return result


@router.get("/etfs/{ts_code}/kline", response_model=EtfKLineResponse, summary="获取ETF K线数据")
async def get_etf_kline(
    ts_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYYMMDD)"),
    adjust: str = Query("qfq", description="复权类型 (qfq=前复权, hfq=后复权, none=不复权)"),
):
    """获取ETF K线数据，支持复权。"""
    if adjust not in ["qfq", "hfq", "none"]:
        raise HTTPException(status_code=400, detail="Invalid adjust type")
    
    service = get_etf_service()
    result = service.get_kline(ts_code, start_date, end_date, adjust)
    return result


@router.get("/exchanges", summary="获取交易所列表")
async def get_exchanges():
    """获取所有可用交易所。"""
    service = get_etf_service()
    return service.get_exchanges()


@router.get("/types", summary="获取ETF类型列表")
async def get_types():
    """获取所有可用ETF类型。"""
    service = get_etf_service()
    return service.get_types()


@router.get("/invest-types", summary="获取投资类型列表")
async def get_invest_types():
    """获取所有可用投资类型。"""
    service = get_etf_service()
    return service.get_invest_types()


@router.get("/managers", summary="获取管理人列表")
async def get_managers():
    """获取所有可用基金管理人。"""
    service = get_etf_service()
    return service.get_managers()


@router.get("/tracking-indices", summary="获取跟踪指数列表")
async def get_tracking_indices():
    """获取所有跟踪指数。"""
    service = get_etf_service()
    return service.get_tracking_indices()


@router.get("/trade-dates", summary="获取可用交易日期")
async def get_trade_dates(
    limit: int = Query(30, ge=1, le=365, description="返回日期数量"),
):
    """获取可用交易日期列表。"""
    service = get_etf_service()
    return service.get_trade_dates(limit)


@router.post("/analyze", response_model=AnalyzeResponse, summary="ETF AI量化分析")
async def analyze_etf(request: AnalyzeRequest):
    """使用AI进行ETF量化分析，支持多轮对话记忆。
    
    - 同一个ts_code + user_id组合会保持对话上下文
    - 设置clear_history=true可清空历史重新开始
    """
    service = get_etf_service()
    try:
        result = await service.analyze_etf(
            ts_code=request.ts_code,
            question=request.question,
            user_id=request.user_id,
            clear_history=request.clear_history,
        )
        return result
    except Exception as e:
        logger.error(f"ETF analysis failed for {request.ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/etfs/{ts_code}/quick-analysis", summary="ETF快速量化分析")
async def get_quick_analysis(ts_code: str):
    """获取ETF快速量化分析（不使用AI，直接数据分析）。"""
    service = get_etf_service()
    result = service.get_quick_analysis(ts_code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
