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


@router.get("/hot-stocks")
async def get_hot_stocks(
    sort_by: str = Query("amount", description="Sort by: amount or pct_chg"),
    limit: int = Query(10, ge=1, le=50, description="Number of stocks to return"),
    date: Optional[str] = Query(None, description="Trade date (YYYY-MM-DD)")
):
    """Get hot stocks by trading amount or price change.
    
    - **sort_by**: 'amount' for trading volume leaders, 'pct_chg' for top gainers
    - **limit**: Number of stocks (1-50)
    - **date**: Optional trade date, defaults to latest
    """
    service = get_market_service()
    result = await service.get_hot_stocks(sort_by=sort_by, limit=limit, date=date)
    return result


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
    
    This endpoint:
    1. Fetches actual stock data and technical indicators
    2. Passes the data as context to LLM for deeper analysis
    """
    service = get_market_service()
    
    # Step 1: Get actual technical analysis data
    try:
        trend_data = await service.analyze_trend(request.code, request.period)
    except Exception as e:
        logger.error(f"Failed to get trend data: {e}")
        raise HTTPException(status_code=500, detail=f"获取股票数据失败: {str(e)}")
    
    # Step 2: Get additional indicator details
    try:
        indicator_data = await service.get_indicators(
            request.code, 
            ["MACD", "RSI", "KDJ", "BOLL", "MA"], 
            period=request.period
        )
    except Exception as e:
        logger.warning(f"Failed to get indicators: {e}")
        indicator_data = {}
    
    # Step 3: Format data for LLM context
    stock_name = trend_data.get("name", request.code)
    trend = trend_data.get("trend", "未知")
    support = trend_data.get("support", 0)
    resistance = trend_data.get("resistance", 0)
    signals = trend_data.get("signals", [])
    
    # Extract latest indicator values
    indicators = indicator_data.get("indicators", {})
    latest_indicators = {}
    for key, values in indicators.items():
        if values and len(values) > 0:
            # Get last non-null value
            for v in reversed(values):
                if v is not None:
                    latest_indicators[key] = round(v, 2) if isinstance(v, float) else v
                    break
    
    # Format signals for prompt
    signal_text = ""
    if signals:
        bullish = [s for s in signals if s.get("type") == "bullish"]
        bearish = [s for s in signals if s.get("type") == "bearish"]
        if bullish:
            signal_text += f"\n看多信号: {', '.join(s.get('signal', '') for s in bullish)}"
        if bearish:
            signal_text += f"\n看空信号: {', '.join(s.get('signal', '') for s in bearish)}"
    
    # Build detailed prompt with actual data
    data_context = f"""
## 股票基础信息
- 股票代码: {request.code}
- 股票名称: {stock_name}
- 分析周期: {request.period}天

## 趋势判断
- 当前趋势: {trend}
- 支撑位: {support:.2f}
- 压力位: {resistance:.2f}

## 技术指标最新值
"""
    
    # Add indicator values
    indicator_names = {
        "MACD_DIF": "MACD DIF",
        "MACD_DEA": "MACD DEA", 
        "MACD_HIST": "MACD 柱状",
        "RSI": "RSI",
        "KDJ_K": "KDJ K值",
        "KDJ_D": "KDJ D值",
        "KDJ_J": "KDJ J值",
        "BOLL_UPPER": "布林上轨",
        "BOLL_MID": "布林中轨",
        "BOLL_LOWER": "布林下轨",
        "MA5": "5日均线",
        "MA10": "10日均线",
        "MA20": "20日均线",
        "MA60": "60日均线",
    }
    
    for key, display_name in indicator_names.items():
        if key in latest_indicators:
            data_context += f"- {display_name}: {latest_indicators[key]}\n"
    
    # Add signals
    if signal_text:
        data_context += f"\n## 技术信号{signal_text}\n"
    
    # Final prompt
    query = f"""请基于以下股票数据进行专业的技术分析，给出详细的分析报告和操作建议：

{data_context}

请从以下几个方面进行分析：
1. **趋势分析**: 结合均线系统和当前趋势判断后市走向
2. **动量分析**: 结合MACD、RSI、KDJ指标判断多空力量
3. **波动分析**: 结合布林带判断股价所处位置和波动空间
4. **综合建议**: 给出具体的操作建议和风险提示

注意：请引用具体的指标数值来支持你的分析结论。"""
    
    # Step 4: Call LLM with data context
    try:
        from stock_datasource.agents import get_market_agent
        
        agent = get_market_agent()
        result = await agent.execute(query, {"period": request.period})
        
        if result.success:
            return {
                "code": request.code,
                "analysis": result.response,
                "trend": trend,
                "signals": signals,
                "metadata": result.metadata
            }
        else:
            return {
                "code": request.code,
                "analysis": result.response,
                "trend": trend,
                "signals": signals,
                "error": True
            }
    except ImportError:
        # MarketAgent not available, return basic analysis summary
        logger.warning("MarketAgent not available, using basic analysis")
        return {
            "code": request.code,
            "analysis": trend_data.get("summary", ""),
            "trend": trend,
            "signals": signals
        }
    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        # Fallback: return basic analysis instead of error
        return {
            "code": request.code,
            "analysis": trend_data.get("summary", f"AI分析暂时不可用: {str(e)}"),
            "trend": trend,
            "signals": signals
        }


@router.get("/analysis/ai/stream")
async def ai_analyze_stock_stream(
    code: str = Query(..., description="Stock code"),
    period: int = Query(60, ge=10, le=365, description="Analysis period")
):
    """Stream AI analysis for a stock (SSE format).
    
    Returns Server-Sent Events with analysis progress and streaming content.
    """
    async def generate():
        try:
            service = get_market_service()
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': '正在获取股票数据...'})}\n\n"
            
            # Step 1: Get trend data
            try:
                trend_data = await service.analyze_trend(code, period)
            except Exception as e:
                logger.error(f"Failed to get trend data: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'获取股票数据失败: {str(e)}'})}\n\n"
                return
            
            yield f"data: {json.dumps({'type': 'status', 'message': '正在计算技术指标...'})}\n\n"
            
            # Step 2: Get indicator data
            try:
                indicator_data = await service.get_indicators(
                    code, 
                    ["MACD", "RSI", "KDJ", "BOLL", "MA"], 
                    period=period
                )
            except Exception as e:
                logger.warning(f"Failed to get indicators: {e}")
                indicator_data = {}
            
            # Step 3: Prepare data context
            stock_name = trend_data.get("name", code)
            trend = trend_data.get("trend", "未知")
            support = trend_data.get("support", 0)
            resistance = trend_data.get("resistance", 0)
            signals = trend_data.get("signals", [])
            
            yield f"data: {json.dumps({'type': 'status', 'message': '正在进行AI分析...'})}\n\n"
            
            # Extract latest indicator values
            indicators = indicator_data.get("indicators", {})
            latest_indicators = {}
            for key, values in indicators.items():
                if values and len(values) > 0:
                    for v in reversed(values):
                        if v is not None:
                            latest_indicators[key] = round(v, 2) if isinstance(v, float) else v
                            break
            
            # Format signals for prompt
            signal_text = ""
            if signals:
                bullish = [s for s in signals if s.get("type") == "bullish"]
                bearish = [s for s in signals if s.get("type") == "bearish"]
                if bullish:
                    signal_text += f"\n看多信号: {', '.join(s.get('signal', '') for s in bullish)}"
                if bearish:
                    signal_text += f"\n看空信号: {', '.join(s.get('signal', '') for s in bearish)}"
            
            # Build data context
            data_context = f"""
## 股票基础信息
- 股票代码: {code}
- 股票名称: {stock_name}
- 分析周期: {period}天

## 趋势判断
- 当前趋势: {trend}
- 支撑位: {support:.2f}
- 压力位: {resistance:.2f}

## 技术指标最新值
"""
            indicator_names = {
                "MACD_DIF": "MACD DIF",
                "MACD_DEA": "MACD DEA", 
                "MACD_HIST": "MACD 柱状",
                "RSI": "RSI",
                "KDJ_K": "KDJ K值",
                "KDJ_D": "KDJ D值",
                "KDJ_J": "KDJ J值",
                "BOLL_UPPER": "布林上轨",
                "BOLL_MID": "布林中轨",
                "BOLL_LOWER": "布林下轨",
                "MA5": "5日均线",
                "MA10": "10日均线",
                "MA20": "20日均线",
                "MA60": "60日均线",
            }
            
            for key, display_name in indicator_names.items():
                if key in latest_indicators:
                    data_context += f"- {display_name}: {latest_indicators[key]}\n"
            
            if signal_text:
                data_context += f"\n## 技术信号{signal_text}\n"
            
            query = f"""请基于以下股票数据进行专业的技术分析，给出详细的分析报告和操作建议：

{data_context}

请从以下几个方面进行分析：
1. **趋势分析**: 结合均线系统和当前趋势判断后市走向
2. **动量分析**: 结合MACD、RSI、KDJ指标判断多空力量
3. **波动分析**: 结合布林带判断股价所处位置和波动空间
4. **综合建议**: 给出具体的操作建议和风险提示

注意：请引用具体的指标数值来支持你的分析结论。"""
            
            # Step 4: Stream LLM response
            try:
                from stock_datasource.agents import get_market_agent
                
                agent = get_market_agent()
                
                # Stream the AI response
                async for event in agent.execute_stream(query, {"period": period}):
                    event_type = event.get("type", "")
                    
                    if event_type == "content":
                        content = event.get("content", "")
                        if content:
                            yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                    elif event_type == "tool_call":
                        tool_name = event.get("tool", "")
                        yield f"data: {json.dumps({'type': 'status', 'message': f'正在调用工具: {tool_name}'})}\n\n"
                    elif event_type == "done":
                        break
                
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                
            except ImportError:
                logger.warning("MarketAgent not available, using basic analysis")
                basic_summary = trend_data.get("summary", "AI分析模块未配置")
                yield f"data: {json.dumps({'type': 'content', 'content': basic_summary})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
            except Exception as e:
                logger.error(f"AI stream analysis failed: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'AI分析失败: {str(e)}'})}\n\n"
                
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
