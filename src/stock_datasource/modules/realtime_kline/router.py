"""FastAPI router for Realtime Daily K-line module (decoupled architecture)."""

import logging
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from .schemas import (
    LatestKlineResponse,
    BatchLatestResponse,
    CollectStatusResponse,
    SyncStatusResponse,
    TriggerResponse,
    PushSwitchRequest,
    PushSwitchResponse,
    MetricsResponse,
)
from .service import get_realtime_kline_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------

@router.get("/latest", response_model=LatestKlineResponse, summary="查询单只证券最新日线快照")
async def get_latest(
    ts_code: str = Query(..., description="证券代码，如 000001.SZ"),
    market: Optional[str] = Query(None, description="市场类型: a_stock/etf/index/hk"),
):
    svc = get_realtime_kline_service()
    return svc.get_latest(ts_code, market)


@router.get("/batch", response_model=BatchLatestResponse, summary="批量查询日线快照")
async def get_batch_latest(
    market: Optional[str] = Query(None, description="市场过滤: a_stock/etf/index/hk"),
    limit: int = Query(100, ge=1, le=5000, description="返回条数"),
):
    svc = get_realtime_kline_service()
    return svc.get_batch_latest(market, limit)


@router.get("/daily", summary="查询指定日期的日线数据")
async def get_daily(
    market: str = Query(..., description="市场类型: a_stock/etf/index/hk"),
    trade_date: str = Query(..., description="交易日期 YYYYMMDD"),
    limit: int = Query(5000, ge=1, le=10000, description="返回条数"),
):
    svc = get_realtime_kline_service()
    rows = svc.query_daily(market, trade_date, limit)
    return {
        "market": market,
        "trade_date": trade_date,
        "count": len(rows),
        "data": rows,
    }


# ---------------------------------------------------------------
# Status & health
# ---------------------------------------------------------------

@router.get("/status", response_model=CollectStatusResponse, summary="获取采集状态")
async def get_collect_status():
    svc = get_realtime_kline_service()
    return svc.get_collect_status()


@router.get("/runtime/health", summary="运行时健康检查")
async def runtime_health():
    from .scheduler import get_runtime
    rt = get_runtime()
    return {
        "is_running": rt.is_running,
        "workers": rt.health(),
    }


# ---------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------

@router.post("/trigger", response_model=TriggerResponse, summary="手动触发采集")
async def trigger_collection(
    markets: Optional[str] = Query(None, description="逗号分隔的市场列表，默认全部"),
):
    try:
        from .scheduler import run_collection

        market_list = None
        if markets:
            market_list = [m.strip() for m in markets.split(",") if m.strip()]

        result = run_collection(markets=market_list)

        total = sum(result.values())
        return TriggerResponse(
            success=True,
            message=f"Collected {total} records",
            markets_collected=result,
        )
    except Exception as e:
        logger.error("Manual trigger failed: %s", e, exc_info=True)
        return TriggerResponse(success=False, message=str(e), markets_collected={})


@router.post("/sync", response_model=SyncStatusResponse, summary="手动触发同步到 ClickHouse")
async def trigger_sync():
    try:
        from .scheduler import run_sink_tick
        result = run_sink_tick()
        return SyncStatusResponse(
            all_ok=result.get("all_ok", False),
            markets=result.get("markets", {}),
        )
    except Exception as e:
        logger.error("Manual sync failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------
# Cloud push switch (hidden feature)
# ---------------------------------------------------------------

@router.post("/push/switch", response_model=PushSwitchResponse, summary="切换云端推送开关")
async def set_push_switch(req: PushSwitchRequest):
    try:
        from .cache import get_cache_store
        from .scheduler import get_runtime

        cache = get_cache_store()
        ok = cache.set_push_switch(req.enabled, source="api")
        if not ok:
            return PushSwitchResponse(
                success=False,
                enabled=req.enabled,
                message="Redis unavailable",
            )

        rt = get_runtime()
        if req.enabled:
            rt.start_push_if_needed()
            msg = "Cloud push enabled, worker started"
        else:
            rt.stop_push()
            msg = "Cloud push disabled, worker stopped"

        logger.info("Push switch toggled: enabled=%s (source=api)", req.enabled)
        return PushSwitchResponse(success=True, enabled=req.enabled, message=msg)
    except Exception as e:
        logger.error("Push switch failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/push/switch", response_model=PushSwitchResponse, summary="查询云端推送开关状态")
async def get_push_switch():
    from .cloud_push import _is_push_enabled
    enabled = _is_push_enabled()
    return PushSwitchResponse(success=True, enabled=enabled, message="")


# ---------------------------------------------------------------
# Observability
# ---------------------------------------------------------------

@router.get("/metrics", response_model=MetricsResponse, summary="获取运行时指标")
async def get_metrics():
    from .metrics import metrics
    snap = metrics.snapshot()
    return MetricsResponse(
        counters=snap.get("counters", {}),
        gauges=snap.get("gauges", {}),
    )


# ---------------------------------------------------------------
# Cleanup (manual)
# ---------------------------------------------------------------

@router.post("/cleanup", summary="手动触发清理（Stream/latest/push state）")
async def trigger_cleanup():
    try:
        from .scheduler import run_cleanup
        result = run_cleanup()
        return {"success": True, **result}
    except Exception as e:
        logger.error("Cleanup failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
