"""News file storage implementation.

轻量级 JSON 文件存储方案，用于持久化新闻数据。
支持按日期分片、自动缓存聚合、定时清理等功能。
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


class NewsFileStorage:
    """轻量级 JSON 文件存储
    
    文件结构：
    data/news/
    ├── sina/
    │   ├── 2024-01-28.json     # 按日期分文件
    │   └── ...
    ├── tushare/
    │   └── ...
    └── cache/
        └── latest.json          # 最新缓存（快速读取）
    """
    
    _instance: Optional['NewsFileStorage'] = None
    _lock = Lock()
    
    def __new__(cls, base_dir: Optional[str] = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, base_dir: Optional[str] = None):
        """初始化存储
        
        Args:
            base_dir: 基础目录，默认为项目根目录下的 data/news
        """
        if self._initialized:
            return
            
        if base_dir is None:
            # 默认使用项目根目录下的 data/news
            project_root = Path(__file__).parent.parent.parent.parent.parent
            base_dir = str(project_root / "data" / "news")
        
        self.base_dir = Path(base_dir)
        self.cache_dir = self.base_dir / "cache"
        self.cache_file = self.cache_dir / "latest.json"
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓存（避免频繁读取文件）
        self._memory_cache: Optional[Dict[str, Any]] = None
        self._memory_cache_time: Optional[datetime] = None
        self._memory_cache_ttl = 60  # 内存缓存有效期（秒）
        
        self._initialized = True
        logger.info(f"NewsFileStorage initialized at: {self.base_dir}")
    
    def save_news(self, news_list: List[Dict[str, Any]], source: str) -> int:
        """保存新闻到按日期分片的文件
        
        Args:
            news_list: 新闻列表（字典格式）
            source: 新闻来源 (sina/tushare)
            
        Returns:
            新增条目数
        """
        if not news_list:
            return 0
        
        today = datetime.now().strftime("%Y-%m-%d")
        source_dir = self.base_dir / source
        source_dir.mkdir(parents=True, exist_ok=True)
        file_path = source_dir / f"{today}.json"
        
        # 加载已有数据
        existing = self._load_json(file_path) or []
        existing_ids = {n.get("id") for n in existing if n.get("id")}
        
        # 去重合并
        new_items = []
        for item in news_list:
            news_id = item.get("id")
            if news_id and news_id not in existing_ids:
                # 确保数据格式正确
                item = self._normalize_news_item(item)
                new_items.append(item)
                existing_ids.add(news_id)
        
        if new_items:
            merged = existing + new_items
            self._save_json(file_path, merged)
            logger.info(f"Saved {len(new_items)} new {source} news to {file_path}")
            
            # 更新缓存
            self._update_cache()
            
            # 清除内存缓存
            self._memory_cache = None
        
        return len(new_items)
    
    def get_latest_news(
        self,
        limit: int = 50,
        source: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """从缓存快速获取最新新闻
        
        Args:
            limit: 返回数量
            source: 按来源筛选（可选）
            category: 按分类筛选（可选）
            
        Returns:
            新闻列表
        """
        # 检查内存缓存
        if self._is_memory_cache_valid():
            cache = self._memory_cache
        else:
            cache = self._load_json(self.cache_file)
            if cache:
                self._memory_cache = cache
                self._memory_cache_time = datetime.now()
        
        if not cache:
            return []
        
        # 合并所有新闻
        all_news = []
        for key, items in cache.items():
            if key.endswith("_news") and isinstance(items, list):
                all_news.extend(items)
        
        # 按来源筛选
        if source and source != "all":
            all_news = [n for n in all_news if n.get("source") == source]
        
        # 按分类筛选
        if category and category != "all":
            all_news = [n for n in all_news if n.get("category") == category]
        
        # 按时间排序
        all_news.sort(
            key=lambda x: x.get("publish_time") or "",
            reverse=True
        )
        
        return all_news[:limit]
    
    def get_news_count(self) -> int:
        """获取缓存的新闻总数"""
        cache = self._load_json(self.cache_file)
        if not cache:
            return 0
        
        count = 0
        for key, items in cache.items():
            if key.endswith("_news") and isinstance(items, list):
                count += len(items)
        return count
    
    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        cache = self._load_json(self.cache_file)
        if not cache:
            return {
                "exists": False,
                "updated_at": None,
                "news_count": 0,
            }
        
        news_count = 0
        sources = {}
        for key, items in cache.items():
            if key.endswith("_news") and isinstance(items, list):
                source_name = key.replace("_news", "")
                sources[source_name] = len(items)
                news_count += len(items)
        
        return {
            "exists": True,
            "updated_at": cache.get("updated_at"),
            "news_count": news_count,
            "sources": sources,
            "cache_file": str(self.cache_file),
        }

    def list_news_files(
        self,
        days: Optional[int] = None,
        sources: Optional[List[str]] = None,
    ) -> List[Path]:
        """列出新闻数据文件
        
        Args:
            days: 仅返回最近 N 天的文件（可选）
            sources: 指定来源列表（可选）
        
        Returns:
            文件路径列表
        """
        available_sources = []
        for source_dir in self.base_dir.iterdir():
            if source_dir.is_dir() and source_dir.name != "cache":
                available_sources.append(source_dir.name)
        
        target_sources = sources or available_sources
        files: List[Path] = []
        
        cutoff_date = None
        if days is not None and days > 0:
            cutoff_date = (datetime.now() - timedelta(days=days - 1)).date()
        
        for source in target_sources:
            source_dir = self.base_dir / source
            if not source_dir.exists():
                continue
            for file_path in source_dir.glob("*.json"):
                if cutoff_date:
                    try:
                        file_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
                        if file_date < cutoff_date:
                            continue
                    except ValueError:
                        pass
                files.append(file_path)
        
        return sorted(files, key=lambda p: p.name, reverse=True)

    def load_news_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """加载指定新闻文件"""
        return self._load_json(file_path) or []

    def save_news_file(self, file_path: Path, news_list: List[Dict[str, Any]]):
        """保存指定新闻文件"""
        self._save_json(file_path, news_list)
    
    def _update_cache(self, days: int = 3):
        """聚合最近 N 天的新闻到缓存文件
        
        Args:
            days: 聚合天数
        """
        cache = {
            "updated_at": datetime.now().isoformat(),
        }
        
        for source in ["sina", "tushare"]:
            source_news = self._load_recent_days(source, days)
            cache[f"{source}_news"] = source_news
        
        self._save_json(self.cache_file, cache)
        
        # 清除内存缓存
        self._memory_cache = None
        
        total = sum(len(v) for k, v in cache.items() if k.endswith("_news"))
        logger.info(f"Updated cache with {total} news items")
    
    def _load_recent_days(self, source: str, days: int = 3) -> List[Dict[str, Any]]:
        """加载最近 N 天的新闻
        
        Args:
            source: 新闻来源
            days: 天数
            
        Returns:
            新闻列表
        """
        all_news = []
        source_dir = self.base_dir / source
        
        if not source_dir.exists():
            return []
        
        # 生成日期列表
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        
        for date_str in dates:
            file_path = source_dir / f"{date_str}.json"
            if file_path.exists():
                news = self._load_json(file_path) or []
                all_news.extend(news)
        
        # 按时间排序
        all_news.sort(
            key=lambda x: x.get("publish_time") or "",
            reverse=True
        )
        
        return all_news
    
    def cleanup_old_files(self, days: int = 7):
        """清理 N 天前的文件
        
        Args:
            days: 保留天数
        """
        cutoff = datetime.now() - timedelta(days=days)
        cleaned_count = 0
        
        for source_dir in self.base_dir.iterdir():
            if source_dir.is_dir() and source_dir.name not in ["cache"]:
                for file_path in source_dir.glob("*.json"):
                    try:
                        # 从文件名解析日期
                        file_date = datetime.strptime(file_path.stem, "%Y-%m-%d")
                        if file_date < cutoff:
                            file_path.unlink()
                            cleaned_count += 1
                            logger.debug(f"Cleaned old file: {file_path}")
                    except ValueError:
                        # 文件名不是日期格式，跳过
                        pass
        
        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} old news files")
        
        return cleaned_count
    
    def force_refresh_cache(self):
        """强制刷新缓存（手动触发）"""
        self._update_cache()
        self._memory_cache = None
        logger.info("Force refreshed news cache")
    
    def _is_memory_cache_valid(self) -> bool:
        """检查内存缓存是否有效"""
        if self._memory_cache is None or self._memory_cache_time is None:
            return False
        
        elapsed = (datetime.now() - self._memory_cache_time).total_seconds()
        return elapsed < self._memory_cache_ttl
    
    def _normalize_news_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """标准化新闻数据格式"""
        # 确保 publish_time 是字符串格式
        publish_time = item.get("publish_time")
        if publish_time:
            if isinstance(publish_time, datetime):
                item["publish_time"] = publish_time.isoformat()
            elif not isinstance(publish_time, str):
                item["publish_time"] = str(publish_time)
        
        # 确保必要字段存在
        item.setdefault("id", "")
        item.setdefault("title", "")
        item.setdefault("content", "")
        item.setdefault("source", "unknown")
        item.setdefault("category", "flash")
        item.setdefault("stock_codes", [])
        item.setdefault("url", None)
        
        return item
    
    def _load_json(self, file_path: Path) -> Optional[Any]:
        """加载 JSON 文件"""
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load JSON from {file_path}: {e}")
            return None
    
    def _save_json(self, file_path: Path, data: Any):
        """保存 JSON 文件"""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save JSON to {file_path}: {e}")
            raise


# 全局实例
_storage_instance: Optional[NewsFileStorage] = None


def get_news_storage() -> NewsFileStorage:
    """获取 NewsFileStorage 单例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = NewsFileStorage()
    return _storage_instance