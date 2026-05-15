"""News Sentiment Sentinel - monitors news sentiment shifts for core pool stocks."""

from __future__ import annotations

import logging
from datetime import datetime

from stock_datasource.models.database import db_client

from ..core.base_sentinel import BaseSentinel
from ..schemas import AlertCategory, AlertSeverity, SentinelAlert

logger = logging.getLogger(__name__)


class NewsSentimentSentinel(BaseSentinel):
    """Monitors news sentiment for stocks in the core pool.

    Uses the news service to detect sentiment shifts and high-impact news.

    Triggers:
    - Sentiment shift: positive → negative or vice versa
    - High-impact news detected for a core pool stock
    """

    SENTINEL_TYPE: str = "news_sentiment"
    CATEGORY: AlertCategory = AlertCategory.NEWS

    def get_monitoring_description(self) -> str:
        return "监控核心池股票的新闻舆情变化，识别情绪突变和重大事件"

    async def scan(self) -> list[SentinelAlert]:
        """Scan news sentiment for core pool stocks."""
        alerts: list[SentinelAlert] = []

        try:
            # Try to import news service - may not be available
            try:
                from stock_datasource.modules.news.service import get_news_service
                news_service = get_news_service()
            except (ImportError, Exception) as import_err:
                logger.debug(f"NewsSentimentSentinel: 新闻服务不可用 - {import_err}")
                return []

            # Get current core pool
            pool_sql = """
                SELECT ts_code, stock_name
                FROM quant_core_pool
                WHERE update_date = (SELECT max(update_date) FROM quant_core_pool)
            """
            pool_df = db_client.execute_query(pool_sql)

            if pool_df is None or len(pool_df) == 0:
                return []

            stock_name_map = dict(zip(pool_df["ts_code"], pool_df["stock_name"]))

            # Check each stock's news sentiment
            for ts_code in pool_df["ts_code"].tolist():
                stock_name = stock_name_map.get(ts_code, ts_code)

                try:
                    # Get recent news for the stock
                    news_data = await news_service.get_stock_news_summary(ts_code)

                    if news_data is None:
                        continue

                    # Check for sentiment shift
                    current_sentiment = news_data.get("current_sentiment")
                    previous_sentiment = news_data.get("previous_sentiment")
                    sentiment_score = news_data.get("sentiment_score", 0)
                    high_impact = news_data.get("high_impact", False)
                    headline = news_data.get("headline", "")

                    # Sentiment shift detection
                    if (current_sentiment and previous_sentiment and
                            current_sentiment != previous_sentiment):

                        if current_sentiment == "negative" and previous_sentiment == "positive":
                            alerts.append(SentinelAlert(
                                sentinel_type=self.SENTINEL_TYPE,
                                category=self.CATEGORY,
                                severity=AlertSeverity.WARNING,
                                ts_code=ts_code,
                                signal_type="sentiment_shift_negative",
                                description=f"{stock_name}({ts_code}) 舆情由正面转为负面，"
                                            f"情绪评分{sentiment_score:.2f}，需关注风险",
                                metric_name="sentiment_score",
                                metric_value=sentiment_score,
                                threshold=0,
                                deviation_pct=sentiment_score * 100,
                                context={
                                    "stock_name": stock_name,
                                    "current_sentiment": current_sentiment,
                                    "previous_sentiment": previous_sentiment,
                                    "headline": headline,
                                    "signal": "negative_shift",
                                },
                            ))

                        elif current_sentiment == "positive" and previous_sentiment == "negative":
                            alerts.append(SentinelAlert(
                                sentinel_type=self.SENTINEL_TYPE,
                                category=self.CATEGORY,
                                severity=AlertSeverity.INFO,
                                ts_code=ts_code,
                                signal_type="sentiment_shift_positive",
                                description=f"{stock_name}({ts_code}) 舆情由负面转为正面，"
                                            f"情绪评分{sentiment_score:.2f}，关注反转机会",
                                metric_name="sentiment_score",
                                metric_value=sentiment_score,
                                threshold=0,
                                deviation_pct=sentiment_score * 100,
                                context={
                                    "stock_name": stock_name,
                                    "current_sentiment": current_sentiment,
                                    "previous_sentiment": previous_sentiment,
                                    "headline": headline,
                                    "signal": "positive_shift",
                                },
                            ))

                    # High-impact news detection
                    if high_impact:
                        alerts.append(SentinelAlert(
                            sentinel_type=self.SENTINEL_TYPE,
                            category=self.CATEGORY,
                            severity=AlertSeverity.CRITICAL,
                            ts_code=ts_code,
                            signal_type="high_impact_news",
                            description=f"{stock_name}({ts_code}) 出现重大新闻事件: {headline[:50]}",
                            metric_name="news_impact",
                            metric_value=1.0,
                            threshold=0.5,
                            deviation_pct=100.0,
                            context={
                                "stock_name": stock_name,
                                "headline": headline,
                                "sentiment_score": sentiment_score,
                                "high_impact": True,
                            },
                        ))

                except Exception as stock_err:
                    logger.debug(f"NewsSentimentSentinel: 获取{ts_code}新闻失败 - {stock_err}")
                    continue

        except Exception as e:
            logger.error(f"NewsSentimentSentinel scan error: {e}", exc_info=True)

        return alerts
