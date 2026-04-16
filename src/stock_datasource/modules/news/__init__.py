"""News module for financial news analysis.

Provides news data retrieval and sentiment analysis.
"""

from .schemas import NewsCategory, NewsItem, NewsSentiment
from .service import NewsService, get_news_service

__all__ = [
    "NewsCategory",
    "NewsItem",
    "NewsSentiment",
    "NewsService",
    "get_news_service",
]
