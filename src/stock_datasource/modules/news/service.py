"""News service implementation.

Provides news data retrieval, sentiment analysis, and hot topics tracking.
Data sources:
- Tushare: news / major_news / cctv_news / anns_d / research_report / npr
- Sina: 财经新闻（兜底）
"""

import os
import re
import json
import hashlib
import logging
import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from .schemas import (
    NewsItem,
    NewsSentiment,
    NewsCategory,
    SentimentType,
    ImpactLevel,
)
from .storage import get_news_storage

logger = logging.getLogger(__name__)


# Redis 缓存配置
NEWS_CACHE_PREFIX = "news:"
NEWS_CACHE_TTL_FLASH = 300            # 快讯缓存5分钟
NEWS_CACHE_TTL_ANNOUNCEMENT = 3600    # 公告缓存1小时
NEWS_CACHE_TTL_HOT_TOPICS = int(os.getenv("NEWS_CACHE_TTL_HOT_TOPICS", "120"))  # 热点缓存默认2分钟
NEWS_CACHE_TTL_MAJOR = 1800           # 通讯缓存30分钟
NEWS_CACHE_TTL_CCTV = 7200            # 联播缓存2小时
NEWS_CACHE_TTL_RESEARCH = 3600        # 研报缓存1小时
NEWS_CACHE_TTL_NPR = 14400            # 政策缓存4小时

NEWS_SRC_LIST = [
    "sina", "wallstreetcn", "10jqka", "eastmoney", "yuncaijing",
    "fenghuang", "jinrongjie", "cls", "yicai"
]

MAJOR_NEWS_SRC_LIST = [
    "新华社", "凤凰财经", "同花顺", "新浪财经", "华尔街见闻", "中证网", "财新网", "第一财经", "财联社"
]


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
        self._fetch_semaphore = asyncio.Semaphore(int(os.getenv("NEWS_FETCH_MAX_CONCURRENCY", "4")))
        self._request_interval = float(os.getenv("NEWS_REQUEST_INTERVAL", "1.0"))
        self._use_sina_fallback = os.getenv("NEWS_ENABLE_SINA_FALLBACK", "true").lower() in {"1", "true", "yes"}
        self._last_failed_sources: List[str] = []
        self._last_partial: bool = False
    
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

    def consume_fetch_meta(self) -> Tuple[bool, List[str]]:
        """获取并清空最近一次抓取元数据。"""
        partial = self._last_partial
        failed_sources = list(self._last_failed_sources)
        self._last_partial = False
        self._last_failed_sources = []
        return partial, failed_sources

    def _set_fetch_meta(self, failed_sources: List[str]):
        self._last_failed_sources = sorted(set(failed_sources))
        self._last_partial = len(self._last_failed_sources) > 0

    async def _run_tushare_with_retry(self, source_name: str, method_name: str, **kwargs):
        if not self.tushare_pro:
            raise RuntimeError("tushare unavailable")

        max_retries = 3
        delay = 0.8
        last_exc: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                async with self._fetch_semaphore:
                    df = await asyncio.to_thread(getattr(self.tushare_pro, method_name), **kwargs)
                await asyncio.sleep(self._request_interval)
                return df
            except Exception as exc:
                last_exc = exc
                logger.warning(f"{source_name} failed on attempt {attempt}: {exc}")
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2

        raise RuntimeError(f"{source_name} failed after {max_retries} retries") from last_exc

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        value_str = str(value).strip()
        if not value_str:
            return None

        candidates = [
            ("%Y%m%d", 8),
            ("%Y-%m-%d", 10),
            ("%Y-%m-%d %H:%M:%S", 19),
            ("%Y-%m-%d %H:%M", 16),
            ("%Y%m%d %H:%M:%S", 17),
            ("%Y%m%d%H%M%S", 14),
        ]

        for fmt, length in candidates:
            try:
                return datetime.strptime(value_str[:length], fmt)
            except Exception:
                continue

        try:
            return datetime.fromisoformat(value_str.replace("Z", "+00:00"))
        except Exception:
            return None

    async def get_news_by_stock(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsItem]:
        """获取指定股票的相关新闻和公告。"""
        cache_key = f"stock:{stock_code}:{days}:{limit}"
        cached = self._get_cache(cache_key)
        if cached:
            logger.debug(f"Cache hit for stock news: {stock_code}")
            self._set_fetch_meta([])
            return [NewsItem(**item) for item in cached]

        failed_sources: List[str] = []
        news_items: List[NewsItem] = []
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        try:
            anns_news = await self._fetch_tushare_anns_d(
                ts_code=stock_code,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            news_items.extend(anns_news)
        except Exception as exc:
            logger.warning(f"fetch anns_d stock news failed: {exc}")
            failed_sources.append("tushare_anns")

        if self._use_sina_fallback:
            try:
                sina_news = await self._get_sina_stock_news(stock_code, max(limit // 2, 5))
                news_items.extend(sina_news)
            except Exception as exc:
                logger.warning(f"fetch sina stock news failed: {exc}")
                failed_sources.append("sina")

        news_items.sort(key=lambda x: x.publish_time or datetime.min, reverse=True)
        news_items = news_items[:limit]

        self._schedule_sentiment_analysis(news_items, stock_context=f"股票代码: {stock_code}")
        self._set_cache(cache_key, [item.model_dump() for item in news_items], NEWS_CACHE_TTL_ANNOUNCEMENT)
        self._set_fetch_meta(failed_sources)
        return news_items
    
    async def get_market_news(
        self,
        category: NewsCategory = NewsCategory.ALL,
        limit: int = 20,
        force_refresh: bool = False,
    ) -> List[NewsItem]:
        """获取市场整体财经新闻。"""
        category_str = category.value if isinstance(category, NewsCategory) else str(category)

        if not force_refresh:
            try:
                storage = get_news_storage()
                cached_news = storage.get_latest_news(
                    limit=max(limit * 3, 30),
                    category=category_str if category_str != "all" else None,
                )
                if cached_news:
                    news_items = [NewsItem(**item) for item in cached_news][:limit]
                    self._set_fetch_meta([])
                    self._schedule_sentiment_analysis(news_items)
                    return news_items
            except Exception as e:
                logger.warning(f"Failed to read from file storage: {e}")

        cache_key = f"market:{category}:{limit}"
        if not force_refresh:
            cached = self._get_cache(cache_key)
            if cached:
                news_items = [NewsItem(**item) for item in cached]
                self._set_fetch_meta([])
                self._schedule_sentiment_analysis(news_items)
                return news_items

        failed_sources: List[str] = []
        news_items: List[NewsItem] = []

        async def _safe_fetch(name: str, coro):
            try:
                return await coro
            except Exception as exc:
                logger.warning(f"{name} fetch failed: {exc}")
                failed_sources.append(name)
                return []

        now = datetime.now()
        start_dt = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        end_dt = now.strftime("%Y-%m-%d %H:%M:%S")

        if category == NewsCategory.ALL:
            start_date = (now - timedelta(days=2)).strftime("%Y%m%d")
            end_date = now.strftime("%Y%m%d")
            task_results = await asyncio.gather(
                _safe_fetch("tushare_news", self._fetch_tushare_news(start_dt, end_dt, limit=limit)),
                _safe_fetch("tushare_major", self._fetch_tushare_major_news(start_dt, end_dt, limit=max(limit // 2, 10))),
                _safe_fetch("tushare_anns", self._fetch_tushare_anns_d(start_date=start_date, end_date=end_date, limit=max(limit, 20))),
                _safe_fetch("tushare_cctv", self._fetch_tushare_cctv_news(now.strftime("%Y%m%d"))),
                _safe_fetch("tushare_research", self._fetch_tushare_research_report(trade_date=now.strftime("%Y%m%d"), limit=max(limit, 20))),
                _safe_fetch("tushare_npr", self._fetch_tushare_npr(start_date=start_dt, end_date=end_dt, limit=max(limit // 2, 10))),
            )
            for group in task_results:
                news_items.extend(group)
            if self._use_sina_fallback and not any(item.source == "tushare_news" for item in news_items):
                news_items.extend(await _safe_fetch("sina", self._get_sina_finance_news(limit)))
        else:
            if category == NewsCategory.FLASH:
                flash_news = await _safe_fetch("tushare_news", self._fetch_tushare_news(start_dt, end_dt, limit=limit))
                news_items.extend(flash_news)
                if self._use_sina_fallback and not flash_news:
                    news_items.extend(await _safe_fetch("sina", self._get_sina_finance_news(limit)))

            if category == NewsCategory.ANALYSIS:
                news_items.extend(await _safe_fetch("tushare_major", self._fetch_tushare_major_news(start_dt, end_dt, limit=max(limit, 20))))

            if category == NewsCategory.ANNOUNCEMENT:
                start_date = (now - timedelta(days=2)).strftime("%Y%m%d")
                end_date = now.strftime("%Y%m%d")
                news_items.extend(await _safe_fetch("tushare_anns", self._fetch_tushare_anns_d(start_date=start_date, end_date=end_date, limit=max(limit, 20))))

            if category == NewsCategory.CCTV:
                news_items.extend(await _safe_fetch("tushare_cctv", self._fetch_tushare_cctv_news(now.strftime("%Y%m%d"))))

            if category == NewsCategory.RESEARCH:
                news_items.extend(await _safe_fetch("tushare_research", self._fetch_tushare_research_report(trade_date=now.strftime("%Y%m%d"), limit=max(limit, 20))))

            if category in [NewsCategory.NPR, NewsCategory.POLICY]:
                news_items.extend(await _safe_fetch("tushare_npr", self._fetch_tushare_npr(start_date=start_dt, end_date=end_dt, limit=max(limit, 20))))

        if category != NewsCategory.ALL:
            news_items = [item for item in news_items if item.category == category]

        deduped: Dict[str, NewsItem] = {}
        for item in news_items:
            deduped[item.id] = item

        result = sorted(deduped.values(), key=lambda x: x.publish_time or datetime.min, reverse=True)[:limit]

        if result:
            self._save_news_to_storage(result)
        self._schedule_sentiment_analysis(result)
        self._set_cache(cache_key, [item.model_dump() for item in result], NEWS_CACHE_TTL_FLASH)
        self._set_fetch_meta(failed_sources)

        return result
    
    async def get_cctv_news(self, date: str) -> List[NewsItem]:
        """获取指定日期新闻联播。"""
        failed_sources: List[str] = []
        try:
            items = await self._fetch_tushare_cctv_news(date=date)
            self._set_fetch_meta([])
            return items
        except Exception as exc:
            logger.warning(f"get_cctv_news failed: {exc}")
            failed_sources.append("tushare_cctv")
            self._set_fetch_meta(failed_sources)
            return []

    async def get_policy_news(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        org: Optional[str] = None,
        ptype: Optional[str] = None,
        limit: int = 50,
    ) -> List[NewsItem]:
        """获取政策法规新闻。"""
        failed_sources: List[str] = []
        try:
            items = await self._fetch_tushare_npr(
                start_date=start_date,
                end_date=end_date,
                org=org,
                ptype=ptype,
                limit=limit,
            )
            self._set_fetch_meta([])
            return items
        except Exception as exc:
            logger.warning(f"get_policy_news failed: {exc}")
            failed_sources.append("tushare_npr")
            self._set_fetch_meta(failed_sources)
            return []

    async def get_research_reports(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ts_code: Optional[str] = None,
        report_type: Optional[str] = None,
        inst_csname: Optional[str] = None,
        ind_name: Optional[str] = None,
        limit: int = 100,
    ) -> List[NewsItem]:
        """获取券商研报。"""
        failed_sources: List[str] = []
        try:
            items = await self._fetch_tushare_research_report(
                start_date=start_date,
                end_date=end_date,
                ts_code=ts_code,
                report_type=report_type,
                inst_csname=inst_csname,
                ind_name=ind_name,
                limit=limit,
            )
            self._set_fetch_meta([])
            return items
        except Exception as exc:
            logger.warning(f"get_research_reports failed: {exc}")
            failed_sources.append("tushare_research")
            self._set_fetch_meta(failed_sources)
            return []

    def _save_news_to_storage(self, news_items: List[NewsItem]):
        """将新闻保存到本地文件存储"""
        try:
            storage = get_news_storage()
            grouped: Dict[str, List[Dict[str, Any]]] = {}

            for item in news_items:
                item_dict = item.model_dump()
                source_key = (item.source or "unknown").replace("/", "_")
                grouped.setdefault(source_key, []).append(item_dict)

            for source_key, source_items in grouped.items():
                saved = storage.save_news(source_items, source_key)
                logger.info(f"Saved {saved} {source_key} news to file storage")

        except Exception as e:
            logger.warning(f"Failed to save news to storage: {e}")

    def _schedule_sentiment_analysis(
        self,
        news_items: List[NewsItem],
        stock_context: Optional[str] = None,
    ) -> None:
        """后台异步分析情绪（不阻塞请求）"""
        missing = [item for item in news_items if item.sentiment is None]
        if not missing:
            return
        try:
            asyncio.create_task(self._background_analyze_sentiment(missing, stock_context))
        except Exception as e:
            logger.warning(f"Failed to schedule sentiment analysis: {e}")

    async def _background_analyze_sentiment(
        self,
        news_items: List[NewsItem],
        stock_context: Optional[str] = None,
    ) -> None:
        """后台执行情绪分析并持久化结果"""
        try:
            sentiments = await self.analyze_news_sentiment(news_items, stock_context)
            self._apply_sentiments_to_news(news_items, sentiments)
            self._save_news_to_storage(news_items)
        except Exception as e:
            logger.warning(f"Background sentiment analysis failed: {e}")

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
    
    async def _fetch_tushare_news(
        self,
        start_date: str,
        end_date: str,
        src: Optional[str] = None,
        limit: int = 100,
    ) -> List[NewsItem]:
        """获取 Tushare 新闻快讯。"""
        items: List[NewsItem] = []
        src_list = [src] if src else NEWS_SRC_LIST

        for one_src in src_list:
            df = await self._run_tushare_with_retry(
                f"tushare_news:{one_src}",
                "news",
                src=one_src,
                start_date=start_date,
                end_date=end_date,
                fields="datetime,content,title,channels",
            )
            if df is None or df.empty:
                continue

            for _, row in df.head(limit).iterrows():
                pub_time = self._parse_datetime(row.get("datetime"))
                title = str(row.get("title") or "")
                content = str(row.get("content") or "")[:1200]
                item = NewsItem(
                    id=_generate_news_id(f"tushare_news:{one_src}", title, pub_time),
                    title=title,
                    content=content,
                    source="tushare_news",
                    news_src=one_src,
                    publish_time=pub_time,
                    category=NewsCategory.FLASH,
                )
                items.append(item)

        return items

    async def _fetch_tushare_major_news(
        self,
        start_date: str,
        end_date: str,
        src: Optional[str] = None,
        limit: int = 100,
    ) -> List[NewsItem]:
        """获取 Tushare 新闻通讯。"""
        items: List[NewsItem] = []
        src_list = [src] if src else MAJOR_NEWS_SRC_LIST

        for one_src in src_list:
            df = await self._run_tushare_with_retry(
                f"tushare_major:{one_src}",
                "major_news",
                src=one_src,
                start_date=start_date,
                end_date=end_date,
                fields="title,content,pub_time,src",
            )
            if df is None or df.empty:
                continue

            for _, row in df.head(limit).iterrows():
                pub_time = self._parse_datetime(row.get("pub_time"))
                title = str(row.get("title") or "")
                content = str(row.get("content") or "")[:3000]
                src_name = str(row.get("src") or one_src)
                items.append(NewsItem(
                    id=_generate_news_id(f"tushare_major:{src_name}", title, pub_time),
                    title=title,
                    content=content,
                    source="tushare_major",
                    news_src=src_name,
                    publish_time=pub_time,
                    category=NewsCategory.ANALYSIS,
                ))

        return items

    async def _fetch_tushare_cctv_news(self, date: str) -> List[NewsItem]:
        """获取新闻联播文字稿。"""
        df = await self._run_tushare_with_retry(
            "tushare_cctv",
            "cctv_news",
            date=date,
            fields="date,title,content",
        )
        if df is None or df.empty:
            return []

        items: List[NewsItem] = []
        for _, row in df.iterrows():
            pub_time = self._parse_datetime(row.get("date"))
            title = str(row.get("title") or "")
            content = str(row.get("content") or "")
            items.append(NewsItem(
                id=_generate_news_id("tushare_cctv", title, pub_time),
                title=title,
                content=content,
                source="tushare_cctv",
                news_src="cctv_news",
                publish_time=pub_time,
                category=NewsCategory.CCTV,
            ))
        return items

    async def _fetch_tushare_anns_d(
        self,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ann_date: Optional[str] = None,
        limit: int = 200,
    ) -> List[NewsItem]:
        """获取上市公司公告。"""
        kwargs: Dict[str, Any] = {
            "fields": "ann_date,ts_code,name,title,url,rec_time"
        }
        if ts_code:
            kwargs["ts_code"] = ts_code
        if ann_date:
            kwargs["ann_date"] = ann_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date

        df = await self._run_tushare_with_retry("tushare_anns", "anns_d", **kwargs)
        if df is None or df.empty:
            return []

        items: List[NewsItem] = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("title") or "")
            code = str(row.get("ts_code") or "")
            pub_time = self._parse_datetime(row.get("rec_time") or row.get("ann_date"))
            name = str(row.get("name") or "")
            items.append(NewsItem(
                id=_generate_news_id("tushare_anns", title, pub_time),
                title=title,
                content=name,
                source="tushare_anns",
                news_src="anns_d",
                publish_time=pub_time,
                stock_codes=[code] if code else [],
                category=NewsCategory.ANNOUNCEMENT,
                url=str(row.get("url") or "") or None,
            ))
        return items

    async def _fetch_tushare_research_report(
        self,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        report_type: Optional[str] = None,
        ts_code: Optional[str] = None,
        inst_csname: Optional[str] = None,
        ind_name: Optional[str] = None,
        limit: int = 200,
    ) -> List[NewsItem]:
        """获取券商研报。"""
        kwargs: Dict[str, Any] = {
            "fields": "trade_date,abstr,title,report_type,author,name,ts_code,inst_csname,ind_name,url"
        }
        if trade_date:
            kwargs["trade_date"] = trade_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        if report_type:
            kwargs["report_type"] = report_type
        if ts_code:
            kwargs["ts_code"] = ts_code
        if inst_csname:
            kwargs["inst_csname"] = inst_csname
        if ind_name:
            kwargs["ind_name"] = ind_name

        df = await self._run_tushare_with_retry("tushare_research", "research_report", **kwargs)
        if df is None or df.empty:
            return []

        items: List[NewsItem] = []
        for _, row in df.head(limit).iterrows():
            pub_time = self._parse_datetime(row.get("trade_date"))
            title = str(row.get("title") or "")
            abstr = str(row.get("abstr") or "")
            ts_code_val = str(row.get("ts_code") or "")
            author = str(row.get("author") or "")
            inst_name = str(row.get("inst_csname") or "")
            ind_name_val = str(row.get("ind_name") or "")
            report_kind = str(row.get("report_type") or "")
            content_parts = [p for p in [abstr, f"机构: {inst_name}" if inst_name else "", f"行业: {ind_name_val}" if ind_name_val else ""] if p]
            items.append(NewsItem(
                id=_generate_news_id("tushare_research", title, pub_time),
                title=title,
                content="\n".join(content_parts),
                source="tushare_research",
                news_src="research_report",
                author=author or None,
                abstract=abstr or None,
                publish_time=pub_time,
                stock_codes=[ts_code_val] if ts_code_val else [],
                category=NewsCategory.RESEARCH,
                url=str(row.get("url") or "") or None,
                sentiment_reasoning=report_kind or None,
            ))
        return items

    async def _fetch_tushare_npr(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        org: Optional[str] = None,
        ptype: Optional[str] = None,
        limit: int = 200,
    ) -> List[NewsItem]:
        """获取国家政策法规。"""
        kwargs: Dict[str, Any] = {
            "fields": "pubtime,title,url,content_html,pcode,puborg,ptype"
        }
        if org:
            kwargs["org"] = org
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        if ptype:
            kwargs["ptype"] = ptype

        df = await self._run_tushare_with_retry("tushare_npr", "npr", **kwargs)
        if df is None or df.empty:
            return []

        items: List[NewsItem] = []
        for _, row in df.head(limit).iterrows():
            pub_time = self._parse_datetime(row.get("pubtime"))
            title = str(row.get("title") or "")
            content_html = str(row.get("content_html") or "")
            puborg = str(row.get("puborg") or "")
            ptype_val = str(row.get("ptype") or "")
            pcode = str(row.get("pcode") or "")
            content = content_html[:2000]
            if puborg:
                content = f"[{puborg}] {content}"
            items.append(NewsItem(
                id=_generate_news_id("tushare_npr", title, pub_time),
                title=title,
                content=content,
                source="tushare_npr",
                news_src=ptype_val or "npr",
                abstract=pcode or None,
                publish_time=pub_time,
                category=NewsCategory.NPR,
                url=str(row.get("url") or "") or None,
            ))
        return items

    async def _get_tushare_announcements(
        self,
        stock_code: str,
        days: int = 7,
        limit: int = 20,
    ) -> List[NewsItem]:
        """兼容旧方法，内部转 anns_d。"""
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        return await self._fetch_tushare_anns_d(
            ts_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    
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