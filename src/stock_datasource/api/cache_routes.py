"""Cache management API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

router = APIRouter(prefix="/api/cache", tags=["cache"])


class CacheSetRequest(BaseModel):
    """Request body for setting cache."""
    key: str
    value: Any
    ttl: int = 300


class CacheDeleteRequest(BaseModel):
    """Request body for deleting cache by pattern."""
    pattern: str


@router.get("/stats")
async def get_cache_stats():
    """Get cache statistics."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    return cache.get_stats()


@router.get("/health")
async def cache_health():
    """Cache health check."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    return cache.health_check()


@router.get("/get/{key:path}")
async def get_cache(key: str):
    """Get cached value by key."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    
    value = await cache.aget(key)
    if value is None:
        return {"found": False, "key": key, "value": None}
    return {"found": True, "key": key, "value": value, "ttl": cache.ttl(key)}


@router.post("/set")
async def set_cache(request: CacheSetRequest):
    """Set cache value."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    
    success = await cache.aset(request.key, request.value, request.ttl)
    return {"success": success, "key": request.key, "ttl": request.ttl}


@router.delete("/delete/{key:path}")
async def delete_cache(key: str):
    """Delete cache by key."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    
    success = await cache.adelete(key)
    return {"success": success, "key": key}


@router.post("/delete-pattern")
async def delete_cache_pattern(request: CacheDeleteRequest):
    """Delete cache by pattern."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    
    count = await cache.adelete_pattern(request.pattern)
    return {"deleted": count, "pattern": request.pattern}


@router.post("/flush")
async def flush_cache():
    """Flush all cache in namespace (stock:*)."""
    from stock_datasource.services.cache_service import get_cache_service
    cache = get_cache_service()
    
    count = cache.flush_namespace()
    return {"flushed": count, "message": "All stock:* keys deleted"}
