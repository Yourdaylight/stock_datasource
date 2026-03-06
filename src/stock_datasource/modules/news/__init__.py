"""News module for financial news analysis.

Provides news data retrieval and sentiment analysis.
"""

from .service import NewsService, get_news_service
from .schemas import NewsItem, NewsSentiment, NewsCategory

__all__ = [
    "NewsService",
    "get_news_service",
    "NewsItem",
    "NewsSentiment",
    "NewsCategory",
]
