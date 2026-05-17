"""Portfolio module router.

All endpoints require authentication via JWT token.
User isolation is enforced by extracting user_id from the authenticated token.
"""

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
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
    daily_change: float | None = None
    daily_pct_chg: float | None = None
    prev_close: float | None = None
    notes: str | None = None
    price_update_time: str | None = None


class AddPositionRequest(BaseModel):
    ts_code: str
    quantity: int
    cost_price: float
    buy_date: str
    notes: str = None


class UpdatePositionRequest(BaseModel):
    """Request model for updating a position."""

    quantity: int | None = Field(None, gt=0, description="持仓数量")
    cost_price: float | None = Field(None, gt=0, description="成本价")
    notes: str | None = Field(None, description="备注")


class BuyTransactionRequest(BaseModel):
    """Request model for buy transaction."""

    ts_code: str = Field(..., description="股票代码")
    quantity: int = Field(..., gt=0, description="买入数量")
    price: float = Field(..., gt=0, description="买入价格")
    transaction_date: str = Field(..., description="交易日期")
    notes: str | None = Field(None, description="备注")
    profile_id: str | None = Field(None, description="账户ID")


class SellTransactionRequest(BaseModel):
    """Request model for sell transaction."""

    ts_code: str = Field(..., description="股票代码")
    quantity: int = Field(..., gt=0, description="卖出数量")
    price: float = Field(..., gt=0, description="卖出价格")
    transaction_date: str = Field(..., description="交易日期")
    notes: str | None = Field(None, description="备注")
    profile_id: str | None = Field(None, description="账户ID")


class TransactionResponse(BaseModel):
    """Response model for transaction."""

    id: str
    user_id: str
    ts_code: str
    stock_name: str
    transaction_type: str
    quantity: int
    price: float
    transaction_date: str
    position_id: str
    realized_pl: float | None = None
    notes: str = ""
    profile_id: str = "default"
    created_at: str | None = None


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
    risk_alerts: list[str] = []
    recommendations: list[str] = []


@router.get("/positions", response_model=list[Position])
async def get_positions(
    include_inactive: bool = Query(False, description="是否包含已删除的持仓"),
    current_user: dict = Depends(get_current_user),
):
    """Get user positions.

    User isolation: Only returns positions belonging to the authenticated user.
    """
    service = get_portfolio_service()
    positions = await service.get_positions(user_id=current_user["id"])

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
            profit_rate=p.profit_rate,
            daily_change=getattr(p, "daily_change", None),
            daily_pct_chg=getattr(p, "daily_pct_chg", None),
            prev_close=getattr(p, "prev_close", None),
            notes=p.notes,
            price_update_time=p.price_update_time,
        )
        for p in positions
    ]


@router.post("/positions", response_model=Position)
async def add_position(
    request: AddPositionRequest, current_user: dict = Depends(get_current_user)
):
    """Add a new position.

    User isolation: Position is created under the authenticated user's account.
    """
    service = get_portfolio_service()

    try:
        position = await service.add_position(
            ts_code=request.ts_code,
            quantity=request.quantity,
            cost_price=request.cost_price,
            buy_date=request.buy_date,
            notes=request.notes,
            user_id=current_user["id"],
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
            profit_rate=position.profit_rate,
            daily_change=getattr(position, "daily_change", None),
            daily_pct_chg=getattr(position, "daily_pct_chg", None),
            prev_close=getattr(position, "prev_close", None),
            notes=position.notes,
            price_update_time=position.price_update_time,
        )
    except Exception as e:
        logger.error(f"Failed to add position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/positions/{position_id}", response_model=Position)
async def update_position(
    position_id: str = Path(..., description="持仓ID"),
    request: UpdatePositionRequest = Body(...),
    current_user: dict = Depends(get_current_user),
):
    """Update a position.

    User isolation: Only updates position if it belongs to the authenticated user.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            # Build update dict from request
            updates = {}
            if request.quantity is not None:
                updates["quantity"] = request.quantity
            if request.cost_price is not None:
                updates["cost_price"] = request.cost_price
            if request.notes is not None:
                updates["notes"] = request.notes

            position = await enhanced_service.update_position(
                position_id,
                current_user["id"],  # Ensure user owns the position
                **updates,
            )

            if not position:
                raise HTTPException(
                    status_code=404, detail="Position not found or not owned by user"
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
                profit_rate=position.profit_rate,
                daily_change=getattr(position, "daily_change", None),
                daily_pct_chg=getattr(position, "daily_pct_chg", None),
                prev_close=getattr(position, "prev_close", None),
                notes=position.notes,
                price_update_time=position.last_price_update.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                if hasattr(position, "last_price_update") and position.last_price_update
                else (
                    position.price_update_time
                    if hasattr(position, "price_update_time")
                    else None
                ),
            )
        else:
            raise HTTPException(
                status_code=503, detail="Enhanced service not available"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/positions/{position_id}")
async def delete_position(
    position_id: str, current_user: dict = Depends(get_current_user)
):
    """Delete a position.

    User isolation: Only deletes position if it belongs to the authenticated user.
    """
    service = get_portfolio_service()

    try:
        success = await service.delete_position(position_id, user_id=current_user["id"])
        if success:
            return {"success": True, "message": "Position deleted successfully"}
        else:
            raise HTTPException(
                status_code=404, detail="Position not found or not owned by user"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_summary(current_user: dict = Depends(get_current_user)):
    """Get portfolio summary.

    User isolation: Only calculates summary for the authenticated user's positions.
    """
    service = get_portfolio_service()
    summary = await service.get_summary(user_id=current_user["id"])

    return {
        "total_value": summary.total_value,
        "total_cost": summary.total_cost,
        "total_profit": summary.total_profit,
        "profit_rate": summary.profit_rate,
        "daily_change": summary.daily_change,
        "daily_change_rate": summary.daily_change_rate,
        "position_count": summary.position_count,
    }


@router.get("/profit-history")
async def get_profit_history(
    days: int = Query(default=30), current_user: dict = Depends(get_current_user)
):
    """Get profit history."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            history = await enhanced_service.get_profit_history(
                days=days, user_id=current_user["id"]
            )
            return {"data": history, "success": True}
        else:
            return {
                "data": [],
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to get profit history: {e}")
        return {"data": [], "success": False, "error": str(e)}


@router.post("/daily-analysis")
async def trigger_daily_analysis(current_user: dict = Depends(get_current_user)):
    """Trigger daily analysis."""
    try:
        analysis_service = get_daily_analysis_service()
        if analysis_service:
            task_id = await analysis_service.trigger_analysis(
                user_id=current_user["id"]
            )
            return {"task_id": task_id, "success": True}
        else:
            return {
                "task_id": "mock_001",
                "success": True,
                "message": "Analysis service not available",
            }
    except Exception as e:
        logger.error(f"Failed to trigger analysis: {e}")
        return {"task_id": None, "success": False, "error": str(e)}


@router.get("/analysis", response_model=DailyAnalysis)
async def get_analysis(
    date: str | None = None, current_user: dict = Depends(get_current_user)
):
    """Get daily analysis."""
    try:
        analysis_service = get_daily_analysis_service()
        if analysis_service:
            analysis = await analysis_service.get_analysis(date=date)
            if analysis:
                return DailyAnalysis(
                    analysis_date=analysis.get("analysis_date", ""),
                    analysis_summary=analysis.get("analysis_summary", ""),
                    stock_analyses=analysis.get("stock_analyses", {}),
                    risk_alerts=analysis.get("risk_alerts", []),
                    recommendations=analysis.get("recommendations", []),
                )

        # Fallback to mock data
        from datetime import datetime

        return DailyAnalysis(
            analysis_date=date or str(datetime.now().date()),
            analysis_summary="您的持仓整体表现良好，建议继续关注市场动态。",
            stock_analyses={
                "600519.SH": {
                    "stock_name": "贵州茅台",
                    "current_price": 1800.0,
                    "profit_rate": 5.88,
                    "recommendation": "hold",
                    "key_points": ["当前盈利5.9%，表现良好", "技术面表现强势"],
                }
            },
            risk_alerts=["市场波动较大，请注意风险控制"],
            recommendations=["建议分散投资，降低单一股票风险"],
        )
    except Exception as e:
        logger.error(f"Failed to get analysis: {e}")
        # Return mock data on error
        from datetime import datetime

        return DailyAnalysis(
            analysis_date=date or str(datetime.now().date()),
            analysis_summary="您的持仓整体表现良好，建议继续关注市场动态。",
            stock_analyses={
                "600519.SH": {
                    "stock_name": "贵州茅台",
                    "current_price": 1800.0,
                    "profit_rate": 5.88,
                    "recommendation": "hold",
                    "key_points": ["当前盈利5.9%，表现良好", "技术面表现强势"],
                }
            },
            risk_alerts=["市场波动较大，请注意风险控制"],
            recommendations=["建议分散投资，降低单一股票风险", "关注市场政策变化"],
        )


# Additional enhanced endpoints
@router.get("/technical-indicators/{ts_code}")
async def get_technical_indicators(
    ts_code: str,
    days: int = Query(default=30),
    current_user: dict = Depends(get_current_user),
):
    """Get technical indicators for a stock."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            indicators = await enhanced_service.get_technical_indicators(ts_code, days)
            return {"data": indicators, "success": True}
        else:
            return {
                "data": {},
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to get technical indicators: {e}")
        return {"data": {}, "success": False, "error": str(e)}


@router.get("/risk-metrics")
async def get_risk_metrics(current_user: dict = Depends(get_current_user)):
    """Get portfolio risk metrics."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            metrics = await enhanced_service.get_risk_metrics(
                user_id=current_user["id"]
            )
            return {"data": metrics, "success": True}
        else:
            return {
                "data": {},
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        return {"data": {}, "success": False, "error": str(e)}


@router.post("/alerts")
async def create_alert(
    alert_data: dict, current_user: dict = Depends(get_current_user)
):
    """Create position alert."""
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            alert_data["user_id"] = current_user["id"]
            alert = await enhanced_service.create_alert(alert_data)
            return {"data": alert, "success": True}
        else:
            return {
                "data": None,
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        return {"data": None, "success": False, "error": str(e)}


@router.get("/alerts")
async def get_alerts(current_user: dict = Depends(get_current_user)):
    """Get position alerts.

    User isolation: Only returns alerts belonging to the authenticated user.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            alerts = await enhanced_service.get_alerts(user_id=current_user["id"])
            return {"data": alerts, "success": True}
        else:
            return {
                "data": [],
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        return {"data": [], "success": False, "error": str(e)}


@router.get("/alerts/check")
async def check_alerts(current_user: dict = Depends(get_current_user)):
    """Check for triggered alerts.

    User isolation: Only checks alerts belonging to the authenticated user.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            triggered_alerts = await enhanced_service.check_alerts(
                user_id=current_user["id"]
            )
            return {
                "triggered_count": len(triggered_alerts) if triggered_alerts else 0,
                "alerts": [
                    {
                        "id": alert.id,
                        "ts_code": alert.ts_code,
                        "alert_type": alert.alert_type,
                        "condition_value": alert.condition_value,
                        "current_value": alert.current_value,
                        "message": alert.message,
                    }
                    for alert in (triggered_alerts or [])
                ],
                "success": True,
            }
        else:
            return {
                "triggered_count": 0,
                "alerts": [],
                "success": True,
                "message": "Enhanced service not available",
            }
    except Exception as e:
        logger.error(f"Failed to check alerts: {e}")
        return {"triggered_count": 0, "alerts": [], "success": False, "error": str(e)}


@router.post("/batch/update-prices")
async def batch_update_prices(current_user: dict = Depends(get_current_user)):
    """Batch update position prices.

    User isolation: Only updates prices for the authenticated user's positions.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if enhanced_service:
            updated_count = await enhanced_service.batch_update_prices(
                user_id=current_user["id"]
            )
            return {
                "message": f"Updated prices for {updated_count} positions",
                "updated_count": updated_count,
                "success": True,
            }
        else:
            return {
                "message": "Enhanced service not available",
                "updated_count": 0,
                "success": True,
            }
    except Exception as e:
        logger.error(f"Failed to batch update prices: {e}")
        return {
            "message": str(e),
            "updated_count": 0,
            "success": False,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Transaction endpoints (buy/sell transaction history)
# ---------------------------------------------------------------------------


@router.post("/transactions/buy", response_model=TransactionResponse)
async def buy_transaction(
    request: BuyTransactionRequest, current_user: dict = Depends(get_current_user)
):
    """Record a buy transaction and update/create position.

    User isolation: Transaction is recorded under the authenticated user's account.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if not enhanced_service:
            raise HTTPException(status_code=503, detail="Enhanced service not available")

        txn = await enhanced_service.record_buy_transaction(
            user_id=current_user["id"],
            ts_code=request.ts_code,
            quantity=request.quantity,
            price=request.price,
            transaction_date=request.transaction_date,
            notes=request.notes,
            profile_id=request.profile_id or "default",
        )

        return TransactionResponse(
            id=txn.id,
            user_id=txn.user_id,
            ts_code=txn.ts_code,
            stock_name=txn.stock_name,
            transaction_type=txn.transaction_type,
            quantity=txn.quantity,
            price=txn.price,
            transaction_date=txn.transaction_date,
            position_id=txn.position_id,
            realized_pl=txn.realized_pl,
            notes=txn.notes,
            profile_id=txn.profile_id,
            created_at=str(txn.created_at) if txn.created_at else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record buy transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transactions/sell", response_model=TransactionResponse)
async def sell_transaction(
    request: SellTransactionRequest, current_user: dict = Depends(get_current_user)
):
    """Record a sell transaction and update position.

    User isolation: Transaction is recorded under the authenticated user's account.
    Validates that the user has sufficient shares to sell.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if not enhanced_service:
            raise HTTPException(status_code=503, detail="Enhanced service not available")

        txn = await enhanced_service.record_sell_transaction(
            user_id=current_user["id"],
            ts_code=request.ts_code,
            quantity=request.quantity,
            price=request.price,
            transaction_date=request.transaction_date,
            notes=request.notes,
            profile_id=request.profile_id or "default",
        )

        return TransactionResponse(
            id=txn.id,
            user_id=txn.user_id,
            ts_code=txn.ts_code,
            stock_name=txn.stock_name,
            transaction_type=txn.transaction_type,
            quantity=txn.quantity,
            price=txn.price,
            transaction_date=txn.transaction_date,
            position_id=txn.position_id,
            realized_pl=txn.realized_pl,
            notes=txn.notes,
            profile_id=txn.profile_id,
            created_at=str(txn.created_at) if txn.created_at else None,
        )
    except ValueError as e:
        logger.warning(f"Sell validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to record sell transaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    ts_code: str | None = Query(None, description="Filter by stock code"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    profile_id: str | None = Query(None, description="Filter by profile ID"),
    current_user: dict = Depends(get_current_user),
):
    """Get transaction history for the authenticated user.

    User isolation: Only returns transactions belonging to the authenticated user.
    Supports filtering by stock code and date range.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if not enhanced_service:
            raise HTTPException(status_code=503, detail="Enhanced service not available")

        transactions = await enhanced_service.get_transactions(
            user_id=current_user["id"],
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            profile_id=profile_id,
        )

        return [
            TransactionResponse(
                id=txn.id,
                user_id=txn.user_id,
                ts_code=txn.ts_code,
                stock_name=txn.stock_name,
                transaction_type=txn.transaction_type,
                quantity=txn.quantity,
                price=txn.price,
                transaction_date=txn.transaction_date,
                position_id=txn.position_id,
                realized_pl=txn.realized_pl,
                notes=txn.notes,
                profile_id=txn.profile_id,
                created_at=str(txn.created_at) if txn.created_at else None,
            )
            for txn in transactions
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TransactionSignalResponse(BaseModel):
    """A buy/sell signal point for K-line chart markers."""
    id: str
    ts_code: str
    signal_type: str = Field(..., description="'buy' or 'sell'")
    source: str = Field(..., description="'user' or 'strategy'")
    signal_date: str
    price: float
    quantity: int | None = None
    strategy_name: str | None = None
    notes: str | None = None


@router.get("/transactions/signals", response_model=list[TransactionSignalResponse])
async def get_transaction_signals(
    ts_code: str = Query(..., description="Stock code (required)"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    current_user: dict = Depends(get_current_user),
):
    """Get buy/sell signal points for K-line chart markers.

    Combines:
    - User transaction signals (actual buy/sell records)
    - Technical strategy signals (from indicator analysis)

    Returns a unified list of signals suitable for rendering B/S markers
    on K-line charts with different styles per source.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if not enhanced_service:
            raise HTTPException(status_code=503, detail="Enhanced service not available")

        signals: list[TransactionSignalResponse] = []

        # 1. User transaction signals
        transactions = await enhanced_service.get_transactions(
            user_id=current_user["id"],
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
        )

        for txn in transactions:
            signals.append(TransactionSignalResponse(
                id=f"user_{txn.id}",
                ts_code=txn.ts_code,
                signal_type=txn.transaction_type,
                source="user",
                signal_date=txn.transaction_date,
                price=txn.price,
                quantity=txn.quantity,
                notes=f"{txn.transaction_type.upper()} {txn.quantity}@{txn.price}",
            ))

        # 2. Strategy signals from technical indicators
        try:
            indicators = await enhanced_service.get_technical_indicators(ts_code, 180)
            strategy_signals = _extract_strategy_signals(ts_code, indicators)
            signals.extend(strategy_signals)
        except Exception as e:
            logger.debug(f"Strategy signals not available for {ts_code}: {e}")

        # Sort by signal_date
        signals.sort(key=lambda s: s.signal_date)

        return signals
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get transaction signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class KlinePatternResponse(BaseModel):
    """A detected candlestick pattern."""
    name: str = Field(..., description="Pattern name (Chinese)")
    name_en: str = Field(..., description="Pattern name (English)")
    date: str = Field(..., description="Date of the pattern (last candle)")
    type: str = Field(..., description="'bullish', 'bearish', or 'neutral'")
    category: str = Field(..., description="'single', 'dual', or 'triple'")


@router.get("/kline-patterns/{ts_code}", response_model=list[KlinePatternResponse])
async def get_kline_patterns(
    ts_code: str = Path(..., description="Stock code"),
    days: int = Query(default=60, description="Number of days to analyze"),
    current_user: dict = Depends(get_current_user),
):
    """Detect candlestick patterns in K-line data for a stock.

    Fetches OHLC data and runs pattern recognition to identify
    single, dual, and triple candlestick patterns.
    """
    try:
        enhanced_service = get_enhanced_portfolio_service()
        if not enhanced_service:
            raise HTTPException(status_code=503, detail="Enhanced service not available")

        patterns = await enhanced_service.get_kline_patterns(ts_code, days)
        return [
            KlinePatternResponse(
                name=p["name"],
                name_en=p["name_en"],
                date=p["date"],
                type=p["type"],
                category=p["category"],
            )
            for p in patterns
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get kline patterns for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _extract_strategy_signals(
    ts_code: str, indicators: dict
) -> list[TransactionSignalResponse]:
    """Extract buy/sell signals from technical indicator data.

    Converts technical signals (MACD crossover, RSI overbought/oversold, etc.)
    into TransactionSignalResponse items with source='strategy'.
    """
    signals: list[TransactionSignalResponse] = []
    signals_data = indicators.get("signals", [])

    for idx, sig in enumerate(signals_data):
        signal_type = "buy" if sig.get("type") in ("buy", "golden_cross", "oversold") else "sell"
        signals.append(TransactionSignalResponse(
            id=f"strategy_{idx}",
            ts_code=ts_code,
            signal_type=signal_type,
            source="strategy",
            signal_date=sig.get("date", ""),
            price=float(sig.get("price", 0)),
            strategy_name=sig.get("name", sig.get("type", "technical")),
            notes=sig.get("message", ""),
        ))

    return signals


# =============================================================================
# Watchlist (自选股) Endpoints
# =============================================================================


@router.get("/watchlist")
async def get_watchlist(current_user: dict = Depends(get_current_user)):
    """Get user's watchlist (自选股)."""
    from stock_datasource.models.database import db_client

    try:
        db_client.execute(
            "CREATE TABLE IF NOT EXISTS user_watchlist ("
            "user_id String, ts_code String, stock_name String DEFAULT '', "
            "added_at DateTime DEFAULT now(), source String DEFAULT 'manual', "
            "notes String DEFAULT ''"
            ") ENGINE = ReplacingMergeTree(added_at) ORDER BY (user_id, ts_code)"
        )
        rows = db_client.execute(
            "SELECT ts_code, stock_name, added_at, source, notes "
            "FROM user_watchlist FINAL WHERE user_id = %(uid)s ORDER BY added_at DESC",
            {"uid": current_user["id"]},
        )
        data = []
        for r in rows:
            try:
                data.append({
                    "ts_code": r[0] if len(r) > 0 else "",
                    "stock_name": r[1] if len(r) > 1 else "",
                    "added_at": str(r[2]) if len(r) > 2 else "",
                    "source": r[3] if len(r) > 3 else "",
                    "notes": r[4] if len(r) > 4 else "",
                })
            except (IndexError, TypeError):
                continue
        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Failed to get watchlist: {e}")
        return {"success": False, "data": [], "error": str(e)}


@router.post("/watchlist")
async def add_to_watchlist(
    ts_code: str = Query(..., description="股票代码"),
    stock_name: str = Query("", description="股票名称"),
    source: str = Query("chat", description="来源"),
    notes: str = Query("", description="备注"),
    current_user: dict = Depends(get_current_user),
):
    """Add stock to watchlist (加入自选). Idempotent."""
    from datetime import datetime as dt

    from stock_datasource.models.database import db_client

    try:
        db_client.execute(
            "CREATE TABLE IF NOT EXISTS user_watchlist ("
            "user_id String, ts_code String, stock_name String DEFAULT '', "
            "added_at DateTime DEFAULT now(), source String DEFAULT 'manual', "
            "notes String DEFAULT ''"
            ") ENGINE = ReplacingMergeTree(added_at) ORDER BY (user_id, ts_code)"
        )
        db_client.execute(
            "INSERT INTO user_watchlist (user_id, ts_code, stock_name, added_at, source, notes) "
            "VALUES (%(uid)s, %(code)s, %(name)s, %(at)s, %(src)s, %(notes)s)",
            {"uid": current_user["id"], "code": ts_code, "name": stock_name,
             "at": dt.now(), "src": source, "notes": notes},
        )
        return {"success": True, "message": f"已加入自选: {ts_code}"}
    except Exception as e:
        logger.error(f"Failed to add to watchlist: {e}")
        return {"success": False, "error": str(e)}


@router.delete("/watchlist/{ts_code}")
async def remove_from_watchlist(ts_code: str, current_user: dict = Depends(get_current_user)):
    """Remove stock from watchlist."""
    from stock_datasource.models.database import db_client

    try:
        db_client.execute(
            "ALTER TABLE user_watchlist DELETE WHERE user_id = %(uid)s AND ts_code = %(code)s",
            {"uid": current_user["id"], "code": ts_code},
        )
        return {"success": True, "message": f"已移出自选: {ts_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/alerts/quick")
async def quick_create_alert(
    ts_code: str = Query(..., description="股票代码"),
    alert_type: str = Query("price", description="price/profit_loss/volume/technical"),
    condition_type: str = Query("greater_than", description="greater_than/less_than"),
    threshold_value: float = Query(0, description="阈值"),
    message: str = Query("", description="自定义消息"),
    current_user: dict = Depends(get_current_user),
):
    """Quick-create a stock alert from chat (轻量版设置提醒)."""
    import uuid
    from datetime import datetime as dt

    from stock_datasource.models.database import db_client

    try:
        aid = f"alert_{uuid.uuid4().hex[:8]}"
        db_client.execute(
            "INSERT INTO position_alerts "
            "(id, user_id, ts_code, alert_type, condition_type, threshold_value, "
            "is_active, message, created_at, updated_at) "
            "VALUES (%(id)s, %(uid)s, %(code)s, %(atype)s, %(ctype)s, %(val)s, "
            "1, %(msg)s, %(now)s, %(now)s)",
            {"id": aid, "uid": current_user["id"], "code": ts_code, "atype": alert_type,
             "ctype": condition_type, "val": threshold_value,
             "msg": message or f"{ts_code} 异动提醒", "now": dt.now()},
        )
        return {"success": True, "alert_id": aid, "message": f"已设置提醒: {ts_code}"}
    except Exception as e:
        logger.error(f"Failed to quick-create alert: {e}")
        return {"success": False, "error": str(e)}
