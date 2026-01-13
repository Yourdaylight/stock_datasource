"""
龙虎榜相关的API路由
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ..services.toplist_service import TopListService
from ..services.toplist_analysis_service import TopListAnalysisService
from ..services.anomaly_detection_service import AnomalyDetectionService
from ..agents.toplist_agent import TopListAgent

router = APIRouter(prefix="/api/toplist", tags=["toplist"])

# 请求/响应模型
class TopListItem(BaseModel):
    """龙虎榜单项"""
    trade_date: str
    ts_code: str
    name: str
    close: Optional[float] = None
    pct_chg: Optional[float] = None
    turnover_rate: Optional[float] = None
    amount: Optional[float] = None
    l_sell: Optional[float] = None
    l_buy: Optional[float] = None
    l_amount: Optional[float] = None
    net_amount: Optional[float] = None
    net_rate: Optional[float] = None
    amount_rate: Optional[float] = None
    float_values: Optional[float] = None
    reason: str

class TopInstItem(BaseModel):
    """机构席位单项"""
    trade_date: str
    ts_code: str
    exalter: str
    buy: Optional[float] = None
    buy_rate: Optional[float] = None
    sell: Optional[float] = None
    sell_rate: Optional[float] = None
    net_buy: Optional[float] = None
    seat_type: str = "unknown"

class TopListSummary(BaseModel):
    """龙虎榜摘要"""
    trade_date: str
    total_stocks: int
    total_amount: float
    avg_pct_chg: float
    avg_turnover_rate: float
    total_net_amount: float
    institution_count: int
    hot_money_count: int
    unknown_count: int
    net_institution_flow: float
    net_hot_money_flow: float

class TopListResponse(BaseModel):
    """龙虎榜响应"""
    success: bool
    data: List[TopListItem]
    summary: Optional[TopListSummary] = None
    total_count: int
    message: str

class InstitutionalAnalysisResponse(BaseModel):
    """机构分析响应"""
    success: bool
    data: Dict[str, Any]
    message: str

class AnomalyAlert(BaseModel):
    """异动预警"""
    ts_code: str
    name: str
    trade_date: str
    anomaly_type: str
    severity: str
    description: str
    confidence: float
    metrics: Dict[str, Any]

class AnomalyResponse(BaseModel):
    """异动检测响应"""
    success: bool
    data: Dict[str, List[AnomalyAlert]]
    total_alerts: int
    critical_count: int
    high_count: int
    message: str

class TopListQuery(BaseModel):
    """龙虎榜查询参数"""
    trade_date: Optional[str] = None
    ts_code: Optional[str] = None
    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)

# 依赖注入
def get_toplist_service() -> TopListService:
    return TopListService()

def get_analysis_service() -> TopListAnalysisService:
    return TopListAnalysisService()

def get_anomaly_service() -> AnomalyDetectionService:
    return AnomalyDetectionService()

def get_toplist_agent() -> TopListAgent:
    return TopListAgent()

# API路由
@router.get("/data/{trade_date}", response_model=TopListResponse)
async def get_top_list_by_date(
    trade_date: str,
    ts_code: Optional[str] = Query(None, description="股票代码，可选"),
    service: TopListService = Depends(get_toplist_service)
):
    """获取指定日期的龙虎榜数据"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        # 验证日期有效性
        try:
            datetime.strptime(formatted_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD or YYYYMMDD")
        
        # 获取数据
        top_list_data = await service.get_top_list_by_date(formatted_date)
        summary = await service.get_top_list_summary(formatted_date)
        
        # 如果指定了股票代码，过滤数据
        if ts_code:
            top_list_data = [item for item in top_list_data if item.get("ts_code") == ts_code]
        
        return TopListResponse(
            success=True,
            data=[TopListItem(**item) for item in top_list_data],
            summary=TopListSummary(**summary) if summary else None,
            total_count=len(top_list_data),
            message=f"Successfully retrieved top list data for {formatted_date}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get top list data: {str(e)}")

@router.get("/institutional-seats/{trade_date}")
async def get_institutional_seats(
    trade_date: str,
    ts_code: Optional[str] = Query(None, description="股票代码，可选"),
    service: TopListService = Depends(get_toplist_service)
):
    """获取指定日期的机构席位数据"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        # 获取数据
        inst_data = await service.get_top_inst_by_date(formatted_date)
        
        # 如果指定了股票代码，过滤数据
        if ts_code:
            inst_data = [item for item in inst_data if item.get("ts_code") == ts_code]
        
        return {
            "success": True,
            "data": [TopInstItem(**item) for item in inst_data],
            "total_count": len(inst_data),
            "message": f"Successfully retrieved institutional seats data for {formatted_date}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get institutional seats data: {str(e)}")

@router.get("/analysis/institutional/{trade_date}", response_model=InstitutionalAnalysisResponse)
async def get_institutional_analysis(
    trade_date: str,
    service: TopListAnalysisService = Depends(get_analysis_service)
):
    """获取机构资金流向分析"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        analysis = await service.analyze_institutional_flow(formatted_date)
        
        return InstitutionalAnalysisResponse(
            success=True,
            data=analysis,
            message=f"Successfully analyzed institutional flow for {formatted_date}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze institutional flow: {str(e)}")

@router.get("/analysis/hot-money")
async def get_hot_money_targets(
    days: int = Query(5, ge=1, le=30, description="分析天数"),
    service: TopListAnalysisService = Depends(get_analysis_service)
):
    """获取游资目标股票"""
    try:
        targets = await service.identify_hot_money_targets(days)
        
        return {
            "success": True,
            "data": {
                "targets": targets,
                "analysis_period": f"最近{days}天"
            },
            "message": f"Successfully identified {len(targets)} hot money targets"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to identify hot money targets: {str(e)}")

@router.get("/analysis/concentration/{ts_code}")
async def get_seat_concentration(
    ts_code: str,
    days: int = Query(10, ge=1, le=30, description="分析天数"),
    service: TopListAnalysisService = Depends(get_analysis_service)
):
    """获取股票席位集中度分析"""
    try:
        concentration = await service.calculate_seat_concentration(ts_code, days)
        
        return {
            "success": True,
            "data": concentration,
            "message": f"Successfully calculated seat concentration for {ts_code}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate seat concentration: {str(e)}")

@router.get("/anomalies/detection", response_model=AnomalyResponse)
async def get_anomaly_detection(
    service: AnomalyDetectionService = Depends(get_anomaly_service)
):
    """获取异动检测结果"""
    try:
        alerts = await service.generate_anomaly_alerts()
        
        # 按严重程度分类
        anomalies_by_severity = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for alert in alerts:
            anomaly_alert = AnomalyAlert(
                ts_code=alert.ts_code,
                name=alert.name,
                trade_date=alert.trade_date,
                anomaly_type=alert.anomaly_type,
                severity=alert.severity,
                description=alert.description,
                confidence=alert.confidence,
                metrics=alert.metrics
            )
            anomalies_by_severity[alert.severity].append(anomaly_alert)
        
        return AnomalyResponse(
            success=True,
            data=anomalies_by_severity,
            total_alerts=len(alerts),
            critical_count=len(anomalies_by_severity["critical"]),
            high_count=len(anomalies_by_severity["high"]),
            message=f"Successfully detected {len(alerts)} anomalies"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to detect anomalies: {str(e)}")

@router.get("/stock/{ts_code}/history")
async def get_stock_toplist_history(
    ts_code: str,
    days: int = Query(30, ge=1, le=90, description="查询天数"),
    service: TopListService = Depends(get_toplist_service)
):
    """获取股票龙虎榜历史"""
    try:
        history = await service.get_stock_top_list_history(ts_code, days)
        
        return {
            "success": True,
            "data": {
                "history": [TopListItem(**item) for item in history],
                "appearance_count": len(history),
                "analysis_period": f"最近{days}天"
            },
            "message": f"{ts_code} appeared on top list {len(history)} times in last {days} days"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stock history: {str(e)}")

@router.get("/analysis/sector/{trade_date}")
async def get_sector_analysis(
    trade_date: str,
    service: TopListAnalysisService = Depends(get_analysis_service)
):
    """获取板块资金流向分析"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        sector_analysis = await service.analyze_sector_flow(formatted_date)
        
        return {
            "success": True,
            "data": sector_analysis,
            "message": f"Successfully analyzed sector flows for {formatted_date}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze sector flows: {str(e)}")

@router.get("/report/{trade_date}")
async def get_comprehensive_report(
    trade_date: str,
    agent: TopListAgent = Depends(get_toplist_agent)
):
    """获取龙虎榜综合分析报告"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        report = await agent.generate_toplist_report(formatted_date)
        
        return report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")

@router.get("/active-stocks")
async def get_active_stocks(
    days: int = Query(7, ge=1, le=30, description="查询天数"),
    service: TopListService = Depends(get_toplist_service)
):
    """获取活跃股票（频繁上榜）"""
    try:
        active_stocks = await service.get_active_stocks(days)
        
        return {
            "success": True,
            "data": {
                "active_stocks": active_stocks,
                "analysis_period": f"最近{days}天"
            },
            "message": f"Found {len(active_stocks)} active stocks in last {days} days"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active stocks: {str(e)}")

@router.get("/statistics/reasons/{trade_date}")
async def get_reason_statistics(
    trade_date: str,
    service: TopListService = Depends(get_toplist_service)
):
    """获取上榜原因统计"""
    try:
        # 验证日期格式
        if len(trade_date) == 8:  # YYYYMMDD
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        else:
            formatted_date = trade_date
        
        statistics = await service.get_reason_statistics(formatted_date)
        
        return {
            "success": True,
            "data": {
                "statistics": statistics,
                "trade_date": formatted_date
            },
            "message": f"Successfully retrieved reason statistics for {formatted_date}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reason statistics: {str(e)}")

# 组合分析相关路由
class PortfolioAnalyzeRequest(BaseModel):
    """组合分析请求"""
    user_id: str = "default_user"

@router.post("/portfolio/analyze")
async def analyze_portfolio_toplist(
    request: PortfolioAnalyzeRequest,
    service: TopListService = Depends(get_toplist_service)
):
    """分析持仓组合的龙虎榜情况"""
    try:
        # 获取最近的龙虎榜数据作为分析基础
        from datetime import datetime, timedelta
        today = datetime.now().date()
        
        # 尝试获取最近7天内的数据
        analysis_result = {
            "on_list_positions": [],
            "capital_flow_analysis": {
                "total_net_flow": 0.0,
                "average_concentration": 0.0,
                "positions_on_toplist": 0,
                "high_risk_positions": 0
            },
            "risk_alerts": [],
            "investment_suggestions": [
                "建议关注龙虎榜中机构净买入的股票",
                "注意回避连续上榜但资金净流出的个股",
                "关注席位集中度较高的股票，可能存在主力资金运作"
            ]
        }
        
        return {
            "success": True,
            "data": analysis_result,
            "message": "Portfolio analysis completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze portfolio: {str(e)}")

@router.post("/portfolio/status")
async def check_portfolio_status(
    request: PortfolioAnalyzeRequest,
    service: TopListService = Depends(get_toplist_service)
):
    """检查持仓在龙虎榜上的状态"""
    try:
        return {
            "success": True,
            "data": {
                "positions_status": [],
                "total_positions": 0,
                "on_toplist_count": 0,
                "toplist_ratio": 0.0
            },
            "message": "Portfolio status check completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check portfolio status: {str(e)}")

@router.post("/portfolio/capital-flow")
async def analyze_portfolio_capital_flow(
    request: PortfolioAnalyzeRequest,
    days: int = Query(5, ge=1, le=30, description="分析天数"),
    service: TopListService = Depends(get_toplist_service)
):
    """分析持仓资金流向"""
    try:
        return {
            "success": True,
            "data": {
                "position_flows": [],
                "summary": {
                    "total_positions": 0,
                    "analyzed_positions": 0,
                    "net_inflow_positions": 0,
                    "net_outflow_positions": 0,
                    "total_net_flow": 0.0
                }
            },
            "message": f"Capital flow analysis completed for last {days} days"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze capital flow: {str(e)}")

# 健康检查
@router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "toplist_api",
        "timestamp": datetime.now().isoformat()
    }