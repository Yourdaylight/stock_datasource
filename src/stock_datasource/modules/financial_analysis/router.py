"""Financial Analysis module router - company list, report browsing, AI analysis."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user

from stock_datasource.utils.stock_code import validate_and_normalize_stock_code

from .service import FinancialAnalysisService

logger = logging.getLogger(__name__)
router = APIRouter()
service = FinancialAnalysisService()


# ========== Request / Response Models ==========


class AnalyzeRequest(BaseModel):
    """Request model for triggering AI analysis."""

    code: str = Field(..., description="Stock code (e.g., 600519 or 00700.HK)")
    end_date: str = Field(..., description="Report period (e.g., 20241231)")
    market: str = Field(default="A", description="Market: 'A' or 'HK'")
    analysis_type: str = Field(default="comprehensive", description="Analysis type")


# ========== Helper ==========


def _normalize_code(code: str, market: str = "auto") -> str:
    """Normalize stock code, raise HTTP 400 on invalid."""
    is_valid, normalized, error_msg = validate_and_normalize_stock_code(
        code, market=market
    )
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    return normalized


# ========== Endpoints ==========


@router.get("/companies")
async def get_companies(
    market: str = Query(default="A", description="Market: 'A' or 'HK'"),
    keyword: str = Query(default="", description="Search by code or name"),
    industry: str = Query(default="", description="Filter by industry"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    current_user: dict = Depends(get_current_user),
):
    """获取上市公司列表，支持分页、搜索、行业筛选。"""
    try:
        result = service.get_companies(
            market=market,
            keyword=keyword,
            industry=industry,
            page=page,
            page_size=page_size,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_companies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/industries")
async def get_industries(
    market: str = Query(default="A", description="Market: 'A' or 'HK'"),
    current_user: dict = Depends(get_current_user),
):
    """获取行业列表，用于筛选下拉。"""
    try:
        result = service.get_industries(market=market)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_industries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{code}/reports")
async def get_report_periods(
    code: str,
    market: str = Query(default="A", description="Market: 'A' or 'HK'"),
    current_user: dict = Depends(get_current_user),
):
    """获取指定公司的所有财报期列表，含核心指标摘要和AI分析状态。"""
    try:
        market_hint = "hk" if market == "HK" else "cn"
        normalized_code = _normalize_code(code, market=market_hint)
        result = service.get_report_periods(normalized_code, market=market)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_report_periods for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{code}/reports/{period}")
async def get_report_detail(
    code: str,
    period: str,
    market: str = Query(default="A", description="Market: 'A' or 'HK'"),
    current_user: dict = Depends(get_current_user),
):
    """获取指定公司指定报告期的财报详情。"""
    try:
        market_hint = "hk" if market == "HK" else "cn"
        normalized_code = _normalize_code(code, market=market_hint)
        result = service.get_report_detail(normalized_code, period, market=market)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_report_detail for {code}/{period}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def run_analysis(request: AnalyzeRequest, current_user: dict = Depends(get_current_user)):
    """触发专业AI财报分析（规则引擎），分析结果自动固化存储。"""
    try:
        market_hint = "hk" if request.market == "HK" else "cn"
        normalized_code = _normalize_code(request.code, market=market_hint)
        result = service.run_analysis(
            ts_code=normalized_code,
            end_date=request.end_date,
            market=request.market,
            analysis_type=request.analysis_type,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in run_analysis for {request.code}/{request.end_date}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/ai-deep")
async def run_llm_analysis(request: AnalyzeRequest, current_user: dict = Depends(get_current_user)):
    """触发LLM大模型深度财报分析（需人工触发，耗时较长）。

    调用配置的LLM（如GPT-4/Kimi）对财务数据进行深度分析，
    生成具有专业洞察力的分析报告。通常需要10-60秒。
    """
    try:
        market_hint = "hk" if request.market == "HK" else "cn"
        normalized_code = _normalize_code(request.code, market=market_hint)
        result = service.run_llm_analysis(
            ts_code=normalized_code,
            end_date=request.end_date,
            market=request.market,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error in run_llm_analysis for {request.code}/{request.end_date}: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{code}/analyses")
async def get_analysis_history(
    code: str,
    end_date: str | None = Query(default=None, description="Filter by report period"),
    market: str = Query(default="A", description="Market: 'A' or 'HK'"),
    limit: int = Query(default=20, ge=1, le=100, description="Max records"),
    current_user: dict = Depends(get_current_user),
):
    """获取指定公司的历史分析记录列表。"""
    try:
        market_hint = "hk" if market == "HK" else "cn"
        normalized_code = _normalize_code(code, market=market_hint)
        result = service.get_analysis_history(
            normalized_code, end_date=end_date, limit=limit
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_analysis_history for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyses/{record_id}")
async def get_analysis_record(record_id: str, current_user: dict = Depends(get_current_user)):
    """获取单条分析记录详情。"""
    try:
        result = service.get_analysis_record(record_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_analysis_record for {record_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(current_user: dict = Depends(get_current_user)):
    """Health check endpoint."""
    return {"status": "healthy", "service": "financial_analysis"}
