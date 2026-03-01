"""FastAPI router for Realtime Minute module.

All routes are registered under /realtime (the /api prefix is added
automatically by the module registration in modules/__init__.py).
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException

from .schemas import (
    MinuteDataResponse,
    BatchMinuteDataResponse,
    RankResponse,
    MarketOverviewResponse,
    MarketStatsResponse,
    CollectStatusResponse,
    TriggerResponse,
    RefreshCodesResponse,
)
from .service import get_realtime_minute_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ===================================================================
# Basic queries
# ===================================================================

@router.get("/minute", response_model=MinuteDataResponse, summary="查询实时分钟数据")
async def get_minute_data(
    ts_code: str = Query(..., description="证券代码，如 600000.SH"),
    freq: str = Query("1min", description="频率: 1min/5min/15min/30min/60min"),
    date: Optional[str] = Query(None, description="日期 YYYYMMDD，默认今天"),
    start_time: Optional[str] = Query(None, description="开始时间 HH:MM:SS"),
    end_time: Optional[str] = Query(None, description="结束时间 HH:MM:SS"),
):
    """查询单只证券的实时分钟K线数据。"""
    svc = get_realtime_minute_service()
    return svc.get_minute_data(ts_code, freq, date, start_time, end_time)


@router.get("/minute/batch", response_model=BatchMinuteDataResponse, summary="批量查询分钟数据")
async def get_batch_minute_data(
    ts_codes: str = Query(..., description="逗号分隔的证券代码列表"),
    freq: str = Query("1min", description="频率"),
    date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
):
    """批量查询多只证券的实时分钟数据。"""
    codes = [c.strip() for c in ts_codes.split(",") if c.strip()]
    if not codes:
        raise HTTPException(status_code=400, detail="ts_codes is required")
    if len(codes) > 50:
        raise HTTPException(status_code=400, detail="Too many codes, max 50")
    svc = get_realtime_minute_service()
    return svc.get_batch_minute_data(codes, freq, date)


@router.get("/minute/latest", summary="获取最新分钟数据")
async def get_latest_minute(
    ts_code: str = Query(..., description="证券代码"),
    freq: str = Query("1min", description="频率"),
):
    """获取单只证券最新一分钟的行情快照。"""
    svc = get_realtime_minute_service()
    result = svc.get_latest_minute(ts_code, freq)
    if result is None:
        return {"ts_code": ts_code, "freq": freq, "data": None}
    return {"ts_code": ts_code, "freq": freq, "data": result}


@router.get("/minute/kline", summary="获取K线格式数据")
async def get_kline_data(
    ts_code: str = Query(..., description="证券代码"),
    freq: str = Query("1min", description="频率"),
    date: Optional[str] = Query(None, description="日期 YYYYMMDD"),
):
    """返回前端 K 线图组件兼容的数据格式。"""
    svc = get_realtime_minute_service()
    return svc.get_kline_data(ts_code, freq, date)


@router.get("/status", response_model=CollectStatusResponse, summary="获取采集状态")
async def get_collect_status():
    """获取各市场数据采集状态。"""
    svc = get_realtime_minute_service()
    return svc.get_collect_status()


# ===================================================================
# Rankings
# ===================================================================

@router.get("/rank/gainers", response_model=RankResponse, summary="分钟涨幅榜")
async def get_top_gainers(
    freq: str = Query("1min", description="频率"),
    market: Optional[str] = Query(None, description="市场过滤: a_stock/etf/index/hk"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
):
    """获取最近一分钟涨幅最大的证券。"""
    svc = get_realtime_minute_service()
    resp = svc.get_top_gainers(freq, market, limit)
    resp["count"] = len(resp["data"])
    return resp


@router.get("/rank/losers", response_model=RankResponse, summary="分钟跌幅榜")
async def get_top_losers(
    freq: str = Query("1min", description="频率"),
    market: Optional[str] = Query(None, description="市场过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
):
    """获取最近一分钟跌幅最大的证券。"""
    svc = get_realtime_minute_service()
    resp = svc.get_top_losers(freq, market, limit)
    resp["count"] = len(resp["data"])
    return resp


@router.get("/rank/volume", response_model=RankResponse, summary="成交量榜")
async def get_top_volume(
    freq: str = Query("1min", description="频率"),
    market: Optional[str] = Query(None, description="市场过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
):
    """获取最近一分钟成交量最大的证券。"""
    svc = get_realtime_minute_service()
    resp = svc.get_top_volume(freq, market, limit)
    resp["count"] = len(resp["data"])
    return resp


@router.get("/rank/amount", response_model=RankResponse, summary="成交额榜")
async def get_top_amount(
    freq: str = Query("1min", description="频率"),
    market: Optional[str] = Query(None, description="市场过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
):
    """获取最近一分钟成交额最大的证券。"""
    svc = get_realtime_minute_service()
    resp = svc.get_top_amount(freq, market, limit)
    resp["count"] = len(resp["data"])
    return resp


# ===================================================================
# Market overview
# ===================================================================

@router.get("/market/overview", response_model=MarketOverviewResponse, summary="市场整体概览")
async def get_market_overview(
    freq: str = Query("1min", description="频率"),
):
    """返回市场涨跌分布、总成交量 / 额等概览信息。"""
    svc = get_realtime_minute_service()
    return svc.get_market_overview(freq)


@router.get("/market/stats", response_model=MarketStatsResponse, summary="市场统计信息")
async def get_market_stats():
    """返回涨停 / 跌停数量和各市场分布情况。"""
    svc = get_realtime_minute_service()
    return svc.get_market_stats()


# ===================================================================
# Admin / management
# ===================================================================

@router.post("/trigger", response_model=TriggerResponse, summary="手动触发采集")
async def trigger_collection(
    freq: str = Query("1min", description="频率"),
    markets: Optional[str] = Query(None, description="逗号分隔的市场列表，默认全部"),
):
    """手动触发一次数据采集。"""
    try:
        from .collector import get_collector
        from .cache_store import get_cache_store

        collector = get_collector()
        cache = get_cache_store()

        market_list = None
        if markets:
            market_list = [m.strip() for m in markets.split(",") if m.strip()]

        data = collector.collect_all(freq=freq, markets=market_list)

        markets_collected = {}
        for market_name, df in data.items():
            if df is not None and not df.empty:
                count = cache.store_bars(df)
                cache.update_status(market_name, count)
                markets_collected[market_name] = count
            else:
                markets_collected[market_name] = 0

        return TriggerResponse(
            success=True,
            message=f"Collected {sum(markets_collected.values())} bars",
            markets_collected=markets_collected,
        )
    except Exception as e:
        logger.error("Manual trigger failed: %s", e, exc_info=True)
        return TriggerResponse(
            success=False,
            message=str(e),
            markets_collected={},
        )


@router.post("/refresh-codes", response_model=RefreshCodesResponse, summary="刷新代码列表")
async def refresh_codes():
    """从数据库刷新静态代码列表（管理员操作）。

    当前版本从 ClickHouse 的 dim 表读取最新股票 / ETF 代码，
    更新到内存配置中。
    """
    from . import config as cfg_module

    counts = {}
    try:
        from stock_datasource.models.database import db_client

        # Refresh A-stock codes
        try:
            df = db_client.execute_query(
                "SELECT ts_code FROM ods_stock_basic WHERE list_status = 'L' ORDER BY ts_code LIMIT 500"
            )
            if df is not None and not df.empty:
                codes = df["ts_code"].tolist()
                batch_size = 100
                cfg_module.ASTOCK_BATCHES = [
                    codes[i:i + batch_size] for i in range(0, len(codes), batch_size)
                ]
                counts["a_stock"] = len(codes)
        except Exception as e:
            logger.warning("Failed to refresh A-stock codes: %s", e)

        # Refresh ETF codes
        try:
            df = db_client.execute_query(
                "SELECT ts_code FROM ods_etf_basic ORDER BY ts_code LIMIT 200"
            )
            if df is not None and not df.empty:
                cfg_module.HOT_ETF_CODES = df["ts_code"].tolist()
                counts["etf"] = len(cfg_module.HOT_ETF_CODES)
        except Exception as e:
            logger.warning("Failed to refresh ETF codes: %s", e)

        counts["index"] = len(cfg_module.INDEX_CODES)
        counts["hk"] = len(cfg_module.HK_CODES)

        return RefreshCodesResponse(success=True, message="Codes refreshed", counts=counts)
    except Exception as e:
        logger.error("Refresh codes failed: %s", e)
        return RefreshCodesResponse(success=False, message=str(e), counts=counts)
