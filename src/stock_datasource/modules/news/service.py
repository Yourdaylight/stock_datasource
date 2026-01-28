"""News service implementation.

Provides news data retrieval, sentiment analysis, and hot topics tracking.
Data sources:
- Tushare: 上市公司公告数据 (anns 接口)
- Sina: 财经新闻 (免费 API)
"""

import os
import re
import json
import hashlib
import logging
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .schemas import (
    NewsItem,
    NewsSentiment,
    HotTopic,
    NewsCategory,
    SentimentType,
    ImpactLevel,
)
from .storage import get_news_storage

logger = logging.getLogger(__name__)


# Redis 缓存配置
NEWS_CACHE_PREFIX = "news:"
NEWS_CACHE_TTL_FLASH = 300       # 快讯缓存5分钟
NEWS_CACHE_TTL_ANNOUNCEMENT = 3600  # 公告缓存1小时
NEWS_CACHE_TTL_HOT_TOPICS = 600  # 热点缓存10分钟


def _get_redis():
    """Get Redis client."""
    try:
        from stock_datasource.services.cache_service import get_cache_service
        cache = get_cache_service()
        return cache._get_redis() if cache.available else None
    except Exception as e:
        logger.warning(f"Failed to get Redis client: {e}")
        return None


def _get_tushare_pro():
    """Get Tushare pro API instance."""
    try:
        import tushare as ts
        token = os.getenv("TUSHARE_TOKEN")
        if not token:
            logger.warning("TUSHARE_TOKEN not set")
            return None
        return ts.pro_api(token)
    except Exception as e:
        logger.warning(f"Failed to get Tushare pro API: {e}")
        return None


def _generate_news_id(source: str, title: str, publish_time: Optional[datetime] = None) -> str:
    """Generate unique news ID based on content hash."""
    content = f"{source}:{title}:{publish_time.isoformat() if publish_time else ''}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


class NewsService:
    """新闻服务
    
    提供新闻获取、情绪分析、热点追踪等功能。
    """
    
    def __init__(self):
        self._tushare_pro = None
        self._llm_client = None
    
    @property
    def tushare_pro(self):
        """Lazy load Tushare pro API."""
        if self._tushare_pro is None:
            self._tushare_pro = _get_tushare_pro()
        return self._tushare_pro
    
    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            try:
                from stock_datasource.llm.client import get_llm_client
                self._llm_client = get_llm_client()
            except Exception as e:
                logger.warning(f"Failed to get LLM client: {e}")
        return self._llm_client
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached data."""
        redis = _get_redis()
        if redis:
            try:
                data = redis.get(f"{NEWS_CACHE_PREFIX}{key}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.debug(f"Cache get failed: {e}")
        return None
    
    def _set_cache(self, key: str, value: Any, ttl: int = 300):
        """Set cached data."""
        redis = _get_redis()
        if redis:
            try:
                redis.setex(f"{NEWS_CACHE_PREFIX}{key}", ttl, json.dumps(value, default=str))
            except Exception as e:
                logger.debug(f"Cache set failed: {e}")
    
    async def get_news_by_stock(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsItem]:
        """获取指定股票的相关新闻和公告
        
        Args:
            stock_code: 股票代码，如 600519.SH
            days: 查询天数，默认7天
            limit: 返回数量，默认20条
            
        Returns:
            新闻列表
        """
        # 尝试从缓存获取
        cache_key = f"stock:{stock_code}:{days}:{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for stock news: {stock_code}")
            return [NewsItem(**item) for item in cached]
        
        news_items: List[NewsItem] = []
        
        # 1. 获取 Tushare 公告数据
        announcements = await self._get_tushare_announcements(stock_code, days, limit)
        news_items.extend(announcements)
        
        # 2. 获取 Sina 新闻
        sina_news = await self._get_sina_stock_news(stock_code, limit // 2)
        news_items.extend(sina_news)
        
        # 按发布时间排序
        news_items.sort(key=lambda x: x.publish_time or datetime.min, reverse=True)
        
        # 限制返回数量
        news_items = news_items[:limit]
        
        # 补齐情绪分析
        sentiments = await self.analyze_news_sentiment(
            news_items,
            stock_context=f"股票代码: {stock_code}"
        )
        self._apply_sentiments_to_news(news_items, sentiments)
        
        # 缓存结果
        self._set_cache(
            cache_key,
            [item.model_dump() for item in news_items],
            NEWS_CACHE_TTL_ANNOUNCEMENT
        )
        
        return news_items
    
    async def get_market_news(
        self,
        category: NewsCategory = NewsCategory.ALL,
        limit: int = 20,
        force_refresh: bool = False,
    ) -> List[NewsItem]:
        """获取市场整体财经新闻
        
        优先从本地文件缓存读取，大幅提升响应速度。
        如果缓存为空或强制刷新，则从外部 API 获取并保存。
        
        Args:
            category: 新闻分类
            limit: 返回数量
            force_refresh: 是否强制刷新（跳过缓存）
            
        Returns:
            新闻列表
        """
        category_str = category.value if isinstance(category, NewsCategory) else str(category)
        
        # 1. 尝试从本地文件缓存读取（毫秒级）
        if not force_refresh:
            try:
                storage = get_news_storage()
                cached_news = storage.get_latest_news(
                    limit=limit * 2,  # 多获取一些，用于筛选
                    category=category_str if category_str != "all" else None,
                )
                if cached_news:
                    logger.debug(f"File cache hit: {len(cached_news)} items")
                    news_items = [NewsItem(**item) for item in cached_news]
                    
                    # 按分类过滤（双重保险）
                    if category != NewsCategory.ALL:
                        news_items = [n for n in news_items if n.category == category]
                    
                    news_items = news_items[:limit]
                    sentiments = await self.analyze_news_sentiment(news_items)
                    self._apply_sentiments_to_news(news_items, sentiments)
                    
                    return news_items
            except Exception as e:
                logger.warning(f"Failed to read from file storage: {e}")
        
        # 2. 尝试从 Redis 缓存获取
        cache_key = f"market:{category}:{limit}"
        if not force_refresh:
            cached = self._get_cache(cache_key)
            if cached:
                logger.debug(f"Redis cache hit for market news: {category}")
                return [NewsItem(**item) for item in cached]
        
        # 3. 从外部 API 获取
        logger.info("Fetching news from external API...")
        news_items: List[NewsItem] = []
        
        # 获取 Sina 财经新闻
        sina_news = await self._get_sina_finance_news(limit)
        news_items.extend(sina_news)
        
        # 4. 保存到本地文件存储
        if news_items:
            self._save_news_to_storage(news_items)
        
        # 按分类过滤
        if category != NewsCategory.ALL:
            news_items = [n for n in news_items if n.category == category]
        
        # 按发布时间排序
        news_items.sort(key=lambda x: x.publish_time or datetime.min, reverse=True)
        
        # 限制返回数量
        news_items = news_items[:limit]
        
        sentiments = await self.analyze_news_sentiment(news_items)
        self._apply_sentiments_to_news(news_items, sentiments)
        
        # 缓存到 Redis
        self._set_cache(
            cache_key,
            [item.model_dump() for item in news_items],
            NEWS_CACHE_TTL_FLASH
        )
        
        return news_items
    
    def _save_news_to_storage(self, news_items: List[NewsItem]):
        """将新闻保存到本地文件存储"""
        try:
            storage = get_news_storage()
            
            # 按来源分组保存
            sina_news = []
            tushare_news = []
            
            for item in news_items:
                item_dict = item.model_dump()
                if item.source == "sina":
                    sina_news.append(item_dict)
                elif item.source == "tushare":
                    tushare_news.append(item_dict)
                else:
                    sina_news.append(item_dict)  # 默认归类到 sina
            
            if sina_news:
                saved = storage.save_news(sina_news, "sina")
                logger.info(f"Saved {saved} sina news to file storage")
            
            if tushare_news:
                saved = storage.save_news(tushare_news, "tushare")
                logger.info(f"Saved {saved} tushare news to file storage")
                
        except Exception as e:
            logger.warning(f"Failed to save news to storage: {e}")

    async def backfill_cached_news_sentiment(
        self,
        days: int = 7,
        sources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """批量补齐缓存新闻的情绪字段
        
        Args:
            days: 处理最近 N 天的缓存文件
            sources: 指定来源（sina/tushare），不传则处理全部
        
        Returns:
            处理统计信息
        """
        storage = get_news_storage()
        files = storage.list_news_files(days=days, sources=sources)
        
        total_files = len(files)
        total_items = 0
        updated_items = 0
        updated_files = 0
        
        for file_path in files:
            try:
                raw_items = storage.load_news_file(file_path)
                if not raw_items:
                    continue
                total_items += len(raw_items)
                
                news_items = [NewsItem(**item) for item in raw_items]
                missing = [item for item in news_items if item.sentiment is None]
                if not missing:
                    continue
                
                sentiments = await self.analyze_news_sentiment(missing)
                self._apply_sentiments_to_news(missing, sentiments)
                
                updated_items += len(missing)
                updated_files += 1
                
                updated_raw = [item.model_dump() for item in news_items]
                storage.save_news_file(file_path, updated_raw)
            except Exception as e:
                logger.warning(f"Failed to backfill sentiment for {file_path}: {e}")
                continue
        
        storage.force_refresh_cache()
        
        return {
            "files": total_files,
            "updated_files": updated_files,
            "items": total_items,
            "updated_items": updated_items,
        }
    
    async def search_news(
        self,
        keyword: str,
        limit: int = 20,
    ) -> List[NewsItem]:
        """按关键词搜索新闻
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量
            
        Returns:
            新闻列表
        """
        # 获取市场新闻
        all_news = await self.get_market_news(NewsCategory.ALL, limit * 2)
        
        # 关键词匹配
        keyword_lower = keyword.lower()
        matched = [
            news for news in all_news
            if keyword_lower in news.title.lower() or keyword_lower in news.content.lower()
        ]
        
        return matched[:limit]
    
    async def analyze_news_sentiment(
        self,
        news_items: List[NewsItem],
        stock_context: Optional[str] = None,
    ) -> List[NewsSentiment]:
        """分析新闻情绪
        
        使用 LLM 分析新闻情绪倾向。
        
        Args:
            news_items: 新闻列表
            stock_context: 股票背景信息（可选）
            
        Returns:
            情绪分析结果列表
        """
        if not news_items:
            return []
        
        results: List[NewsSentiment] = []
        
        # 构建分析 prompt
        prompt = self._build_sentiment_prompt(news_items, stock_context)
        
        try:
            if self.llm_client:
                result = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                response = result.get("content", "") if isinstance(result, dict) else str(result)
                
                # 解析结果
                results = self._parse_sentiment_response(response, news_items)
            else:
                # 降级：使用简单规则
                results = self._simple_sentiment_analysis(news_items)
        except Exception as e:
            logger.warning(f"LLM sentiment analysis failed: {e}")
            results = self._simple_sentiment_analysis(news_items)
        
        return results
    
    async def get_hot_topics(
        self,
        limit: int = 10,
    ) -> List[HotTopic]:
        """获取当前市场热点话题
        
        Args:
            limit: 返回数量
            
        Returns:
            热点话题列表
        """
        # 尝试从缓存获取
        cache_key = f"hot_topics:{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug("Cache hit for hot topics")
            return [HotTopic(**item) for item in cached]
        
        # 获取最近新闻
        recent_news = await self.get_market_news(NewsCategory.ALL, limit=50)
        
        if not recent_news:
            return []
        
        # 使用 LLM 提取热点
        topics = await self._extract_hot_topics(recent_news, limit)
        
        # 缓存结果
        self._set_cache(
            cache_key,
            [topic.model_dump() for topic in topics],
            NEWS_CACHE_TTL_HOT_TOPICS
        )
        
        return topics
    
    async def summarize_news(
        self,
        news_items: List[NewsItem],
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """AI 生成新闻摘要
        
        Args:
            news_items: 新闻列表
            focus: 关注重点（可选）
            
        Returns:
            摘要结果，包含 summary, key_points, sentiment_overview
        """
        if not news_items:
            return {
                "summary": "暂无新闻数据",
                "key_points": [],
                "sentiment_overview": "无法分析",
            }
        
        prompt = self._build_summary_prompt(news_items, focus)
        
        try:
            if self.llm_client:
                result = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                )
                response = result.get("content", "") if isinstance(result, dict) else str(result)
                return self._parse_summary_response(response)
            else:
                # 降级：简单摘要
                return self._simple_summary(news_items)
        except Exception as e:
            logger.warning(f"LLM summarize failed: {e}")
            return self._simple_summary(news_items)
    
    # =========================================================================
    # Tushare 数据源
    # =========================================================================
    
    async def _get_tushare_announcements(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsItem]:
        """获取 Tushare 公告数据"""
        if not self.tushare_pro:
            return []
        
        try:
            # 计算日期范围
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            
            # 调用 Tushare anns 接口
            # 注意：anns 接口可能需要较高权限
            df = self.tushare_pro.anns(
                ts_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                fields="ts_code,ann_date,title,content,pub_time"
            )
            
            if df is None or df.empty:
                logger.debug(f"No announcements found for {stock_code}")
                return []
            
            news_items = []
            for _, row in df.head(limit).iterrows():
                try:
                    pub_time_str = row.get('pub_time') or row.get('ann_date')
                    pub_time = None
                    if pub_time_str:
                        try:
                            if len(str(pub_time_str)) == 8:
                                pub_time = datetime.strptime(str(pub_time_str), "%Y%m%d")
                            else:
                                pub_time = datetime.strptime(str(pub_time_str)[:19], "%Y-%m-%d %H:%M:%S")
                        except:
                            pass
                    
                    title = str(row.get('title', ''))
                    content = str(row.get('content', ''))[:500]  # 限制内容长度
                    
                    news_item = NewsItem(
                        id=_generate_news_id("tushare", title, pub_time),
                        title=title,
                        content=content,
                        source="tushare",
                        publish_time=pub_time,
                        stock_codes=[stock_code],
                        category=NewsCategory.ANNOUNCEMENT,
                    )
                    news_items.append(news_item)
                except Exception as e:
                    logger.debug(f"Failed to parse announcement row: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.warning(f"Failed to get Tushare announcements: {e}")
            return []
    
    # =========================================================================
    # Sina 数据源
    # =========================================================================
    
    async def _get_sina_stock_news(
        self,
        stock_code: str,
        limit: int = 10,
    ) -> List[NewsItem]:
        """获取 Sina 股票相关新闻"""
        try:
            # 提取纯股票代码（去掉后缀）
            pure_code = stock_code.split('.')[0]
            
            # Sina 股票新闻 API
            url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCB_AllNewsStock/symbol/{pure_code}.phtml"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                
                if response.status_code != 200:
                    logger.warning(f"Sina stock news request failed: {response.status_code}")
                    return []
                
                # 解析 HTML 提取新闻
                news_items = self._parse_sina_stock_news_html(response.text, stock_code, limit)
                return news_items
                
        except Exception as e:
            logger.warning(f"Failed to get Sina stock news: {e}")
            return []
    
    async def _get_sina_finance_news(
        self,
        limit: int = 20,
    ) -> List[NewsItem]:
        """获取 Sina 财经新闻"""
        try:
            # Sina 财经滚动新闻 API
            url = "https://feed.mix.sina.com.cn/api/roll/get"
            params = {
                "pageid": "153",  # 财经频道
                "num": limit,
                "lid": "2509",
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                
                if response.status_code != 200:
                    logger.warning(f"Sina finance news request failed: {response.status_code}")
                    return []
                
                data = response.json()
                news_items = self._parse_sina_finance_news(data, limit)
                return news_items
                
        except Exception as e:
            logger.warning(f"Failed to get Sina finance news: {e}")
            return []
    
    def _parse_sina_stock_news_html(
        self,
        html: str,
        stock_code: str,
        limit: int,
    ) -> List[NewsItem]:
        """解析 Sina 股票新闻 HTML"""
        news_items = []
        
        # 简单的正则匹配提取新闻
        # 实际生产中建议使用 BeautifulSoup
        pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>\s*<span[^>]*>(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})</span>'
        matches = re.findall(pattern, html)
        
        for url, title, time_str in matches[:limit]:
            try:
                pub_time = datetime.strptime(time_str.strip(), "%Y-%m-%d %H:%M")
                news_item = NewsItem(
                    id=_generate_news_id("sina", title, pub_time),
                    title=title.strip(),
                    content="",
                    source="sina",
                    publish_time=pub_time,
                    stock_codes=[stock_code],
                    category=NewsCategory.FLASH,
                    url=url,
                )
                news_items.append(news_item)
            except Exception as e:
                logger.debug(f"Failed to parse news item: {e}")
                continue
        
        return news_items
    
    def _parse_sina_finance_news(
        self,
        data: Dict[str, Any],
        limit: int,
    ) -> List[NewsItem]:
        """解析 Sina 财经新闻 API 响应"""
        news_items = []
        
        result = data.get("result", {})
        items = result.get("data", [])
        
        for item in items[:limit]:
            try:
                title = item.get("title", "")
                summary = item.get("summary", "") or item.get("intro", "")
                url = item.get("url", "")
                create_time = item.get("ctime", "")
                
                pub_time = None
                if create_time:
                    try:
                        pub_time = datetime.fromtimestamp(int(create_time))
                    except:
                        pass
                
                # 根据标题判断分类
                category = self._categorize_news(title)
                
                news_item = NewsItem(
                    id=_generate_news_id("sina", title, pub_time),
                    title=title,
                    content=summary[:500] if summary else "",
                    source="sina",
                    publish_time=pub_time,
                    stock_codes=[],
                    category=category,
                    url=url,
                )
                news_items.append(news_item)
            except Exception as e:
                logger.debug(f"Failed to parse finance news item: {e}")
                continue
        
        return news_items
    
    def _categorize_news(self, title: str) -> NewsCategory:
        """根据标题判断新闻分类"""
        title_lower = title.lower()
        
        if any(kw in title_lower for kw in ["公告", "披露", "年报", "季报", "业绩"]):
            return NewsCategory.ANNOUNCEMENT
        elif any(kw in title_lower for kw in ["政策", "央行", "监管", "法规", "条例"]):
            return NewsCategory.POLICY
        elif any(kw in title_lower for kw in ["行业", "产业", "板块", "龙头"]):
            return NewsCategory.INDUSTRY
        elif any(kw in title_lower for kw in ["分析", "研报", "研究", "点评"]):
            return NewsCategory.ANALYSIS
        else:
            return NewsCategory.FLASH
    
    # =========================================================================
    # LLM 相关方法
    # =========================================================================
    
    def _build_sentiment_prompt(
        self,
        news_items: List[NewsItem],
        stock_context: Optional[str] = None,
    ) -> str:
        """构建情绪分析 prompt"""
        news_text = "\n".join([
            f"{i+1}. [ID:{item.id}] {item.title}"
            for i, item in enumerate(news_items[:10])  # 限制数量避免 token 过多
        ])
        
        context_text = f"\n股票背景: {stock_context}" if stock_context else ""
        
        return f"""请分析以下财经新闻的情绪倾向。

对于每条新闻，请判断：
1. sentiment: positive(利好)/negative(利空)/neutral(中性)
2. score: -1.0到1.0的情绪分数
3. impact_level: high(重大)/medium(中等)/low(轻微)
4. reasoning: 简短分析理由（不超过50字）
{context_text}

新闻列表：
{news_text}

请以JSON数组格式输出，每个元素包含：news_id, sentiment, score, impact_level, reasoning
只输出JSON，不要其他文字。"""
    
    def _parse_sentiment_response(
        self,
        response: str,
        news_items: List[NewsItem],
    ) -> List[NewsSentiment]:
        """解析情绪分析响应"""
        results = []
        
        try:
            # 尝试从响应中提取 JSON
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                # 创建 news_id 到 title 的映射
                id_to_title = {item.id: item.title for item in news_items}
                
                for item in data:
                    news_id = item.get("news_id", "")
                    sentiment_str = item.get("sentiment", "neutral")
                    
                    # 转换情绪类型
                    sentiment = SentimentType.NEUTRAL
                    if sentiment_str == "positive":
                        sentiment = SentimentType.POSITIVE
                    elif sentiment_str == "negative":
                        sentiment = SentimentType.NEGATIVE
                    
                    # 转换影响程度
                    impact_str = item.get("impact_level", "low")
                    impact = ImpactLevel.LOW
                    if impact_str == "high":
                        impact = ImpactLevel.HIGH
                    elif impact_str == "medium":
                        impact = ImpactLevel.MEDIUM
                    
                    results.append(NewsSentiment(
                        news_id=news_id,
                        title=id_to_title.get(news_id, ""),
                        sentiment=sentiment,
                        score=float(item.get("score", 0)),
                        reasoning=item.get("reasoning", ""),
                        impact_level=impact,
                    ))
        except Exception as e:
            logger.warning(f"Failed to parse sentiment response: {e}")
        
        return results
    
    def _simple_sentiment_analysis(
        self,
        news_items: List[NewsItem],
    ) -> List[NewsSentiment]:
        """简单规则情绪分析（降级方案）"""
        positive_keywords = ["利好", "上涨", "增长", "突破", "新高", "加仓", "买入"]
        negative_keywords = ["利空", "下跌", "亏损", "减持", "风险", "下调", "卖出"]
        
        results = []
        for item in news_items:
            title_lower = item.title.lower()
            
            pos_count = sum(1 for kw in positive_keywords if kw in title_lower)
            neg_count = sum(1 for kw in negative_keywords if kw in title_lower)
            
            if pos_count > neg_count:
                sentiment = SentimentType.POSITIVE
                score = min(0.3 + pos_count * 0.2, 1.0)
            elif neg_count > pos_count:
                sentiment = SentimentType.NEGATIVE
                score = max(-0.3 - neg_count * 0.2, -1.0)
            else:
                sentiment = SentimentType.NEUTRAL
                score = 0.0
            
            results.append(NewsSentiment(
                news_id=item.id,
                title=item.title,
                sentiment=sentiment,
                score=score,
                reasoning="基于关键词规则分析",
                impact_level=ImpactLevel.LOW,
            ))
        
        return results
    
    async def _extract_hot_topics(
        self,
        news_items: List[NewsItem],
        limit: int,
    ) -> List[HotTopic]:
        """使用 LLM 提取热点话题"""
        if not news_items:
            return []
        
        # 构建 prompt
        news_text = "\n".join([
            f"- {item.title}" for item in news_items[:30]
        ])
        
        prompt = f"""请从以下财经新闻中提取当前市场热点话题。

新闻列表：
{news_text}

请提取 {limit} 个最热门的话题，对于每个话题：
1. topic: 话题名称（简短）
2. keywords: 3-5个关键词
3. heat_score: 热度分数（0-100）
4. summary: 话题简要描述（不超过100字）

请以JSON数组格式输出，只输出JSON。"""
        
        try:
            if self.llm_client:
                result = await self.llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                )
                response = result.get("content", "") if isinstance(result, dict) else str(result)
                return self._parse_hot_topics_response(response, limit)
        except Exception as e:
            logger.warning(f"LLM hot topics extraction failed: {e}")
        
        # 降级：简单关键词统计
        return self._simple_hot_topics(news_items, limit)
    
    def _parse_hot_topics_response(
        self,
        response: str,
        limit: int,
    ) -> List[HotTopic]:
        """解析热点话题响应"""
        results = []
        
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                for item in data[:limit]:
                    results.append(HotTopic(
                        topic=item.get("topic", ""),
                        keywords=item.get("keywords", []),
                        heat_score=float(item.get("heat_score", 0)),
                        related_stocks=[],
                        news_count=1,
                        summary=item.get("summary", ""),
                    ))
        except Exception as e:
            logger.warning(f"Failed to parse hot topics response: {e}")
        
        return results
    
    def _simple_hot_topics(
        self,
        news_items: List[NewsItem],
        limit: int,
    ) -> List[HotTopic]:
        """简单关键词统计提取热点（降级方案）"""
        # 简单统计关键词频率
        keyword_counts: Dict[str, int] = {}
        
        hot_keywords = [
            "AI", "人工智能", "芯片", "半导体", "新能源", "光伏", "储能",
            "消费", "医药", "银行", "地产", "汽车", "科技", "创新"
        ]
        
        for item in news_items:
            for kw in hot_keywords:
                if kw in item.title:
                    keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
        
        # 按频率排序
        sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for kw, count in sorted_keywords[:limit]:
            results.append(HotTopic(
                topic=kw,
                keywords=[kw],
                heat_score=min(count * 10, 100),
                related_stocks=[],
                news_count=count,
                summary=f"近期有{count}条新闻涉及{kw}相关内容",
            ))
        
        return results
    
    def _build_summary_prompt(
        self,
        news_items: List[NewsItem],
        focus: Optional[str] = None,
    ) -> str:
        """构建新闻摘要 prompt"""
        news_text = "\n".join([
            f"- {item.title}" + (f": {item.content[:100]}..." if item.content else "")
            for item in news_items[:20]
        ])
        
        focus_text = f"\n请重点关注: {focus}" if focus else ""
        
        return f"""请对以下财经新闻进行摘要分析。
{focus_text}

新闻列表：
{news_text}

请输出：
1. summary: 整体摘要（200字以内）
2. key_points: 3-5个要点（数组）
3. sentiment_overview: 整体市场情绪概述（50字以内）

请以JSON格式输出。"""
    
    def _parse_summary_response(self, response: str) -> Dict[str, Any]:
        """解析摘要响应"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "summary": data.get("summary", ""),
                    "key_points": data.get("key_points", []),
                    "sentiment_overview": data.get("sentiment_overview", ""),
                }
        except Exception as e:
            logger.warning(f"Failed to parse summary response: {e}")
        
        return {
            "summary": response[:500] if response else "摘要生成失败",
            "key_points": [],
            "sentiment_overview": "",
        }
    
    def _simple_summary(self, news_items: List[NewsItem]) -> Dict[str, Any]:
        """简单摘要（降级方案）"""
        titles = [item.title for item in news_items[:5]]
        
        return {
            "summary": f"共有 {len(news_items)} 条相关新闻。最新动态包括：" + "；".join(titles),
            "key_points": titles[:3],
            "sentiment_overview": "市场情绪需进一步分析",
        }

    def _apply_sentiments_to_news(
        self,
        news_items: List[NewsItem],
        sentiments: List[NewsSentiment],
    ) -> None:
        """将情绪分析结果写入新闻列表"""
        if not news_items or not sentiments:
            return
        sentiment_map = {item.news_id: item for item in sentiments}
        for news_item in news_items:
            sentiment = sentiment_map.get(news_item.id)
            if not sentiment:
                continue
            if not sentiment.news_id:
                sentiment.news_id = news_item.id
            if not sentiment.title:
                sentiment.title = news_item.title
            news_item.sentiment = sentiment
            news_item.sentiment_score = sentiment.score
            news_item.sentiment_reasoning = sentiment.reasoning
            news_item.impact_level = sentiment.impact_level


# Singleton instance
_news_service: Optional[NewsService] = None


def get_news_service() -> NewsService:
    """Get NewsService singleton."""
    global _news_service
    if _news_service is None:
        _news_service = NewsService()
    return _news_service