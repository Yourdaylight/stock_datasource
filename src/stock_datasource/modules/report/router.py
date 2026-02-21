"""Report module router with enhanced financial analysis endpoints."""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import logging

from stock_datasource.services.financial_report_service import FinancialReportService
from stock_datasource.agents.report_agent import ReportAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services
financial_service = FinancialReportService()
report_agent = ReportAgent()


class FinancialData(BaseModel):
    """Financial data model for API responses."""
    period: str
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_attr_p: Optional[float] = None
    total_assets: Optional[float] = None
    total_liab: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    gross_margin: Optional[float] = None
    net_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    debt_ratio: Optional[float] = None
    current_ratio: Optional[float] = None
    # Income statement detail fields
    operate_profit: Optional[float] = None
    total_profit: Optional[float] = None
    basic_eps: Optional[float] = None
    diluted_eps: Optional[float] = None
    ebit: Optional[float] = None
    ebitda: Optional[float] = None
    # Cost & expense
    oper_cost: Optional[float] = None
    sell_exp: Optional[float] = None
    admin_exp: Optional[float] = None
    fin_exp: Optional[float] = None
    rd_exp: Optional[float] = None
    total_cogs: Optional[float] = None
    # Expense ratios (% of revenue)
    sell_exp_ratio: Optional[float] = None
    admin_exp_ratio: Optional[float] = None
    fin_exp_ratio: Optional[float] = None
    rd_exp_ratio: Optional[float] = None
    # Tax & other
    income_tax: Optional[float] = None
    biz_tax_surchg: Optional[float] = None
    minority_gain: Optional[float] = None
    invest_income: Optional[float] = None
    non_oper_income: Optional[float] = None
    non_oper_exp: Optional[float] = None
    
    @field_validator('*', mode='before')
    @classmethod
    def parse_nullable_float(cls, v, info):
        """Parse nullable float values, handling ClickHouse NULL representations."""
        if info.field_name == 'period':
            return v
        if v is None or v == '\\N' or v == 'None' or v == '':
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class FinancialRequest(BaseModel):
    """Request model for financial data."""
    code: str = Field(..., description="Stock code (e.g., 600519.SH or 600519)")
    periods: int = Field(default=4, ge=1, le=20, description="Number of periods to analyze")


class FinancialResponse(BaseModel):
    """Response model for financial data."""
    code: str
    name: Optional[str] = None
    periods: int
    latest_period: Optional[str] = None
    data: List[FinancialData]
    summary: Optional[Dict[str, Any]] = None
    status: str


class CompareRequest(BaseModel):
    """Request model for peer comparison."""
    code: str = Field(..., description="Stock code")
    end_date: Optional[str] = Field(None, description="Report date in YYYYMMDD format")
    industry_limit: int = Field(default=20, ge=5, le=100, description="Number of peer companies")


class CompareResponse(BaseModel):
    """Response model for peer comparison."""
    code: str
    end_date: str
    peer_count: int
    comparison: Dict[str, Any]
    interpretation: Dict[str, Any]
    status: str


class AnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    code: str = Field(..., description="Stock code")
    analysis_type: str = Field(default="comprehensive", description="Type of analysis")
    periods: int = Field(default=4, ge=1, le=20, description="Number of periods")


class AnalysisResponse(BaseModel):
    """Response model for AI analysis."""
    code: str
    analysis_type: str
    content: str
    insights: Optional[Dict[str, Any]] = None
    status: str


def _normalize_stock_code(code: str) -> str:
    """Normalize stock code format."""
    if len(code) == 6 and code.isdigit():
        if code.startswith('6'):
            return f"{code}.SH"
        elif code.startswith(('0', '3')):
            return f"{code}.SZ"
    return code


@router.post("/financial", response_model=FinancialResponse)
async def get_financial(request: FinancialRequest):
    """Get comprehensive financial data and analysis."""
    try:
        # Normalize stock code
        normalized_code = _normalize_stock_code(request.code)
        
        # Get comprehensive analysis
        analysis = financial_service.get_comprehensive_analysis(normalized_code, request.periods)
        
        if analysis.get("status") == "error":
            raise HTTPException(status_code=400, detail=analysis.get("error", "Analysis failed"))
        
        summary_data = analysis.get("summary", {})
        raw_data = summary_data.get("raw_data", [])
        
        # Helper function to clean ClickHouse NULL values
        def clean_null_values(data):
            """Recursively clean \\N values from dict/list structures."""
            if isinstance(data, dict):
                return {k: clean_null_values(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [clean_null_values(v) for v in data]
            elif data == '\\N' or data == 'None' or data == '':
                return None
            elif isinstance(data, float):
                import math
                if math.isnan(data) or math.isinf(data):
                    return None
                return data
            elif isinstance(data, str):
                # Try to convert numeric strings to float
                try:
                    f = float(data)
                    import math
                    return None if (math.isnan(f) or math.isinf(f)) else f
                except (ValueError, TypeError):
                    return data
            return data
        
        # Helper: check if a value is valid (not None, not ClickHouse NULL '\N')
        def _valid(v):
            return v is not None and v != '\\N' and v != 'None' and v != ''
        
        # Supplement revenue / net_profit from income statement as fallback
        # (service layer already tries this, but router provides a second pass)
        income_map: Dict[str, Dict[str, Any]] = {}
        try:
            income_data = financial_service.income_service.get_profitability_metrics(
                normalized_code, request.periods * 3  # fetch more periods to cover date gaps
            )
            for m in income_data.get("metrics", []):
                ed = m.get("end_date", "")
                if ed:
                    income_map[ed] = m
        except Exception as e:
            logger.warning(f"Failed to get income data for {normalized_code}: {e}")
        
        # Convert raw data to FinancialData format
        financial_data = []
        for item in raw_data:
            # Convert end_date to string if it's a pandas Timestamp
            end_date = item.get("end_date", "")
            if hasattr(end_date, 'strftime'):
                end_date = end_date.strftime('%Y-%m-%d')
            elif end_date and not isinstance(end_date, str):
                end_date = str(end_date)
            
            # Try to get revenue / net_profit from income statement
            income_item = income_map.get(end_date, {})
            
            raw_revenue = item.get("total_revenue")
            raw_net_profit = item.get("net_profit")
            revenue = raw_revenue if _valid(raw_revenue) else income_item.get("total_revenue")
            net_profit = raw_net_profit if _valid(raw_net_profit) else income_item.get("net_income")
            
            # Also fallback gross_margin / net_margin from income
            raw_gross_margin = item.get("gross_profit_margin")
            raw_net_margin = item.get("net_profit_margin")
            gross_margin = raw_gross_margin if _valid(raw_gross_margin) else income_item.get("gross_margin")
            net_margin = raw_net_margin if _valid(raw_net_margin) else income_item.get("net_margin")
            
            financial_data.append(FinancialData(
                period=end_date,
                revenue=revenue,
                net_profit=net_profit,
                net_profit_attr_p=income_item.get("net_income_attr_parent"),
                total_assets=item.get("total_assets"),
                total_liab=item.get("total_liab"),
                roe=item.get("roe"),
                roa=item.get("roa"),
                gross_margin=gross_margin,
                net_margin=net_margin,
                operating_margin=income_item.get("operating_margin"),
                debt_ratio=item.get("debt_to_assets"),
                current_ratio=item.get("current_ratio"),
                # Income statement details
                operate_profit=income_item.get("operate_profit"),
                total_profit=income_item.get("total_profit"),
                basic_eps=income_item.get("basic_eps"),
                diluted_eps=income_item.get("diluted_eps"),
                ebit=income_item.get("ebit"),
                ebitda=income_item.get("ebitda"),
                # Cost & expense
                oper_cost=income_item.get("oper_cost"),
                sell_exp=income_item.get("sell_exp"),
                admin_exp=income_item.get("admin_exp"),
                fin_exp=income_item.get("fin_exp"),
                rd_exp=income_item.get("rd_exp"),
                total_cogs=income_item.get("total_cogs"),
                # Expense ratios
                sell_exp_ratio=income_item.get("sell_exp_ratio"),
                admin_exp_ratio=income_item.get("admin_exp_ratio"),
                fin_exp_ratio=income_item.get("fin_exp_ratio"),
                rd_exp_ratio=income_item.get("rd_exp_ratio"),
                # Tax & other
                income_tax=income_item.get("income_tax"),
                biz_tax_surchg=income_item.get("biz_tax_surchg"),
                minority_gain=income_item.get("minority_gain"),
                invest_income=income_item.get("invest_income"),
                non_oper_income=income_item.get("non_oper_income"),
                non_oper_exp=income_item.get("non_oper_exp"),
            ))
        
        # Convert latest_period to string if needed
        latest_period = summary_data.get("latest_period")
        if hasattr(latest_period, 'strftime'):
            latest_period = latest_period.strftime('%Y-%m-%d')
        elif latest_period and not isinstance(latest_period, str):
            latest_period = str(latest_period)
        
        # Clean null values from summary data
        profitability = clean_null_values(summary_data.get("profitability", {}))
        solvency = clean_null_values(summary_data.get("solvency", {}))
        efficiency = clean_null_values(summary_data.get("efficiency", {}))
        growth = clean_null_values(summary_data.get("growth", {}))
        
        return FinancialResponse(
            code=normalized_code,
            name=f"股票 {normalized_code}",  # In production, get from stock basic info
            periods=summary_data.get("periods", 0),
            latest_period=latest_period,
            data=financial_data,
            summary={
                "profitability": profitability,
                "solvency": solvency,
                "efficiency": efficiency,
                "growth": growth,
                "health_score": analysis.get("health_analysis", {}).get("health_score", 0)
            },
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_financial for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/compare", response_model=CompareResponse)
async def compare_financials(request: CompareRequest):
    """Get peer comparison analysis."""
    try:
        # Normalize stock code
        normalized_code = _normalize_stock_code(request.code)
        
        # Get peer comparison
        analysis = financial_service.get_peer_comparison_analysis(normalized_code, request.end_date)
        
        if analysis.get("status") == "error":
            raise HTTPException(status_code=400, detail=analysis.get("error", "Comparison failed"))
        
        comparison_data = analysis.get("comparison", {})
        
        return CompareResponse(
            code=normalized_code,
            end_date=analysis.get("end_date", ""),
            peer_count=comparison_data.get("peer_count", 0),
            comparison=comparison_data.get("comparison", {}),
            interpretation=analysis.get("interpretation", {}),
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in compare_financials for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/analysis", response_model=AnalysisResponse)
async def get_ai_analysis(request: AnalysisRequest):
    """Get AI-powered financial analysis and insights."""
    try:
        # Normalize stock code
        normalized_code = _normalize_stock_code(request.code)
        
        # Generate AI analysis based on type
        if request.analysis_type == "comprehensive":
            # Use ReportAgent for comprehensive analysis
            from stock_datasource.agents.report_agent import get_comprehensive_financial_analysis
            content = get_comprehensive_financial_analysis(normalized_code, request.periods)
            
            # Also get structured insights
            insights_data = financial_service.get_investment_insights(normalized_code)
            insights = insights_data.get("insights", {}) if insights_data.get("status") == "success" else None
            
        elif request.analysis_type == "peer_comparison":
            from stock_datasource.agents.report_agent import get_peer_comparison_analysis
            content = get_peer_comparison_analysis(normalized_code)
            insights = None
            
        elif request.analysis_type == "investment_insights":
            from stock_datasource.agents.report_agent import get_investment_insights
            content = get_investment_insights(normalized_code)
            
            # Get structured insights
            insights_data = financial_service.get_investment_insights(normalized_code)
            insights = insights_data.get("insights", {}) if insights_data.get("status") == "success" else None
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported analysis type: {request.analysis_type}")
        
        return AnalysisResponse(
            code=normalized_code,
            analysis_type=request.analysis_type,
            content=content,
            insights=insights,
            status="success"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_ai_analysis for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "financial_report"}


# ========== 新增：三大财务报表 API ==========

class StatementRequest(BaseModel):
    """Request model for financial statements."""
    code: str = Field(..., description="Stock code (e.g., 600519.SH or 600519)")
    periods: int = Field(default=4, ge=1, le=20, description="Number of periods")
    report_type: int = Field(default=1, ge=1, le=6, description="Report type: 1=合并报表, 2=单季合并, 4=调整合并, 6=母公司")


class ForecastRequest(BaseModel):
    """Request model for forecast/express data."""
    code: str = Field(..., description="Stock code")
    limit: int = Field(default=10, ge=1, le=50, description="Number of records")


@router.post("/income")
async def get_income_statement(request: StatementRequest):
    """获取利润表数据"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_income_statement(
            normalized_code, request.periods, request.report_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting income statement for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/balance")
async def get_balance_sheet(request: StatementRequest):
    """获取资产负债表数据"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_balance_sheet(
            normalized_code, request.periods, request.report_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting balance sheet for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cashflow")
async def get_cash_flow(request: StatementRequest):
    """获取现金流量表数据"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_cash_flow(
            normalized_code, request.periods, request.report_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cash flow for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/statements")
async def get_full_statements(request: StatementRequest):
    """获取完整三大财务报表（利润表+资产负债表+现金流量表）"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_full_financial_statements(
            normalized_code, request.periods, request.report_type
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting full statements for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast")
async def get_forecast(request: ForecastRequest):
    """获取业绩预告数据"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_forecast(normalized_code, request.limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting forecast for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/express")
async def get_express(request: ForecastRequest):
    """获取业绩快报数据"""
    try:
        normalized_code = _normalize_stock_code(request.code)
        result = financial_service.get_express(normalized_code, request.limit)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting express for {request.code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Legacy endpoint for backward compatibility
@router.post("/financial_legacy")
async def get_financial_legacy(request: FinancialRequest):
    """Legacy financial endpoint (deprecated)."""
    # Mock implementation for backward compatibility
    return {
        "code": request.code,
        "name": "示例公司",
        "data": [
            {
                "period": "2024Q3",
                "revenue": 100000000000,
                "net_profit": 50000000000,
                "roe": 0.25,
                "gross_margin": 0.9
            }
        ]
    }
