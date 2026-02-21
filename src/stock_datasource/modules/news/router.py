"""News module HTTP router.

Provides API endpoints for news retrieval, sentiment analysis, and hot topics.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from .service import get_news_service
from .storage import get_news_storage
from .schemas import (
    NewsCategory,
    NewsListResponse,
    SentimentListResponse,
    HotTopicsResponse,
    NewsSummaryResponse,
)

router = APIRouter()


@router.get("/cache-info", summary="获取新闻缓存信息")
async def get_cache_info():
    """获取本地文件缓存信息
    
    返回缓存状态、新闻数量、更新时间等信息。
    用于监控和调试。
    """
    try:
        storage = get_news_storage()
        info = storage.get_cache_info()
        return {
            "success": True,
            "data": info,
            "message": ""
        }
    except Exception as e:
        return {
            "success": False,
            "data": None,
            "message": str(e)
        }


@router.post("/refresh-cache", summary="刷新新闻缓存")
async def refresh_cache():
    """强制刷新本地文件缓存
    
    从外部 API 获取最新新闻并更新本地缓存。
    """
    try:
        service = get_news_service()
        # 强制刷新获取最新新闻
        news_items = await service.get_market_news(
            NewsCategory.ALL,
            limit=50,
            force_refresh=True
        )
        
        # 获取更新后的缓存信息
        storage = get_news_storage()
        info = storage.get_cache_info()
        
        return {
            "success": True,
            "message": f"缓存已刷新，获取到 {len(news_items)} 条新闻",
            "data": info
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": str(e),
            "data": None
        }


@router.get("/categories", summary="获取新闻分类列表")
async def get_categories():
    """获取所有可用的新闻分类"""
    categories = [
        {"value": "all", "label": "全部"},
        {"value": "announcement", "label": "公告"},
        {"value": "flash", "label": "快讯"},
        {"value": "analysis", "label": "分析"},
        {"value": "policy", "label": "政策"},
        {"value": "industry", "label": "行业"},
    ]
    return {
        "success": True,
        "data": categories,
        "message": ""
    }


@router.get("/sources", summary="获取新闻来源列表")
async def get_sources():
    """获取所有可用的新闻来源
    
    当前已实现的数据源：
    - tushare: 上市公司公告（通过 Tushare 官方 API）
    - sina: 财经新闻（通过新浪公开 API）
    """
    sources = [
        {"value": "all", "label": "全部来源"},
        {"value": "tushare", "label": "公告数据（Tushare）"},
        {"value": "sina", "label": "财经新闻（新浪）"},
    ]
    return {
        "success": True,
        "data": sources,
        "message": ""
    }


@router.get("/list", summary="获取新闻列表")
async def get_news_list(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    category: Optional[str] = Query(default=None, description="新闻分类"),
    source: Optional[str] = Query(default=None, description="新闻来源"),
    sentiment: Optional[str] = Query(default=None, description="情绪类型"),
    stock_codes: Optional[str] = Query(default=None, description="股票代码，多个用逗号分隔"),
    start_date: Optional[str] = Query(default=None, description="开始日期，格式：YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期，格式：YYYY-MM-DD"),
    sort_by: str = Query(default="time", description="排序字段：time/heat/sentiment"),
    sort_order: str = Query(default="desc", description="排序方向：asc/desc"),
):
    """获取新闻列表（支持分页和筛选）
    
    数据来源说明：
    - tushare: 上市公司公告（通过 Tushare 官方 API）
    - sina: 财经新闻（通过新浪公开 API）
    
    注意：首次请求可能较慢（需要从外部 API 获取数据），后续会使用缓存
    """
    from datetime import datetime
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        service = get_news_service()
        
        # 解析 category
        news_category = NewsCategory.ALL
        if category and category != "all":
            try:
                news_category = NewsCategory(category)
            except ValueError:
                pass
        
        # 计算需要获取的数据量（优化：只获取需要的数据，而不是固定100条）
        # 考虑筛选后可能减少的数据，多获取一些
        fetch_limit = min(page * page_size * 2 + 20, 100)
        
        # 获取基础新闻数据
        all_news = await service.get_market_news(news_category, limit=fetch_limit)
        
        # 如果没有筛选条件且source也是all或空，直接分页返回，避免不必要的遍历
        if not source or source == "all":
            if not stock_codes and not start_date and not end_date:
                # 无筛选条件，直接返回
                total = len(all_news)
                start_idx = (page - 1) * page_size
                end_idx = start_idx + page_size
                page_data = all_news[start_idx:end_idx]
                
                return {
                    "success": True,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "data": page_data,
                    "has_more": end_idx < total,
                    "message": ""
                }
        
        # 解析股票代码列表
        stock_code_list = []
        if stock_codes:
            stock_code_list = [code.strip() for code in stock_codes.split(',') if code.strip()]
        
        # 应用筛选条件
        filtered_news = []
        for news in all_news:
            # 来源筛选
            if source and source != "all" and news.source != source:
                continue
            
            # 股票代码筛选
            if stock_code_list:
                if not any(code in news.stock_codes for code in stock_code_list):
                    continue
            
            # 日期范围筛选
            if news.publish_time:
                news_date = news.publish_time.date() if isinstance(news.publish_time, datetime) else news.publish_time
                
                if start_date:
                    try:
                        start = datetime.strptime(start_date, "%Y-%m-%d").date()
                        if news_date < start:
                            continue
                    except ValueError:
                        pass
                
                if end_date:
                    try:
                        end = datetime.strptime(end_date, "%Y-%m-%d").date()
                        if news_date > end:
                            continue
                    except ValueError:
                        pass
            
            filtered_news.append(news)
        
        # 排序
        if sort_by == "time" and filtered_news:
            filtered_news.sort(
                key=lambda x: x.publish_time or datetime.min,
                reverse=(sort_order == "desc")
            )
        
        # 分页
        total = len(filtered_news)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_data = filtered_news[start_idx:end_idx]
        
        return {
            "success": True,
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": page_data,
            "has_more": end_idx < total,
            "message": ""
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/stock/{code}", response_model=NewsListResponse, summary="获取股票新闻")
async def get_news_by_stock(
    code: str,
    days: int = Query(default=7, ge=1, le=30, description="查询天数"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
):
    """获取指定股票的相关新闻和公告
    
    Args:
        code: 股票代码，如 600519.SH
        days: 查询天数，默认7天
        limit: 返回数量，默认20条
    """
    try:
        service = get_news_service()
        news_items = await service.get_news_by_stock(code, days, limit)
        
        return NewsListResponse(
            success=True,
            total=len(news_items),
            data=news_items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market", response_model=NewsListResponse, summary="获取市场新闻")
async def get_market_news(
    category: NewsCategory = Query(default=NewsCategory.ALL, description="新闻分类"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
):
    """获取市场整体财经新闻
    
    Args:
        category: 新闻分类 (all/announcement/flash/analysis/policy/industry)
        limit: 返回数量
    """
    try:
        service = get_news_service()
        news_items = await service.get_market_news(category, limit)
        
        return NewsListResponse(
            success=True,
            total=len(news_items),
            data=news_items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=NewsListResponse, summary="搜索新闻")
async def search_news(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(default=20, ge=1, le=100, description="返回数量"),
):
    """按关键词搜索新闻
    
    Args:
        keyword: 搜索关键词
        limit: 返回数量
    """
    try:
        service = get_news_service()
        news_items = await service.search_news(keyword, limit)
        
        return NewsListResponse(
            success=True,
            total=len(news_items),
            data=news_items,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hot-topics", response_model=HotTopicsResponse, summary="获取热点话题")
async def get_hot_topics(
    limit: int = Query(default=10, ge=1, le=50, description="返回数量"),
    stock_code: Optional[str] = Query(default=None, description="股票代码（可选）"),
    days: int = Query(default=7, ge=1, le=30, description="查询天数（仅股票模式）"),
):
    """获取当前市场热点话题
    
    Args:
        limit: 返回数量
        stock_code: 股票代码（可选）
        days: 查询天数（仅股票模式）
    """
    try:
        service = get_news_service()
        topics = await service.get_hot_topics(limit=limit, stock_code=stock_code, days=days)
        
        return HotTopicsResponse(
            success=True,
            data=topics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-sentiment", response_model=SentimentListResponse, summary="分析新闻情绪")
async def analyze_sentiment(
    stock_code: str = Query(..., description="股票代码"),
    days: int = Query(default=7, ge=1, le=30, description="查询天数"),
    limit: int = Query(default=10, ge=1, le=50, description="分析数量"),
):
    """分析股票相关新闻的情绪倾向
    
    Args:
        stock_code: 股票代码
        days: 查询天数
        limit: 分析新闻数量
    """
    try:
        service = get_news_service()
        
        # 先获取新闻
        news_items = await service.get_news_by_stock(stock_code, days, limit)
        
        if not news_items:
            return SentimentListResponse(
                success=True,
                total=0,
                data=[],
                message="暂无相关新闻",
            )
        
        # 分析情绪
        sentiments = await service.analyze_news_sentiment(
            news_items,
            stock_context=f"股票代码: {stock_code}"
        )
        
        return SentimentListResponse(
            success=True,
            total=len(sentiments),
            data=sentiments,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summarize", response_model=NewsSummaryResponse, summary="生成新闻摘要")
async def summarize_news(
    stock_code: Optional[str] = Query(default=None, description="股票代码（可选）"),
    focus: Optional[str] = Query(default=None, description="关注重点（可选）"),
    days: int = Query(default=3, ge=1, le=7, description="查询天数"),
    limit: int = Query(default=20, ge=1, le=50, description="新闻数量"),
):
    """AI 生成新闻摘要
    
    Args:
        stock_code: 股票代码（可选，不提供则获取市场新闻）
        focus: 关注重点
        days: 查询天数
        limit: 新闻数量
    """
    try:
        service = get_news_service()
        
        # 获取新闻
        if stock_code:
            news_items = await service.get_news_by_stock(stock_code, days, limit)
        else:
            news_items = await service.get_market_news(NewsCategory.ALL, limit)
        
        if not news_items:
            return NewsSummaryResponse(
                success=True,
                summary="暂无相关新闻",
                message="未找到新闻数据",
            )
        
        # 生成摘要
        result = await service.summarize_news(news_items, focus)
        
        return NewsSummaryResponse(
            success=True,
            summary=result.get("summary", ""),
            key_points=result.get("key_points", []),
            sentiment_overview=result.get("sentiment_overview", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
