"""Screener module router - 智能选股模块API

增强功能：
- 多维度条件筛选
- 十维画像
- 自然语言选股
- AI推荐
- 行业筛选
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Any, Optional, Dict
import logging
import pandas as pd

from .schemas import (
    ScreenerCondition, ScreenerRequest, NLScreenerRequest, BatchProfileRequest,
    StockItem, StockListResponse, NLScreenerResponse, 
    StockProfile, PresetStrategy,
    SectorInfo, SectorListResponse,
    FieldDefinition, MarketSummary,
    Recommendation, RecommendationResponse,
    TechnicalSignal, TechnicalSignalResponse,
)
from .service import get_screener_service
from .profile import get_profile_service

logger = logging.getLogger(__name__)


def _safe_float(value) -> Optional[float]:
    """Convert value to float, return None if NaN or invalid."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

router = APIRouter()


# =============================================================================
# 股票列表 API
# =============================================================================

@router.get("/stocks", response_model=StockListResponse)
async def get_stocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "pct_chg",
    sort_order: str = "desc",
    search: Optional[str] = None,
    trade_date: Optional[str] = Query(None, description="交易日期，格式 YYYY-MM-DD，默认最新日期"),
    market_type: Optional[str] = Query(None, description="市场类型: a_share, hk_stock, all (默认 a_share)")
):
    """获取分页股票列表（含最新行情）
    
    支持 A 股和港股，通过 market_type 参数切换。
    """
    try:
        service = get_screener_service()
        items, total = service.get_stocks(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            search=search,
            trade_date=trade_date,
            market_type=market_type
        )
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return StockListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Failed to get stocks: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


# =============================================================================
# 条件筛选 API
# =============================================================================

@router.post("/filter", response_model=StockListResponse)
async def filter_stocks(
    request: ScreenerRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """多条件筛选股票
    
    支持 A 股和港股，通过 market_type 参数切换。
    """
    try:
        service = get_screener_service()
        items, total = service.filter_by_conditions(
            conditions=request.conditions,
            sort_by=request.sort_by or "pct_chg",
            sort_order=request.sort_order,
            page=page,
            page_size=page_size,
            trade_date=request.trade_date,
            market_type=request.market_type
        )
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return StockListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Failed to filter stocks: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


# =============================================================================
# 自然语言选股 API
# =============================================================================

@router.post("/nl", response_model=NLScreenerResponse)
async def nl_screener(
    request: NLScreenerRequest,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """自然语言选股 - 使用AI解析用户意图"""
    try:
        from stock_datasource.agents import get_screener_agent
        
        agent = get_screener_agent()
        result = await agent.execute(request.query, {"session_id": "screener"})
        
        # 解析Agent返回的结果 - 使用正确的字段名 metadata 和 response
        if result.success and result.metadata:
            parsed_data = result.metadata.get('parsed_conditions', {})
            parsed_conditions = parsed_data.get('conditions', [])
            explanation = parsed_data.get('explanation', '') or result.response
            
            # 使用解析出的条件进行筛选
            if parsed_conditions:
                service = get_screener_service()
                conditions = [ScreenerCondition(**c) for c in parsed_conditions]
                items, total = service.filter_by_conditions(
                    conditions=conditions,
                    page=page,
                    page_size=page_size
                )
                
                total_pages = (total + page_size - 1) // page_size if total > 0 else 0
                
                return NLScreenerResponse(
                    parsed_conditions=conditions,
                    items=items,
                    total=total,
                    page=page,
                    page_size=page_size,
                    total_pages=total_pages,
                    explanation=explanation
                )
        
        # 未能解析出有效条件
        return NLScreenerResponse(
            parsed_conditions=[],
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            explanation=result.response if result.response else "无法解析您的选股条件，请尝试更具体的描述"
        )
        
    except Exception as e:
        logger.error(f"NL screener failed: {e}")
        return NLScreenerResponse(
            parsed_conditions=[],
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
            explanation=f"选股失败: {str(e)}"
        )


# =============================================================================
# 十维画像 API
# =============================================================================

@router.get("/profile/{ts_code}", response_model=StockProfile)
async def get_stock_profile(ts_code: str):
    """获取单只股票的十维画像"""
    try:
        service = get_profile_service()
        profile = service.calculate_profile(ts_code.upper())
        
        if not profile:
            raise HTTPException(status_code=404, detail=f"未找到股票 {ts_code} 的数据")
        
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile for {ts_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-profile", response_model=List[StockProfile])
async def batch_get_profiles(request: BatchProfileRequest):
    """批量获取股票画像"""
    try:
        if len(request.ts_codes) > 50:
            raise HTTPException(status_code=400, detail="一次最多查询50只股票")
        
        service = get_profile_service()
        profiles = service.batch_calculate_profiles([c.upper() for c in request.ts_codes])
        
        return profiles
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to batch get profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# 行业筛选 API
# =============================================================================

@router.get("/sectors", response_model=SectorListResponse)
async def get_sectors(
    market_type: Optional[str] = Query(None, description="市场类型: a_share, hk_stock (默认 a_share)")
):
    """获取行业列表
    
    注：港股暂不支持行业筛选，返回空列表
    """
    try:
        # 港股暂不支持行业筛选
        if market_type == 'hk_stock':
            return SectorListResponse(sectors=[], total=0)
        
        service = get_screener_service()
        sectors = service.get_sectors()
        
        return SectorListResponse(
            sectors=sectors,
            total=len(sectors)
        )
    except Exception as e:
        logger.error(f"Failed to get sectors: {e}")
        return SectorListResponse(sectors=[], total=0)


@router.get("/sectors/{sector}/stocks", response_model=StockListResponse)
async def get_sector_stocks(
    sector: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = "pct_chg",
    sort_order: str = "desc",
):
    """获取特定行业的股票列表"""
    try:
        service = get_screener_service()
        items, total = service.get_stocks_by_sector(
            sector=sector,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return StockListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        logger.error(f"Failed to get sector stocks: {e}")
        return StockListResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)


# =============================================================================
# AI推荐 API
# =============================================================================

@router.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    market_type: Optional[str] = Query(None, description="市场类型: a_share, hk_stock (默认 a_share)")
):
    """获取AI智能推荐
    
    根据市场类型返回不同的推荐策略
    """
    try:
        service = get_screener_service()
        
        categories: Dict[str, List[Recommendation]] = {}
        
        if market_type == 'hk_stock':
            # 港股推荐策略（基于港股支持的字段）
            from stock_datasource.plugins.tushare_hk_daily.service import TuShareHKDailyService
            hk_service = TuShareHKDailyService()
            latest_date = hk_service.get_latest_trade_date() or ""
            
            # 强势港股推荐
            momentum_conds = [
                ScreenerCondition(field="pct_chg", operator="gt", value=3),
            ]
            items, _ = service.filter_by_conditions(momentum_conds, sort_by="pct_chg", sort_order="desc", page=1, page_size=5, market_type='hk_stock')
            categories["strong_momentum"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"今日涨幅 {item.pct_chg:.2f}%，动量强劲" if item.pct_chg else "强势股",
                    score=75.0,
                    category="强势港股"
                ) for item in items
            ]
            
            # 大跌港股（可能超跌反弹）
            oversold_conds = [
                ScreenerCondition(field="pct_chg", operator="lt", value=-3),
            ]
            items, _ = service.filter_by_conditions(oversold_conds, sort_by="pct_chg", sort_order="asc", page=1, page_size=5, market_type='hk_stock')
            categories["oversold"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"今日跌幅 {item.pct_chg:.2f}%，关注超跌机会" if item.pct_chg else "超跌股",
                    score=65.0,
                    category="超跌港股"
                ) for item in items
            ]
            
            # 高成交港股
            volume_conds = [
                ScreenerCondition(field="amount", operator="gt", value=1000000000),  # 成交额 > 10亿
            ]
            items, _ = service.filter_by_conditions(volume_conds, sort_by="amount", sort_order="desc", page=1, page_size=5, market_type='hk_stock')
            categories["high_volume"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"成交额 {item.amount/100000000:.2f}亿，资金关注度高" if item.amount else "高成交",
                    score=70.0,
                    category="高成交港股"
                ) for item in items
            ]
        else:
            # A股推荐策略（原有逻辑）
            latest_date = service.get_latest_trade_date() or ""
            
            # 低估值推荐
            low_pe_conds = [
                ScreenerCondition(field="pe", operator="lt", value=15),
                ScreenerCondition(field="pe", operator="gt", value=0),
                ScreenerCondition(field="pb", operator="lt", value=2),
            ]
            items, _ = service.filter_by_conditions(low_pe_conds, sort_by="pe", sort_order="asc", page=1, page_size=5, market_type='a_share')
            categories["low_valuation"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"PE={item.pe_ttm:.1f}, PB={item.pb:.2f}, 估值较低" if item.pe_ttm and item.pb else "低估值",
                    score=80.0,
                    category="低估值"
                ) for item in items
            ]
            
            # 强势股推荐
            momentum_conds = [
                ScreenerCondition(field="pct_chg", operator="gt", value=5),
            ]
            items, _ = service.filter_by_conditions(momentum_conds, sort_by="pct_chg", sort_order="desc", page=1, page_size=5, market_type='a_share')
            categories["strong_momentum"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"今日涨幅 {item.pct_chg:.2f}%，动量强劲" if item.pct_chg else "强势股",
                    score=75.0,
                    category="强势股"
                ) for item in items
            ]
            
            # 活跃股推荐
            active_conds = [
                ScreenerCondition(field="turnover_rate", operator="gt", value=10),
            ]
            items, _ = service.filter_by_conditions(active_conds, sort_by="turnover_rate", sort_order="desc", page=1, page_size=5, market_type='a_share')
            categories["high_activity"] = [
                Recommendation(
                    ts_code=item.ts_code,
                    stock_name=item.stock_name or item.ts_code,
                    reason=f"换手率 {item.turnover_rate:.2f}%，交投活跃" if item.turnover_rate else "活跃股",
                    score=70.0,
                    category="活跃股"
                ) for item in items
            ]
        
        return RecommendationResponse(
            trade_date=latest_date,
            categories=categories
        )
    except Exception as e:
        logger.error(f"Failed to get recommendations: {e}")
        return RecommendationResponse(trade_date="", categories={})


# =============================================================================
# 技术信号 API
# =============================================================================

@router.get("/signals", response_model=TechnicalSignalResponse)
async def get_technical_signals():
    """获取技术信号股票"""
    # 暂时返回空结果，需要后续实现技术指标计算
    service = get_screener_service()
    latest_date = service.get_latest_trade_date() or ""
    
    return TechnicalSignalResponse(
        trade_date=latest_date,
        signals={}
    )


# =============================================================================
# 预设策略 API
# =============================================================================

@router.get("/presets", response_model=List[PresetStrategy])
async def get_presets():
    """获取预设筛选策略"""
    return [
        PresetStrategy(
            id="low_pe",
            name="低估值策略",
            description="PE < 15, PB < 2",
            conditions=[
                ScreenerCondition(field="pe", operator="lt", value=15),
                ScreenerCondition(field="pb", operator="lt", value=2)
            ]
        ),
        PresetStrategy(
            id="value_dividend",
            name="高股息策略",
            description="股息率 > 3%",
            conditions=[
                ScreenerCondition(field="dv_ratio", operator="gt", value=3)
            ]
        ),
        PresetStrategy(
            id="high_turnover",
            name="活跃股策略",
            description="换手率 > 5%",
            conditions=[
                ScreenerCondition(field="turnover_rate", operator="gt", value=5)
            ]
        ),
        PresetStrategy(
            id="large_cap",
            name="大盘股策略",
            description="总市值 > 1000亿",
            conditions=[
                ScreenerCondition(field="total_mv", operator="gt", value=10000000)
            ]
        ),
        PresetStrategy(
            id="strong_momentum",
            name="强势股策略",
            description="涨幅 > 5%",
            conditions=[
                ScreenerCondition(field="pct_chg", operator="gt", value=5)
            ]
        ),
        PresetStrategy(
            id="momentum_volume",
            name="放量上涨策略",
            description="涨幅 > 3%, 换手率 > 3%",
            conditions=[
                ScreenerCondition(field="pct_chg", operator="gt", value=3),
                ScreenerCondition(field="turnover_rate", operator="gt", value=3)
            ]
        ),
    ]


@router.post("/presets/{preset_id}/apply", response_model=StockListResponse)
async def apply_preset(
    preset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """应用预设策略进行筛选"""
    presets = await get_presets()
    preset = next((p for p in presets if p.id == preset_id), None)
    
    if not preset:
        raise HTTPException(status_code=404, detail=f"预设策略 {preset_id} 不存在")
    
    return await filter_stocks(
        ScreenerRequest(conditions=preset.conditions),
        page=page,
        page_size=page_size
    )


# =============================================================================
# 字段定义 API
# =============================================================================

@router.get("/fields", response_model=List[Dict[str, Any]])
async def get_fields():
    """获取可用筛选字段"""
    service = get_screener_service()
    return service.get_available_fields()


# =============================================================================
# 市场概况 API
# =============================================================================

@router.get("/summary", response_model=MarketSummary)
async def get_market_summary():
    """获取市场概况统计"""
    try:
        from stock_datasource.models.database import db_client
        
        db = db_client
        
        # Get latest trade date
        date_query = "SELECT max(trade_date) as max_date FROM ods_daily"
        date_df = db.execute_query(date_query)
        if date_df.empty or date_df.iloc[0]['max_date'] is None:
            raise HTTPException(status_code=404, detail="No data available")
        
        latest_date_raw = date_df.iloc[0]['max_date']
        if hasattr(latest_date_raw, 'strftime'):
            latest_date = latest_date_raw.strftime('%Y-%m-%d')
        else:
            latest_date = str(latest_date_raw).split()[0].split('T')[0]
        
        # Get summary statistics - 使用子查询先去重再聚合
        summary_query = f"""
            SELECT 
                count(*) as total_stocks,
                sum(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) as up_count,
                sum(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) as down_count,
                sum(CASE WHEN pct_chg = 0 THEN 1 ELSE 0 END) as flat_count,
                sum(CASE WHEN pct_chg >= 9.9 THEN 1 ELSE 0 END) as limit_up,
                sum(CASE WHEN pct_chg <= -9.9 THEN 1 ELSE 0 END) as limit_down,
                avg(pct_chg) as avg_change
            FROM (
                SELECT ts_code, argMax(pct_chg, _ingested_at) as pct_chg
                FROM ods_daily
                WHERE trade_date = '{latest_date}'
                GROUP BY ts_code
            )
        """
        
        df = db.execute_query(summary_query)
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data available")
        
        row = df.iloc[0]
        return MarketSummary(
            trade_date=latest_date,
            total_stocks=int(row['total_stocks']),
            up_count=int(row['up_count']),
            down_count=int(row['down_count']),
            flat_count=int(row['flat_count']),
            limit_up=int(row['limit_up']),
            limit_down=int(row['limit_down']),
            avg_change=float(row['avg_change']) if row['avg_change'] else 0,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get market summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
