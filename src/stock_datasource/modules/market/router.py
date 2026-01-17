"""Market module router.

API endpoints for market data and technical analysis.
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
import logging
import json

from .schemas import (
    KLineRequest,
    KLineResponse,
    IndicatorRequest,
    IndicatorResponse,
    IndicatorResponseV2,
    StockSearchResult,
    AnalysisRequest,
    TrendAnalysisResponse,
    MarketOverviewResponse,
    HotSectorsResponse,
    PatternRequest,
)
from .service import get_market_service

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# K-Line Endpoints
# =============================================================================

@router.post("/kline", response_model=KLineResponse)
async def get_kline(request: KLineRequest):
    """Get K-line data for a stock.
    
    - **code**: Stock code (e.g., 000001.SZ, 600519.SH)
    - **start_date**: Start date (YYYY-MM-DD or YYYYMMDD)
    - **end_date**: End date (YYYY-MM-DD or YYYYMMDD)
    - **adjust**: Adjustment type (qfq=forward, hfq=backward, none)
    """
    service = get_market_service()
    result = await service.get_kline(
        code=request.code,
        start_date=request.start_date,
        end_date=request.end_date,
        adjust=request.adjust
    )
    return KLineResponse(**result)


# =============================================================================
# Technical Indicator Endpoints
# =============================================================================

@router.post("/indicators", response_model=IndicatorResponse)
async def get_indicators(request: IndicatorRequest):
    """Get technical indicators for a stock (legacy format).
    
    Available indicators: MA, EMA, MACD, RSI, KDJ, BOLL, ATR, OBV, DMI, CCI
    
    - **code**: Stock code
    - **indicators**: List of indicators to calculate
    - **period**: Data period in days (default 60)
    """
    service = get_market_service()
    result = await service.get_indicators_legacy(
        code=request.code,
        indicators=request.indicators,
        period=request.period
    )
    return IndicatorResponse(**result)


@router.post("/indicators/v2", response_model=IndicatorResponseV2)
async def get_indicators_v2(request: IndicatorRequest):
    """Get technical indicators for a stock (V2 format with better structure).
    
    Returns indicators as arrays aligned with dates, plus detected signals.
    
    Available indicators: MA, EMA, MACD, RSI, KDJ, BOLL, ATR, OBV, DMI, CCI
    
    - **code**: Stock code
    - **indicators**: List of indicators to calculate
    - **period**: Data period in days (default 60)
    - **params**: Optional custom parameters for indicators
    """
    service = get_market_service()
    params_dict = None
    if request.params:
        params_dict = request.params.dict(exclude_none=True)
    
    result = await service.get_indicators(
        code=request.code,
        indicators=request.indicators,
        period=request.period,
        params=params_dict
    )
    return IndicatorResponseV2(**result)


# =============================================================================
# Search Endpoints
# =============================================================================

@router.get("/search", response_model=List[StockSearchResult])
async def search_stock(keyword: str = Query(..., min_length=1, description="Search keyword")):
    """Search stocks by keyword (code or name)."""
    service = get_market_service()
    results = await service.search_stock(keyword)
    return [StockSearchResult(**r) for r in results]


# =============================================================================
# Market Overview Endpoints
# =============================================================================

@router.get("/overview", response_model=MarketOverviewResponse)
async def get_market_overview():
    """Get market overview with major indices and statistics.
    
    Returns:
    - Major index data (上证指数, 深证成指, 创业板指, etc.)
    - Market statistics (涨跌家数, 涨停跌停数, 成交额)
    """
    service = get_market_service()
    result = await service.get_market_overview()
    return MarketOverviewResponse(**result)


@router.get("/hot-sectors", response_model=HotSectorsResponse)
async def get_hot_sectors():
    """Get hot sectors with leading stocks."""
    service = get_market_service()
    result = await service.get_hot_sectors()
    return HotSectorsResponse(**result)


# =============================================================================
# Analysis Endpoints
# =============================================================================

@router.post("/analysis", response_model=TrendAnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """Analyze stock trend using technical indicators.
    
    Returns:
    - Trend direction (上涨趋势/下跌趋势/震荡)
    - Support and resistance levels
    - Technical signals (金叉/死叉/超买/超卖)
    - Analysis summary
    """
    service = get_market_service()
    result = await service.analyze_trend(
        code=request.code,
        period=request.period
    )
    return TrendAnalysisResponse(**result)


@router.get("/analysis/stream")
async def analyze_stock_stream(
    code: str = Query(..., description="Stock code"),
    period: int = Query(60, ge=10, le=365, description="Analysis period")
):
    """Stream AI analysis for a stock (SSE format).
    
    Returns Server-Sent Events with analysis progress and results.
    """
    async def generate():
        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '正在获取股票数据...'})}\n\n"
            
            service = get_market_service()
            
            # Get trend analysis
            yield f"data: {json.dumps({'type': 'status', 'message': '正在计算技术指标...'})}\n\n"
            
            result = await service.analyze_trend(code, period)
            
            yield f"data: {json.dumps({'type': 'status', 'message': '正在生成分析报告...'})}\n\n"
            
            # Send result
            yield f"data: {json.dumps({'type': 'result', 'data': result})}\n\n"
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Analysis stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/analysis/ai")
async def ai_analyze_stock(request: AnalysisRequest):
    """AI-powered stock analysis using MarketAgent.
    
    This endpoint uses the MarketAgent with LLM to provide deeper analysis.
    """
    try:
        from stock_datasource.agents import get_market_agent
        
        agent = get_market_agent()
        query = f"请分析股票{request.code}的走势，给出技术分析建议"
        
        result = await agent.execute(query, {"period": request.period})
        
        if result.success:
            return {
                "code": request.code,
                "analysis": result.response,
                "metadata": result.metadata
            }
        else:
            return {
                "code": request.code,
                "analysis": result.response,
                "error": True
            }
    except ImportError:
        # MarketAgent not available, fallback to basic analysis
        service = get_market_service()
        result = await service.analyze_trend(request.code, request.period)
        return {
            "code": request.code,
            "analysis": result.get("summary", ""),
            "trend": result.get("trend", ""),
            "signals": result.get("signals", [])
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Pattern Recognition (Future)
# =============================================================================

@router.post("/pattern")
async def detect_pattern(request: PatternRequest):
    """Detect chart patterns (头肩顶, 双底, 等).
    
    Note: This is a placeholder for future pattern recognition feature.
    """
    # TODO: Implement pattern recognition
    return {
        "code": request.code,
        "patterns": [],
        "message": "Pattern recognition coming soon"
    }
