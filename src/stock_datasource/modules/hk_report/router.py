"""HK Report module router with financial analysis endpoints for Hong Kong stocks."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import logging

from stock_datasource.services.hk_financial_report_service import HKFinancialReportService
from stock_datasource.utils.stock_code import normalize_stock_code_for_router

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize service
hk_financial_service = HKFinancialReportService()


def _validate_hk_stock_code(code: str) -> str:
    """Validate and normalize HK stock code using unified utility."""
    return normalize_stock_code_for_router(code, market="hk")


# ========== Request Models ==========

class HKFinancialRequest(BaseModel):
    """Request model for HK financial data."""
    code: str = Field(..., description="HK stock code (e.g., 00700.HK or 00700)")
    periods: int = Field(default=8, ge=1, le=40, description="Number of periods to analyze")


class HKStatementRequest(BaseModel):
    """Request model for HK financial statements."""
    code: str = Field(..., description="HK stock code")
    periods: int = Field(default=8, ge=1, le=40, description="Number of periods")
    period: Optional[str] = Field(None, description="Specific report period YYYYMMDD")
    indicators: Optional[str] = Field(None, description="Comma-separated indicator names")


class HKRawRequest(BaseModel):
    """Request model for raw EAV data."""
    code: str = Field(..., description="HK stock code")
    period: Optional[str] = Field(None, description="Report period YYYYMMDD")
    indicators: Optional[str] = Field(None, description="Comma-separated indicator names")
    limit: int = Field(default=500, ge=1, le=5000, description="Max records")


class HKAnalysisRequest(BaseModel):
    """Request model for HK AI analysis."""
    code: str = Field(..., description="HK stock code")
    periods: int = Field(default=8, ge=1, le=40, description="Number of periods to analyze")


class HKIndicatorListRequest(BaseModel):
    """Request model for listing indicators."""
    code: Optional[str] = Field(None, description="HK stock code (optional, for filtering)")


# ========== API Endpoints ==========

@router.post("/financial")
async def get_hk_financial(request: HKFinancialRequest):
    """获取港股综合财务分析"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_comprehensive_analysis(code, request.periods)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in HK financial analysis for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators")
async def get_hk_indicators(request: HKFinancialRequest):
    """获取港股财务指标数据（宽表）"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_financial_indicators(code, request.periods)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK indicators for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/income")
async def get_hk_income(request: HKStatementRequest):
    """获取港股利润表数据（PIVOT 宽表格式）"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_income_statement(code, request.periods, request.period)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK income for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/balance")
async def get_hk_balance(request: HKStatementRequest):
    """获取港股资产负债表数据（PIVOT 宽表格式）"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_balance_sheet(code, request.periods, request.period)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK balance for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cashflow")
async def get_hk_cashflow(request: HKStatementRequest):
    """获取港股现金流量表数据（PIVOT 宽表格式）"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_cash_flow(code, request.periods, request.period)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK cashflow for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/statements")
async def get_hk_statements(request: HKFinancialRequest):
    """获取港股完整三大财务报表（利润表+资产负债表+现金流量表）"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_full_financial_statements(code, request.periods)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK statements for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Raw EAV Endpoints ==========

@router.post("/income/raw")
async def get_hk_income_raw(request: HKRawRequest):
    """获取港股利润表原始 EAV 数据"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_income_raw(code, request.period, request.indicators, request.limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK income raw for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/balance/raw")
async def get_hk_balance_raw(request: HKRawRequest):
    """获取港股资产负债表原始 EAV 数据"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_balancesheet_raw(code, request.period, request.indicators, request.limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK balance raw for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cashflow/raw")
async def get_hk_cashflow_raw(request: HKRawRequest):
    """获取港股现金流量表原始 EAV 数据"""
    try:
        code = _validate_hk_stock_code(request.code)
        result = hk_financial_service.get_cashflow_raw(code, request.period, request.indicators, request.limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting HK cashflow raw for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Indicator List Endpoints ==========

@router.post("/indicators/income")
async def list_hk_income_indicators(request: HKIndicatorListRequest):
    """列出港股利润表所有可用指标"""
    try:
        code = _validate_hk_stock_code(request.code) if request.code else None
        indicators = hk_financial_service.list_income_indicators(code)
        return {"indicators": indicators, "count": len(indicators)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing HK income indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators/balance")
async def list_hk_balance_indicators(request: HKIndicatorListRequest):
    """列出港股资产负债表所有可用指标"""
    try:
        code = _validate_hk_stock_code(request.code) if request.code else None
        indicators = hk_financial_service.list_balancesheet_indicators(code)
        return {"indicators": indicators, "count": len(indicators)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing HK balance indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators/cashflow")
async def list_hk_cashflow_indicators(request: HKIndicatorListRequest):
    """列出港股现金流量表所有可用指标"""
    try:
        code = _validate_hk_stock_code(request.code) if request.code else None
        indicators = hk_financial_service.list_cashflow_indicators(code)
        return {"indicators": indicators, "count": len(indicators)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing HK cashflow indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "hk_financial_report"}


@router.post("/analysis")
async def get_hk_ai_analysis(request: HKAnalysisRequest):
    """获取港股AI智能分析"""
    try:
        code = _validate_hk_stock_code(request.code)
        from stock_datasource.agents.hk_report_agent import get_hk_comprehensive_financial_analysis
        content = get_hk_comprehensive_financial_analysis(code, request.periods)
        return {
            "code": code,
            "analysis_type": "comprehensive",
            "content": content,
            "insights": None,
            "status": "success"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in HK AI analysis for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
