"""Pydantic schemas for Realtime Daily K-line module."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MarketType(str, Enum):
    A_STOCK = "a_stock"
    ETF = "etf"
    INDEX = "index"
    HK = "hk"


class DailyKlineBar(BaseModel):
    ts_code: str = Field(..., description="证券代码")
    name: Optional[str] = Field(None, description="证券名称")
    trade_date: Optional[str] = Field(None, description="交易日期 YYYYMMDD")
    trade_time: Optional[str] = Field(None, description="交易时间")
    open: Optional[float] = Field(None, description="开盘价")
    close: Optional[float] = Field(None, description="收盘价/最新价")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    pre_close: Optional[float] = Field(None, description="昨收价")
    vol: Optional[float] = Field(None, description="成交量")
    amount: Optional[float] = Field(None, description="成交额")
    pct_chg: Optional[float] = Field(None, description="涨跌幅(%)")
    bid: Optional[float] = Field(None, description="买一价(港股)")
    ask: Optional[float] = Field(None, description="卖一价(港股)")
    market: Optional[str] = Field(None, description="市场类型")
    collected_at: Optional[str] = Field(None, description="采集时间")
    version: Optional[int] = Field(None, description="版本号(毫秒)")


class LatestKlineResponse(BaseModel):
    ts_code: str = Field(..., description="证券代码")
    market: Optional[str] = Field(None, description="市场类型")
    data: Optional[DailyKlineBar] = Field(None, description="日线快照")
    source: str = Field(default="redis", description="数据来源 redis/clickhouse")


class BatchLatestResponse(BaseModel):
    market: Optional[str] = Field(None, description="市场类型")
    count: int = Field(default=0, description="数据条数")
    data: List[DailyKlineBar] = Field(default_factory=list, description="日线快照列表")


class CollectStatusResponse(BaseModel):
    is_running: bool = Field(default=False, description="运行时是否启动")
    workers: Dict[str, bool] = Field(default_factory=dict, description="各 worker 健康状态")
    markets: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="各市场采集状态")
    last_collect_time: Optional[str] = Field(None, description="最后采集时间")
    total_cached_keys: int = Field(default=0, description="Redis latest key 数")
    push_enabled: bool = Field(default=False, description="云端推送是否开启")


class SyncStatusResponse(BaseModel):
    all_ok: bool = Field(default=False, description="全部市场同步是否成功")
    markets: Dict[str, Any] = Field(default_factory=dict, description="各市场同步结果")


class TriggerResponse(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="结果消息")
    markets_collected: Dict[str, int] = Field(default_factory=dict, description="各市场采集数量")


class PushSwitchRequest(BaseModel):
    enabled: bool = Field(..., description="是否开启云端推送")


class PushSwitchResponse(BaseModel):
    success: bool = Field(..., description="操作是否成功")
    enabled: bool = Field(..., description="当前推送状态")
    message: str = Field(default="", description="说明")


class MetricsResponse(BaseModel):
    counters: Dict[str, int] = Field(default_factory=dict)
    gauges: Dict[str, float] = Field(default_factory=dict)
