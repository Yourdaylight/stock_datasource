"""News data models and schemas.

Defines data structures for news items, sentiment analysis, and hot topics.
"""

from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class NewsCategory(str, Enum):
    """新闻分类"""
    ANNOUNCEMENT = "announcement"  # 上市公司公告
    FLASH = "flash"                # 财经快讯
    ANALYSIS = "analysis"          # 分析解读
    POLICY = "policy"              # 政策法规
    INDUSTRY = "industry"          # 行业动态
    ALL = "all"                    # 全部


class SentimentType(str, Enum):
    """情绪类型"""
    POSITIVE = "positive"  # 利好
    NEGATIVE = "negative"  # 利空
    NEUTRAL = "neutral"    # 中性


class ImpactLevel(str, Enum):
    """影响程度"""
    HIGH = "high"      # 重大影响
    MEDIUM = "medium"  # 中等影响
    LOW = "low"        # 轻微影响


class NewsSentiment(BaseModel):
    """新闻情绪分析结果"""
    news_id: str = Field(..., description="新闻ID")
    title: str = Field(default="", description="新闻标题")
    sentiment: SentimentType = Field(..., description="情绪类型")
    score: float = Field(default=0.0, ge=-1.0, le=1.0, description="情绪分数，-1.0到1.0")
    reasoning: str = Field(default="", description="分析理由")
    impact_level: ImpactLevel = Field(default=ImpactLevel.LOW, description="影响程度")
    
    class Config:
        use_enum_values = True


class NewsItem(BaseModel):
    """新闻条目"""
    id: str = Field(..., description="新闻唯一标识")
    title: str = Field(..., description="新闻标题")
    content: str = Field(default="", description="新闻内容或摘要")
    source: str = Field(default="unknown", description="新闻来源（tushare/sina/etc）")
    publish_time: Optional[datetime] = Field(default=None, description="发布时间")
    stock_codes: List[str] = Field(default_factory=list, description="关联股票代码")
    category: NewsCategory = Field(default=NewsCategory.ALL, description="新闻分类")
    url: Optional[str] = Field(default=None, description="原文链接")
    sentiment: Optional[NewsSentiment] = Field(default=None, description="情绪分析结果")
    sentiment_score: Optional[float] = Field(
        default=None,
        ge=-1.0,
        le=1.0,
        description="情绪分数，-1.0到1.0"
    )
    sentiment_reasoning: Optional[str] = Field(default=None, description="情绪分析理由")
    impact_level: Optional[ImpactLevel] = Field(default=None, description="影响程度")

    @model_validator(mode="before")
    @classmethod
    def normalize_sentiment(cls, data):
        if not isinstance(data, dict):
            return data

        sentiment_value = data.get("sentiment")
        if isinstance(sentiment_value, dict):
            return data

        sentiment_str = None
        if sentiment_value is not None:
            sentiment_str = getattr(sentiment_value, "value", sentiment_value)

        has_flat = (
            sentiment_str is not None
            or data.get("sentiment_score") is not None
            or data.get("sentiment_reasoning")
            or data.get("impact_level")
        )
        if has_flat:
            data["sentiment"] = {
                "news_id": data.get("id", ""),
                "title": data.get("title", ""),
                "sentiment": sentiment_str or "neutral",
                "score": data.get("sentiment_score") or 0.0,
                "reasoning": data.get("sentiment_reasoning") or "",
                "impact_level": getattr(data.get("impact_level"), "value", data.get("impact_level") or "low"),
            }

        return data

    class Config:
        use_enum_values = True


class HotTopic(BaseModel):
    """热点话题"""
    topic: str = Field(..., description="话题名称")
    keywords: List[str] = Field(default_factory=list, description="关键词")
    heat_score: float = Field(default=0.0, description="热度分数")
    related_stocks: List[str] = Field(default_factory=list, description="相关股票代码")
    news_count: int = Field(default=0, description="相关新闻数量")
    summary: str = Field(default="", description="话题摘要")


# API Request/Response schemas
class GetNewsByStockRequest(BaseModel):
    """获取股票相关新闻请求"""
    stock_code: str = Field(..., description="股票代码，如 600519.SH")
    days: int = Field(default=7, ge=1, le=30, description="查询天数")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量")


class GetMarketNewsRequest(BaseModel):
    """获取市场新闻请求"""
    category: NewsCategory = Field(default=NewsCategory.ALL, description="新闻分类")
    limit: int = Field(default=20, ge=1, le=100, description="返回数量")


class AnalyzeSentimentRequest(BaseModel):
    """情绪分析请求"""
    news_ids: List[str] = Field(default_factory=list, description="新闻ID列表")
    stock_code: Optional[str] = Field(default=None, description="关联股票代码（用于上下文）")


class NewsListResponse(BaseModel):
    """新闻列表响应"""
    success: bool = Field(default=True)
    total: int = Field(default=0, description="总数")
    data: List[NewsItem] = Field(default_factory=list)
    message: str = Field(default="")


class SentimentListResponse(BaseModel):
    """情绪分析结果列表响应"""
    success: bool = Field(default=True)
    total: int = Field(default=0)
    data: List[NewsSentiment] = Field(default_factory=list)
    message: str = Field(default="")


class HotTopicsResponse(BaseModel):
    """热点话题响应"""
    success: bool = Field(default=True)
    trade_date: Optional[str] = Field(default=None, description="数据日期")
    data: List[HotTopic] = Field(default_factory=list)
    message: str = Field(default="")


class NewsSummaryResponse(BaseModel):
    """新闻摘要响应"""
    success: bool = Field(default=True)
    summary: str = Field(default="", description="AI生成的新闻摘要")
    key_points: List[str] = Field(default_factory=list, description="要点列表")
    sentiment_overview: str = Field(default="", description="整体情绪概述")
    message: str = Field(default="")