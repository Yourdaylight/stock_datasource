"""Portfolio module router."""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel
import logging
from .service import get_portfolio_service

logger = logging.getLogger(__name__)

router = APIRouter()


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
    return []


@router.post("/daily-analysis")
async def trigger_daily_analysis():
    """Trigger daily analysis."""
    return {"task_id": "analysis_001"}


@router.get("/analysis", response_model=DailyAnalysis)
async def get_analysis(date: Optional[str] = None):
    """Get daily analysis."""
    return DailyAnalysis(
        analysis_date="2024-01-09",
        analysis_summary="您的持仓整体表现良好，贵州茅台今日上涨1%，技术指标显示短期趋势向好。",
        risk_alerts=["贵州茅台已接近目标价位，建议关注"],
        recommendations=["建议继续持有贵州茅台", "可考虑适当分散投资"]
    )
