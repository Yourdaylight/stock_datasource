"""Redis cache service with Langfuse coexistence support."""

import json
import logging
from typing import Any, Optional, Callable, TypeVar, Union
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheService:
    """Redis cache service with namespace isolation and graceful degradation.
    
    Features:
    - Uses Redis DB 1 with 'stock:' prefix to isolate from Langfuse (DB 0)
    - Graceful degradation when Redis is unavailable
    - Support for both sync and async operations
    - Decorator-based caching for functions
    - TTL management and batch invalidation
    """
    
    PREFIX = "stock:"  # Namespace prefix for isolation
    
    def __init__(self):
        self._redis = None
        self._available = True
        self._connection_attempted = False
    
    def _get_redis(self):
        """Lazy connection to Redis with graceful degradation."""
        if self._redis is not None:
            return self._redis
        
        if self._connection_attempted and not self._available:
            return None
        
        self._connection_attempted = True
        
        try:
            from redis import Redis, ConnectionError as RedisConnectionError
            from stock_datasource.config.settings import settings
            
            if not settings.REDIS_ENABLED:
                logger.info("Redis caching is disabled")
                self._available = False
                return None
            
            self._redis = Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD or None,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            self._redis.ping()
            logger.info(f"Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT} DB={settings.REDIS_DB}")
            self._available = True
            return self._redis
        except ImportError:
            logger.warning("Redis package not installed, caching disabled")
            self._available = False
            return None
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}, caching disabled")
            self._available = False
            return None
    
    @property
    def available(self) -> bool:
        """Check if Redis is available."""
        self._get_redis()
        return self._available
    
    def _key(self, key: str) -> str:
        """Add namespace prefix to key."""
        if key.startswith(self.PREFIX):
            return key
        return f"{self.PREFIX}{key}"
    
    def _serialize(self, value: Any) -> str:
        """Serialize value to JSON string."""
        return json.dumps(value, ensure_ascii=False, default=str)
    
    def _deserialize(self, data: str) -> Any:
        """Deserialize JSON string to value."""
        if data is None:
            return None
        return json.loads(data)
    
    # Synchronous methods
    def get(self, key: str) -> Optional[Any]:
        """Get cached value (sync)."""
        redis = self._get_redis()
        if redis is None:
            return None
        try:
            data = redis.get(self._key(key))
            return self._deserialize(data)
        except Exception as e:
            logger.warning(f"Cache get failed for {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set cache with TTL (sync)."""
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            return bool(redis.setex(
                self._key(key),
                ttl,
                self._serialize(value)
            ))
        except Exception as e:
            logger.warning(f"Cache set failed for {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete single key (sync)."""
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            return bool(redis.delete(self._key(key)))
        except Exception as e:
            logger.warning(f"Cache delete failed for {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (sync)."""
        redis = self._get_redis()
        if redis is None:
            return 0
        try:
            keys = redis.keys(self._key(pattern))
            if keys:
                return redis.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete pattern failed for {pattern}: {e}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists (sync)."""
        redis = self._get_redis()
        if redis is None:
            return False
        try:
            return bool(redis.exists(self._key(key)))
        except Exception:
            return False
    
    def ttl(self, key: str) -> int:
        """Get TTL of key in seconds (sync)."""
        redis = self._get_redis()
        if redis is None:
            return -2
        try:
            return redis.ttl(self._key(key))
        except Exception:
            return -2
    
    # Async wrappers (for FastAPI)
    async def aget(self, key: str) -> Optional[Any]:
        """Get cached value (async)."""
        return await asyncio.get_event_loop().run_in_executor(None, self.get, key)
    
    async def aset(self, key: str, value: Any, ttl: int = 300) -> bool:
        """Set cache with TTL (async)."""
        return await asyncio.get_event_loop().run_in_executor(None, self.set, key, value, ttl)
    
    async def adelete(self, key: str) -> bool:
        """Delete single key (async)."""
        return await asyncio.get_event_loop().run_in_executor(None, self.delete, key)
    
    async def adelete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern (async)."""
        return await asyncio.get_event_loop().run_in_executor(None, self.delete_pattern, pattern)
    
    # Decorator for caching
    def cached(self, key_template: str, ttl: int = 300):
        """Decorator for caching function results.
        
        Args:
            key_template: Key template with {param} placeholders
            ttl: Time to live in seconds
            
        Example:
            @cache.cached("daily:{ts_code}:{date}", ttl=86400)
            async def get_daily_data(ts_code: str, date: str):
                ...
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                # Build cache key from kwargs
                try:
                    key = key_template.format(**kwargs)
                except KeyError:
                    # If template params missing, skip cache
                    return await func(*args, **kwargs)
                
                # Try cache first
                cached_value = await self.aget(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key}")
                    return cached_value
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result if not None
                if result is not None:
                    await self.aset(key, result, ttl)
                    logger.debug(f"Cache set: {key}")
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                # Build cache key from kwargs
                try:
                    key = key_template.format(**kwargs)
                except KeyError:
                    return func(*args, **kwargs)
                
                # Try cache first
                cached_value = self.get(key)
                if cached_value is not None:
                    logger.debug(f"Cache hit: {key}")
                    return cached_value
                
                # Execute function
                result = func(*args, **kwargs)
                
                # Cache result if not None
                if result is not None:
                    self.set(key, result, ttl)
                    logger.debug(f"Cache set: {key}")
                
                return result
            
            # Return appropriate wrapper based on function type
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        
        return decorator
    
    # Statistics and monitoring
    def get_stats(self) -> dict:
        """Get cache statistics."""
        redis = self._get_redis()
        if redis is None:
            return {
                "available": False,
                "error": "Redis not connected"
            }
        try:
            info = redis.info("stats")
            memory = redis.info("memory")
            return {
                "available": True,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "keys": redis.dbsize(),
                "used_memory": memory.get("used_memory_human", "unknown"),
                "max_memory": memory.get("maxmemory_human", "unknown"),
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round(hits / total * 100, 2)
    
    def flush_namespace(self) -> int:
        """Flush all keys with our namespace prefix."""
        return self.delete_pattern("*")
    
    def health_check(self) -> dict:
        """Health check for monitoring."""
        redis = self._get_redis()
        if redis is None:
            return {"status": "unavailable", "message": "Redis not connected"}
        try:
            redis.ping()
            return {"status": "healthy", "message": "Redis connected"}
        except Exception as e:
            return {"status": "unhealthy", "message": str(e)}


# Singleton instance
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """Get global cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


# Convenience alias
cache = get_cache_service
