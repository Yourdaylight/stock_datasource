"""News module for financial news analysis.

Provides news data retrieval, sentiment analysis, and hot topics tracking.
"""

from .service import NewsService, get_news_service
from .schemas import NewsItem, NewsSentiment, HotTopic, NewsCategory

__all__ = [
    "NewsService",
    "get_news_service",
    "NewsItem",
    "NewsSentiment",
    "HotTopic",
    "NewsCategory",
]
