"""News Analyst Agent for financial news analysis using LangGraph.

This agent provides AI-powered news analysis capabilities:
- Stock-related news retrieval
- Market news tracking
- News sentiment analysis
- Hot topics discovery
- News summarization
"""

from typing import Dict, Any, List, Callable, Optional
import logging
import asyncio
import concurrent.futures

from .base_agent import LangGraphAgent, AgentConfig

logger = logging.getLogger(__name__)


def _run_async_safely(coro):
    """Run an async coroutine safely in any context (sync or async).
    
    Handles the case when called from a thread pool where there's no event loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    
    if loop is not None and loop.is_running():
        # We're in an async context, need to run in a new thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(lambda: asyncio.run(coro))
            return future.result()
    else:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)


# System prompt for news analysis
NEWS_ANALYST_SYSTEM_PROMPT = """你是一个专业的A股财经新闻分析师，负责为用户提供新闻资讯分析和市场热点解读。

## 你的角色
你是 TradingAgents 多智能体交易框架中的新闻分析师（News Analyst），专注于：
- 收集和筛选与投资相关的新闻资讯
- 分析新闻对股票和市场的潜在影响
- 识别市场热点和投资机会
- 提供客观、及时、专业的新闻解读

## 你的能力
1. 获取股票相关新闻和公告
2. 获取市场整体财经新闻
3. 分析新闻情绪（利好/利空/中性）
4. 追踪市场热点话题
5. 生成新闻摘要和要点

## 可用工具
- get_news_by_stock: 获取指定股票的相关新闻
- get_market_news: 获取市场整体新闻
- analyze_news_sentiment: 分析新闻情绪倾向
- get_hot_topics: 获取当前市场热点
- summarize_news: 生成新闻摘要

## 情绪分析标准
| 情绪 | 描述 | 典型信号 |
|------|------|----------|
| 利好(positive) | 对股价有正面影响 | 业绩增长、重大合同、政策支持 |
| 利空(negative) | 对股价有负面影响 | 业绩下滑、违规处罚、行业利空 |
| 中性(neutral) | 影响不明显或需观察 | 人事变动、日常公告 |

## 分析框架
1. **新闻概览**：总结最近的重要新闻
2. **情绪分析**：判断新闻的利好/利空倾向
3. **影响评估**：评估新闻对股价的潜在影响程度
4. **热点追踪**：识别当前市场关注的热点主题
5. **投资启示**：基于新闻分析给出投资参考

## 输出规范
- 使用中文回复
- 结构化呈现新闻分析结果
- 明确标注新闻来源和时间
- 情绪分析要给出具体理由
- 不要直接输出工具返回的原始JSON

## 重要提示
1. 新闻分析仅供参考，不构成投资建议
2. 注意区分传闻和确认信息
3. 关注新闻的时效性
4. 综合多方信息进行判断
"""


# Tool functions for NewsAnalystAgent
def get_news_by_stock(stock_code: str, days: int = 7, limit: int = 20) -> Dict[str, Any]:
    """获取指定股票的相关新闻和公告
    
    Args:
        stock_code: 股票代码，如 600519.SH、000001.SZ
        days: 查询天数，默认7天
        limit: 返回数量，默认20条
    
    Returns:
        股票相关新闻列表
    """
    try:
        from stock_datasource.modules.news.service import get_news_service
        
        logger.info(f"get_news_by_stock called with stock_code={stock_code}, days={days}, limit={limit}")
        
        service = get_news_service()
        news_items = _run_async_safely(service.get_news_by_stock(stock_code, days, limit))
        
        if not news_items:
            return {
                "message": f"暂无 {stock_code} 的相关新闻",
                "stock_code": stock_code,
                "news_count": 0,
            }
        
        # 格式化新闻列表供 LLM 理解
        formatted_news = []
        for news in news_items[:10]:  # 限制返回给 LLM 的数量
            formatted_news.append({
                "id": news.id,
                "title": news.title,
                "source": news.source,
                "category": news.category,
                "publish_time": news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else "未知",
                "content_preview": news.content[:100] + "..." if len(news.content) > 100 else news.content,
            })
        
        return {
            "stock_code": stock_code,
            "news_count": len(news_items),
            "displayed_count": len(formatted_news),
            "news_list": formatted_news,
        }
    except Exception as e:
        logger.error(f"get_news_by_stock error: {e}", exc_info=True)
        return {"message": f"获取新闻失败: {str(e)}", "stock_code": stock_code}


def get_market_news(category: str = "all", limit: int = 20) -> Dict[str, Any]:
    """获取市场整体财经新闻
    
    Args:
        category: 新闻分类，可选值: all(全部)/announcement(公告)/flash(快讯)/analysis(分析)/policy(政策)/industry(行业)
        limit: 返回数量，默认20条
    
    Returns:
        市场新闻列表
    """
    try:
        from stock_datasource.modules.news.service import get_news_service
        from stock_datasource.modules.news.schemas import NewsCategory
        
        logger.info(f"get_market_news called with category={category}, limit={limit}")
        
        # 转换分类
        category_map = {
            "all": NewsCategory.ALL,
            "announcement": NewsCategory.ANNOUNCEMENT,
            "flash": NewsCategory.FLASH,
            "analysis": NewsCategory.ANALYSIS,
            "policy": NewsCategory.POLICY,
            "industry": NewsCategory.INDUSTRY,
        }
        news_category = category_map.get(category.lower(), NewsCategory.ALL)
        
        service = get_news_service()
        news_items = _run_async_safely(service.get_market_news(news_category, limit))
        
        if not news_items:
            return {
                "message": "暂无市场新闻",
                "category": category,
                "news_count": 0,
            }
        
        # 格式化新闻列表
        formatted_news = []
        for news in news_items[:15]:
            formatted_news.append({
                "id": news.id,
                "title": news.title,
                "source": news.source,
                "category": news.category,
                "publish_time": news.publish_time.strftime("%Y-%m-%d %H:%M") if news.publish_time else "未知",
            })
        
        return {
            "category": category,
            "news_count": len(news_items),
            "displayed_count": len(formatted_news),
            "news_list": formatted_news,
        }
    except Exception as e:
        logger.error(f"get_market_news error: {e}", exc_info=True)
        return {"message": f"获取市场新闻失败: {str(e)}", "category": category}


def analyze_news_sentiment(stock_code: str, days: int = 7, limit: int = 10) -> Dict[str, Any]:
    """分析股票相关新闻的情绪倾向
    
    Args:
        stock_code: 股票代码，如 600519.SH
        days: 查询天数，默认7天
        limit: 分析新闻数量，默认10条
    
    Returns:
        情绪分析结果，包含利好/利空/中性统计
    """
    try:
        from stock_datasource.modules.news.service import get_news_service
        
        logger.info(f"analyze_news_sentiment called with stock_code={stock_code}")
        
        service = get_news_service()
        
        # 获取新闻
        news_items = _run_async_safely(service.get_news_by_stock(stock_code, days, limit))
        
        if not news_items:
            return {
                "message": f"暂无 {stock_code} 的新闻可供分析",
                "stock_code": stock_code,
            }
        
        # 分析情绪
        sentiments = _run_async_safely(
            service.analyze_news_sentiment(news_items, f"股票代码: {stock_code}")
        )
        
        # 统计情绪分布
        positive_count = sum(1 for s in sentiments if s.sentiment == "positive")
        negative_count = sum(1 for s in sentiments if s.sentiment == "negative")
        neutral_count = sum(1 for s in sentiments if s.sentiment == "neutral")
        
        # 计算综合情绪分数
        avg_score = sum(s.score for s in sentiments) / len(sentiments) if sentiments else 0
        
        # 整体情绪判断
        if avg_score > 0.2:
            overall_sentiment = "偏利好"
        elif avg_score < -0.2:
            overall_sentiment = "偏利空"
        else:
            overall_sentiment = "中性"
        
        # 详细结果
        details = []
        for s in sentiments:
            sentiment_label = {"positive": "利好", "negative": "利空", "neutral": "中性"}.get(s.sentiment, "中性")
            impact_label = {"high": "重大", "medium": "中等", "low": "轻微"}.get(s.impact_level, "轻微")
            details.append({
                "title": s.title,
                "sentiment": sentiment_label,
                "impact": impact_label,
                "reasoning": s.reasoning,
            })
        
        return {
            "stock_code": stock_code,
            "analyzed_count": len(sentiments),
            "sentiment_stats": {
                "positive": positive_count,
                "negative": negative_count,
                "neutral": neutral_count,
            },
            "average_score": round(avg_score, 2),
            "overall_sentiment": overall_sentiment,
            "details": details[:5],  # 只返回前5条详情
        }
    except Exception as e:
        logger.error(f"analyze_news_sentiment error: {e}", exc_info=True)
        return {"message": f"情绪分析失败: {str(e)}", "stock_code": stock_code}


def get_hot_topics(limit: int = 10) -> Dict[str, Any]:
    """获取当前市场热点话题
    
    Args:
        limit: 返回热点数量，默认10个
    
    Returns:
        热点话题列表
    """
    try:
        from stock_datasource.modules.news.service import get_news_service
        
        logger.info(f"get_hot_topics called with limit={limit}")
        
        service = get_news_service()
        topics = _run_async_safely(service.get_hot_topics(limit))
        
        if not topics:
            return {
                "message": "暂无热点话题",
                "topic_count": 0,
            }
        
        # 格式化热点列表
        formatted_topics = []
        for topic in topics:
            formatted_topics.append({
                "topic": topic.topic,
                "keywords": topic.keywords,
                "heat_score": topic.heat_score,
                "summary": topic.summary,
                "news_count": topic.news_count,
            })
        
        return {
            "topic_count": len(topics),
            "hot_topics": formatted_topics,
        }
    except Exception as e:
        logger.error(f"get_hot_topics error: {e}", exc_info=True)
        return {"message": f"获取热点失败: {str(e)}"}


def summarize_news(stock_code: str = None, focus: str = None, limit: int = 20) -> Dict[str, Any]:
    """AI 生成新闻摘要和要点
    
    Args:
        stock_code: 股票代码（可选），不提供则汇总市场新闻
        focus: 关注重点（可选），如"业绩"、"政策"等
        limit: 摘要新闻数量，默认20条
    
    Returns:
        新闻摘要，包含要点和情绪概述
    """
    try:
        from stock_datasource.modules.news.service import get_news_service
        from stock_datasource.modules.news.schemas import NewsCategory
        
        logger.info(f"summarize_news called with stock_code={stock_code}, focus={focus}")
        
        service = get_news_service()
        
        # 获取新闻
        if stock_code:
            news_items = _run_async_safely(service.get_news_by_stock(stock_code, days=7, limit=limit))
        else:
            news_items = _run_async_safely(service.get_market_news(NewsCategory.ALL, limit))
        
        if not news_items:
            return {
                "message": "暂无新闻可供摘要",
                "stock_code": stock_code,
            }
        
        # 生成摘要
        result = _run_async_safely(service.summarize_news(news_items, focus))
        
        return {
            "stock_code": stock_code or "市场整体",
            "focus": focus,
            "news_count": len(news_items),
            "summary": result.get("summary", ""),
            "key_points": result.get("key_points", []),
            "sentiment_overview": result.get("sentiment_overview", ""),
        }
    except Exception as e:
        logger.error(f"summarize_news error: {e}", exc_info=True)
        return {"message": f"生成摘要失败: {str(e)}"}


class NewsAnalystAgent(LangGraphAgent):
    """News Analyst Agent for AI-powered financial news analysis.
    
    Inherits from LangGraphAgent and provides:
    - Stock news retrieval and analysis
    - Market news tracking
    - Sentiment analysis
    - Hot topics discovery
    - News summarization
    """
    
    def __init__(self):
        config = AgentConfig(
            name="NewsAnalystAgent",
            description="负责财经新闻分析，提供新闻获取、情绪分析、热点追踪、新闻摘要等功能",
            temperature=0.5,  # 适中的温度，平衡准确性和创造性
            max_tokens=2500,
        )
        super().__init__(config)
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy load LLM client with Langfuse integration."""
        if self._llm_client is None:
            try:
                from stock_datasource.llm.client import get_llm_client
                self._llm_client = get_llm_client()
            except Exception as e:
                logger.warning(f"Failed to get LLM client: {e}")
        return self._llm_client
    
    def get_tools(self) -> List[Callable]:
        """Return news analysis tools."""
        return [
            get_news_by_stock,
            get_market_news,
            analyze_news_sentiment,
            get_hot_topics,
            summarize_news,
        ]
    
    def get_system_prompt(self) -> str:
        """Return system prompt for news analysis."""
        return NEWS_ANALYST_SYSTEM_PROMPT


# Singleton instance
_news_analyst_agent: Optional[NewsAnalystAgent] = None


def get_news_analyst_agent() -> NewsAnalystAgent:
    """Get NewsAnalystAgent singleton instance."""
    global _news_analyst_agent
    if _news_analyst_agent is None:
        _news_analyst_agent = NewsAnalystAgent()
    return _news_analyst_agent
