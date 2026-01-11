"""Portfolio management API endpoints."""

import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Request/Response models
class PositionCreateRequest(BaseModel):
    """Request model for creating a position."""
    ts_code: str = Field(..., description="股票代码")
    quantity: int = Field(..., gt=0, description="持仓数量")
    cost_price: float = Field(..., gt=0, description="成本价")
    buy_date: str = Field(..., description="买入日期 (YYYY-MM-DD)")
    notes: Optional[str] = Field(None, description="备注")


class PositionUpdateRequest(BaseModel):
    """Request model for updating a position."""
    quantity: Optional[int] = Field(None, gt=0, description="持仓数量")
    cost_price: Optional[float] = Field(None, gt=0, description="成本价")
    notes: Optional[str] = Field(None, description="备注")


class PositionResponse(BaseModel):
    """Response model for position data."""
    id: str
    user_id: str
    ts_code: str
    stock_name: str
    quantity: int
    cost_price: float
    buy_date: str
    current_price: Optional[float]
    market_value: Optional[float]
    profit_loss: Optional[float]
    profit_rate: Optional[float]
    notes: Optional[str]
    sector: Optional[str]
    industry: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class PortfolioSummaryResponse(BaseModel):
    """Response model for portfolio summary."""
    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    daily_change: float
    daily_change_rate: float
    position_count: int
    risk_score: Optional[float]
    top_performer: Optional[str]
    worst_performer: Optional[str]
    sector_distribution: Optional[Dict[str, float]]


class AlertCreateRequest(BaseModel):
    """Request model for creating an alert."""
    position_id: str = Field(..., description="持仓ID")
    ts_code: str = Field(..., description="股票代码")
    alert_type: str = Field(..., description="预警类型: price_high, price_low, profit_target, stop_loss")
    condition_value: float = Field(..., description="预警条件值")
    message: Optional[str] = Field(None, description="预警消息")


class AlertResponse(BaseModel):
    """Response model for alert data."""
    id: str
    user_id: str
    position_id: str
    ts_code: str
    alert_type: str
    condition_value: float
    current_value: float
    is_triggered: bool
    is_active: bool
    trigger_count: int
    last_triggered: Optional[datetime]
    message: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AnalysisReportResponse(BaseModel):
    """Response model for analysis report."""
    id: str
    user_id: str
    report_date: date
    report_type: str
    market_analysis: str
    portfolio_summary: str
    individual_analysis: str
    risk_assessment: str
    recommendations: str
    ai_insights: str
    status: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AnalysisTriggerRequest(BaseModel):
    """Request model for triggering analysis."""
    analysis_date: Optional[str] = Field(None, description="分析日期 (YYYY-MM-DD), 默认为今天")


# Create router
router = APIRouter(prefix="/api/portfolio", tags=["Portfolio Management"])


@router.get("/positions", response_model=List[PositionResponse])
async def get_positions(
    user_id: str = Query("default_user", description="用户ID"),
    include_inactive: bool = Query(False, description="是否包含已删除的持仓")
):
    """获取持仓列表."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        positions = await service.get_positions(user_id, include_inactive)
        
        return [
            PositionResponse(
                id=pos.id,
                user_id=pos.user_id,
                ts_code=pos.ts_code,
                stock_name=pos.stock_name,
                quantity=pos.quantity,
                cost_price=pos.cost_price,
                buy_date=pos.buy_date,
                current_price=pos.current_price,
                market_value=pos.market_value,
                profit_loss=pos.profit_loss,
                profit_rate=pos.profit_rate,
                notes=pos.notes,
                sector=pos.sector,
                industry=pos.industry,
                is_active=pos.is_active,
                created_at=pos.created_at,
                updated_at=pos.updated_at
            )
            for pos in positions
        ]
        
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/positions", response_model=PositionResponse)
async def create_position(
    request: PositionCreateRequest,
    user_id: str = Query("default_user", description="用户ID")
):
    """添加新持仓."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        position = await service.add_position(
            user_id=user_id,
            ts_code=request.ts_code,
            quantity=request.quantity,
            cost_price=request.cost_price,
            buy_date=request.buy_date,
            notes=request.notes
        )
        
        return PositionResponse(
            id=position.id,
            user_id=position.user_id,
            ts_code=position.ts_code,
            stock_name=position.stock_name,
            quantity=position.quantity,
            cost_price=position.cost_price,
            buy_date=position.buy_date,
            current_price=position.current_price,
            market_value=position.market_value,
            profit_loss=position.profit_loss,
            profit_rate=position.profit_rate,
            notes=position.notes,
            sector=position.sector,
            industry=position.industry,
            is_active=position.is_active,
            created_at=position.created_at,
            updated_at=position.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/positions/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: str = Path(..., description="持仓ID"),
    request: PositionUpdateRequest = Body(...),
    user_id: str = Query("default_user", description="用户ID")
):
    """更新持仓信息."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        
        # Build update dict from request
        updates = {}
        if request.quantity is not None:
            updates['quantity'] = request.quantity
        if request.cost_price is not None:
            updates['cost_price'] = request.cost_price
        if request.notes is not None:
            updates['notes'] = request.notes
        
        position = await service.update_position(position_id, user_id, **updates)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        return PositionResponse(
            id=position.id,
            user_id=position.user_id,
            ts_code=position.ts_code,
            stock_name=position.stock_name,
            quantity=position.quantity,
            cost_price=position.cost_price,
            buy_date=position.buy_date,
            current_price=position.current_price,
            market_value=position.market_value,
            profit_loss=position.profit_loss,
            profit_rate=position.profit_rate,
            notes=position.notes,
            sector=position.sector,
            industry=position.industry,
            is_active=position.is_active,
            created_at=position.created_at,
            updated_at=position.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{position_id}")
async def delete_position(
    position_id: str = Path(..., description="持仓ID"),
    user_id: str = Query("default_user", description="用户ID")
):
    """删除持仓."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        success = await service.delete_position(position_id, user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Position not found")
        
        return {"message": "Position deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def get_portfolio_summary(
    user_id: str = Query("default_user", description="用户ID")
):
    """获取投资组合汇总."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        summary = await service.get_summary(user_id)
        
        return PortfolioSummaryResponse(
            total_value=summary.total_value,
            total_cost=summary.total_cost,
            total_profit=summary.total_profit,
            profit_rate=summary.profit_rate,
            daily_change=summary.daily_change,
            daily_change_rate=summary.daily_change_rate,
            position_count=summary.position_count,
            risk_score=summary.risk_score,
            top_performer=summary.top_performer,
            worst_performer=summary.worst_performer,
            sector_distribution=summary.sector_distribution
        )
        
    except Exception as e:
        logger.error(f"Failed to get portfolio summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profit-history")
async def get_profit_history(
    user_id: str = Query("default_user", description="用户ID"),
    days: int = Query(30, ge=1, le=365, description="历史天数")
):
    """获取盈亏历史."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        history = await service.get_profit_history(user_id, days)
        
        return {"data": history}
        
    except Exception as e:
        logger.error(f"Failed to get profit history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/daily-analysis")
async def trigger_daily_analysis(
    request: AnalysisTriggerRequest,
    user_id: str = Query("default_user", description="用户ID")
):
    """触发每日分析."""
    try:
        from stock_datasource.services.daily_analysis_service import get_daily_analysis_service
        
        service = get_daily_analysis_service()
        
        analysis_date = None
        if request.analysis_date:
            analysis_date = datetime.strptime(request.analysis_date, "%Y-%m-%d").date()
        
        report = await service.run_daily_analysis(user_id, analysis_date)
        
        return {
            "message": "Analysis triggered successfully",
            "report_id": report.id,
            "status": report.status
        }
        
    except Exception as e:
        logger.error(f"Failed to trigger daily analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{report_date}", response_model=AnalysisReportResponse)
async def get_analysis_report(
    report_date: str = Path(..., description="报告日期 (YYYY-MM-DD)"),
    user_id: str = Query("default_user", description="用户ID")
):
    """获取分析报告."""
    try:
        from stock_datasource.services.daily_analysis_service import get_daily_analysis_service
        
        service = get_daily_analysis_service()
        analysis_date = datetime.strptime(report_date, "%Y-%m-%d").date()
        
        report = await service.get_analysis_report(user_id, analysis_date)
        
        if not report:
            raise HTTPException(status_code=404, detail="Analysis report not found")
        
        return AnalysisReportResponse(
            id=report.id,
            user_id=report.user_id,
            report_date=report.report_date,
            report_type=report.report_type,
            market_analysis=report.market_analysis,
            portfolio_summary=report.portfolio_summary,
            individual_analysis=report.individual_analysis,
            risk_assessment=report.risk_assessment,
            recommendations=report.recommendations,
            ai_insights=report.ai_insights,
            status=report.status,
            created_at=report.created_at,
            updated_at=report.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get analysis report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis", response_model=List[AnalysisReportResponse])
async def get_analysis_history(
    user_id: str = Query("default_user", description="用户ID"),
    days: int = Query(30, ge=1, le=365, description="历史天数")
):
    """获取分析报告历史."""
    try:
        from stock_datasource.services.daily_analysis_service import get_daily_analysis_service
        
        service = get_daily_analysis_service()
        reports = await service.get_analysis_history(user_id, days)
        
        return [
            AnalysisReportResponse(
                id=report.id,
                user_id=report.user_id,
                report_date=report.report_date,
                report_type=report.report_type,
                market_analysis=report.market_analysis,
                portfolio_summary=report.portfolio_summary,
                individual_analysis=report.individual_analysis,
                risk_assessment=report.risk_assessment,
                recommendations=report.recommendations,
                ai_insights=report.ai_insights,
                status=report.status,
                created_at=report.created_at,
                updated_at=report.updated_at
            )
            for report in reports
        ]
        
    except Exception as e:
        logger.error(f"Failed to get analysis history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts", response_model=AlertResponse)
async def create_alert(
    request: AlertCreateRequest,
    user_id: str = Query("default_user", description="用户ID")
):
    """创建持仓预警."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        alert = await service.create_alert(
            user_id=user_id,
            position_id=request.position_id,
            ts_code=request.ts_code,
            alert_type=request.alert_type,
            condition_value=request.condition_value,
            message=request.message or ""
        )
        
        return AlertResponse(
            id=alert.id,
            user_id=alert.user_id,
            position_id=alert.position_id,
            ts_code=alert.ts_code,
            alert_type=alert.alert_type,
            condition_value=alert.condition_value,
            current_value=alert.current_value,
            is_triggered=alert.is_triggered,
            is_active=alert.is_active,
            trigger_count=alert.trigger_count,
            last_triggered=alert.last_triggered,
            message=alert.message,
            created_at=alert.created_at,
            updated_at=alert.updated_at
        )
        
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/check")
async def check_alerts(
    user_id: str = Query("default_user", description="用户ID")
):
    """检查预警触发."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        triggered_alerts = await service.check_alerts(user_id)
        
        return {
            "triggered_count": len(triggered_alerts),
            "alerts": [
                {
                    "id": alert.id,
                    "ts_code": alert.ts_code,
                    "alert_type": alert.alert_type,
                    "condition_value": alert.condition_value,
                    "current_value": alert.current_value,
                    "message": alert.message
                }
                for alert in triggered_alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to check alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch/update-prices")
async def batch_update_prices(
    user_id: str = Query("default_user", description="用户ID")
):
    """批量更新持仓价格."""
    try:
        from stock_datasource.modules.portfolio.enhanced_service import get_enhanced_portfolio_service
        
        service = get_enhanced_portfolio_service()
        updated_count = await service.batch_update_prices(user_id)
        
        return {
            "message": f"Updated prices for {updated_count} positions",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Failed to batch update prices: {e}")
        raise HTTPException(status_code=500, detail=str(e))