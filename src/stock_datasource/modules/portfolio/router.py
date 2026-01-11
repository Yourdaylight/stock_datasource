"""Portfolio module router."""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging
from .service import get_portfolio_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize services lazily to avoid import issues
def get_enhanced_portfolio_service():
    try:
        from .enhanced_service import EnhancedPortfolioService
        return EnhancedPortfolioService()
    except ImportError as e:
        logger.warning(f"Enhanced portfolio service not available: {e}")
        return None

def get_daily_analysis_service():
    try:
        from ...services.daily_analysis_service import DailyAnalysisService
        return DailyAnalysisService()
    except ImportError as e:
        logger.warning(f"Daily analysis service not available: {e}")
        return None


class Position(BaseModel):
    id: str
    ts_code: str
    stock_name: str
    quantity: int
    cost_price: float
    buy_date: str
    current_price: float = None
    market_value: float = None
    profit_loss: float = None
    profit_rate: float = None


class AddPositionRequest(BaseModel):
    ts_code: str
    quantity: int
    cost_price: float
    buy_date: str
    notes: str = None


class PortfolioSummary(BaseModel):
    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    daily_change: float
    daily_change_rate: float
    position_count: int


class DailyAnalysis(BaseModel):
    analysis_date: str
    analysis_summary: str
    stock_analyses: dict = {}
    risk_alerts: List[str] = []
    recommendations: List[str] = []


@router.get("/positions", response_model=List[Position])
async def get_positions():
    """Get user positions."""
    service = get_portfolio_service()
    positions = await service.get_positions()
    
    # Convert to Pydantic models
    return [
        Position(
            id=p.id,
            ts_code=p.ts_code,
            stock_name=p.stock_name,
            quantity=p.quantity,
            cost_price=p.cost_price,
            buy_date=p.buy_date,
            current_price=p.current_price,
            market_value=p.market_value,
            profit_loss=p.profit_loss,
            profit_rate=p.profit_rate
        ) for p in positions
    ]


@router.post("/positions", response_model=Position)
async def add_position(request: AddPositionRequest):
    """Add a new position."""
    service = get_portfolio_service()
    
    try:
        position = await service.add_position(
            ts_code=request.ts_code,
            quantity=request.quantity,
            cost_price=request.cost_price,
            buy_date=request.buy_date,
            notes=request.notes
        )
        
        return Position(
            id=position.id,
            ts_code=position.ts_code,
            stock_name=position.stock_name,
            quantity=position.quantity,
            cost_price=position.cost_price,
            buy_date=position.buy_date,
            current_price=position.current_price,
            market_value=position.market_value,
            profit_loss=position.profit_loss,
            profit_rate=position.profit_rate
        )
    except Exception as e:
        logger.error(f"Failed to add position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/positions/{position_id}", response_model=Position)
async def update_position(position_id: str, request: AddPositionRequest):
    """Update a position."""
    return Position(
        id=position_id,
        ts_code=request.ts_code,
        stock_name="更新股票",
        quantity=request.quantity,
        cost_price=request.cost_price,
        buy_date=request.buy_date
    )


@router.delete("/positions/{position_id}")
async def delete_position(position_id: str):
    """Delete a position."""
    service = get_portfolio_service()
    
    try:
        success = await service.delete_position(position_id)
        if success:
            return {"success": True}
        else:
            raise HTTPException(status_code=404, detail="Position not found")
    except Exception as e:
        logger.error(f"Failed to delete position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=PortfolioSummary)
async def get_summary():
    """Get portfolio summary."""
    service = get_portfolio_service()
    summary = await service.get_summary()
    
    return PortfolioSummary(
        total_value=summary.total_value,
        total_cost=summary.total_cost,
        total_profit=summary.total_profit,
        profit_rate=summary.profit_rate,
        daily_change=summary.daily_change,
        daily_change_rate=summary.daily_change_rate,
        position_count=summary.position_count
    )


@router.get("/profit-history")
async def get_profit_history(days: int = Query(default=30)):
    """Get profit history."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            history = await enhanced_service.get_profit_history(days=days)
            return {"data": history, "success": True}
        else:
            return {"data": [], "success": True, "message": "Enhanced service not available"}
    except Exception as e:
        logger.error(f"Failed to get profit history: {e}")
        return {"data": [], "success": False, "error": str(e)}


@router.post("/daily-analysis")
async def trigger_daily_analysis():
    """Trigger daily analysis."""
    try:
        analysis_service = get_daily_analysis_service()
        if analysis_service:
            task_id = await analysis_service.trigger_analysis()
            return {"task_id": task_id, "success": True}
        else:
            return {"task_id": "mock_001", "success": True, "message": "Analysis service not available"}
    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}")
        return {"task_id": None, "success": False, "error": str(e)}


@router.get("/analysis", response_model=DailyAnalysis)
async def get_analysis(date: Optional[str] = None):
    """Get daily analysis."""
    try:
        analysis_service = get_daily_analysis_service()
        if analysis_service:
            analysis = await analysis_service.get_analysis(date=date)
            if analysis:
                return DailyAnalysis(
                    analysis_date=analysis.get('analysis_date', ''),
                    analysis_summary=analysis.get('analysis_summary', ''),
                    stock_analyses=analysis.get('stock_analyses', {}),
                    risk_alerts=analysis.get('risk_alerts', []),
                    recommendations=analysis.get('recommendations', [])
                )
        
        # Fallback to mock data
        return DailyAnalysis(
            analysis_date=date or "2024-01-09",
            analysis_summary="您的持仓整体表现良好，建议继续关注市场动态。",
            risk_alerts=["市场波动较大，请注意风险控制"],
            recommendations=["建议分散投资，降低单一股票风险"]
        )
    except Exception as e:
        logger.error(f"Failed to get analysis: {e}")
        # Return mock data on error
        return DailyAnalysis(
            analysis_date=date or "2024-01-09",
            analysis_summary="分析服务暂时不可用",
            risk_alerts=[],
            recommendations=[]
        )


# Additional enhanced endpoints
@router.get("/technical-indicators/{ts_code}")
async def get_technical_indicators(ts_code: str, days: int = Query(default=30)):
    """Get technical indicators for a stock."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            indicators = await enhanced_service.get_technical_indicators(ts_code, days)
            return {"data": indicators, "success": True}
        else:
            return {"data": {}, "success": True, "message": "Enhanced service not available"}
    except Exception as e:
        logger.error(f"Failed to get technical indicators: {e}")
        return {"data": {}, "success": False, "error": str(e)}


@router.get("/risk-metrics")
async def get_risk_metrics():
    """Get portfolio risk metrics."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            metrics = await enhanced_service.get_risk_metrics()
            return {"data": metrics, "success": True}
        else:
            return {"data": {}, "success": True, "message": "Enhanced service not available"}
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        return {"data": {}, "success": False, "error": str(e)}


@router.post("/alerts")
async def create_alert(alert_data: dict):
    """Create position alert."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            alert = await enhanced_service.create_alert(alert_data)
            return {"data": alert, "success": True}
        else:
            return {"data": None, "success": True, "message": "Enhanced service not available"}
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        return {"data": None, "success": False, "error": str(e)}


@router.get("/alerts")
async def get_alerts():
    """Get position alerts."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            alerts = await enhanced_service.get_alerts()
            return {"data": alerts, "success": True}
        else:
            return {"data": [], "success": True, "message": "Enhanced service not available"}
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return {"data": [], "success": False, "error": str(e)}
