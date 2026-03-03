"""Static configuration for realtime daily K-line decoupled stream sync.

All runtime-overridable settings use RT_KLINE_* prefix via pydantic-settings.
This file holds structural constants (key patterns, table names, code lists).
"""

from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Timing defaults (overridable via settings.RT_KLINE_*)
# ---------------------------------------------------------------------------
COLLECT_INTERVAL_DEFAULT = 1.5       # seconds
BACKOFF_LEVELS: List[float] = [1.5, 3.0, 5.0]
BACKOFF_FAIL_THRESHOLD = 3           # consecutive failures to trigger next level
BACKOFF_RECOVER_THRESHOLD = 5        # consecutive successes to recover one level

PUSH_INTERVAL_DEFAULT = 2.0          # seconds
PUSH_WINDOW_DEFAULT = 10.0           # sliding window seconds
SINK_INTERVAL_DEFAULT = 60           # seconds

# ---------------------------------------------------------------------------
# Redis key layout  — design.md §Redis Layout
# ---------------------------------------------------------------------------
REDIS_KEY_PREFIX_LATEST = "stock:rtk:latest"         # String per symbol
REDIS_KEY_PREFIX_STREAM = "stock:rtk:stream"          # Stream per market
REDIS_KEY_SWITCH_PUSH = "stock:rtk:switch:cloud_push"  # runtime push switch
REDIS_KEY_CKPT_CH = "stock:rtk:ckpt:clickhouse"       # checkpoint per market
REDIS_KEY_CKPT_PUSH = "stock:rtk:ckpt:push"           # push checkpoint per market
REDIS_KEY_LAST_ACKED = "stock:rtk:last_acked_state"    # Hash per market
REDIS_KEY_CIRCUIT_BREAKER = "stock:rtk:push_circuit_breaker"
REDIS_KEY_DLQ_PUSH = "stock:rtk:deadletter:push"       # List per market
REDIS_KEY_DLQ_SINK = "stock:rtk:deadletter:sink"       # List per market
REDIS_KEY_AUDIT_SWITCH = "stock:rtk:audit:push_switch"  # Stream
REDIS_KEY_STATUS = "stock:rtk:status"

# TTLs
CACHE_LATEST_TTL = 24 * 3600        # 24h
STREAM_TTL_HOURS_DEFAULT = 72        # 72h
STREAM_MAXLEN_PER_MARKET = 500_000   # cap per-market stream length

# ---------------------------------------------------------------------------
# ClickHouse table names — design.md §Final Table Naming
# ---------------------------------------------------------------------------
CLICKHOUSE_TABLES: Dict[str, str] = {
    "a_stock": "ods_rt_kline_tick_cn",
    "etf": "ods_rt_kline_tick_etf",
    "index": "ods_rt_kline_tick_index",
    "hk": "ods_rt_kline_tick_hk",
}


def get_table_for_market(market: str) -> str:
    return CLICKHOUSE_TABLES.get(market, CLICKHOUSE_TABLES["a_stock"])


# ---------------------------------------------------------------------------
# Tushare API → market mapping
# ---------------------------------------------------------------------------
MARKET_API_MAP: Dict[str, str] = {
    "a_stock": "rt_k",
    "etf": "rt_etf_k",
    "index": "rt_idx_k",
    "hk": "rt_hk_k",
}

# ---------------------------------------------------------------------------
# Trading hours
# ---------------------------------------------------------------------------
# A股/ETF/指数实时采集时间窗
CN_TRADING_HOURS: List[Tuple[str, str]] = [
    ("09:25", "11:35"),
    ("12:55", "15:05"),
]
HK_TRADING_HOURS: List[Tuple[str, str]] = [
    ("09:15", "12:05"),
    ("12:55", "16:15"),
]

# ---------------------------------------------------------------------------
# Symbol patterns (full-market shards)
# ---------------------------------------------------------------------------
ASTOCK_PATTERNS: List[str] = [
    "6*.SH", "68*.SH", "0*.SZ", "3*.SZ", "*.BJ",
]

# 深市 ETF 一般无需 topic；沪市 ETF 建议显式 topic=HQ_FND_TICK
ETF_QUERY_PATTERNS: List[Dict[str, str]] = [
    {"ts_code": "1*.SZ"},
    {"ts_code": "5*.SH", "topic": "HQ_FND_TICK"},
]

# 指数按交易所分片，携带字段白名单减少传输体积
INDEX_QUERY_PATTERNS: List[Dict[str, str]] = [
    {"ts_code": "0*.SH", "fields": "ts_code,name,trade_time,close,vol,pct_chg"},
    {"ts_code": "399*.SZ", "fields": "ts_code,name,trade_time,close,vol,pct_chg"},
]

# 兼容已有 market 检测逻辑
INDEX_CODES: List[str] = [
    "000001.SH", "399001.SZ", "399006.SZ", "000016.SH",
    "000300.SH", "000905.SH", "000852.SH", "000688.SH",
]

# 港股分片（避免单次全量压力）
HK_PATTERNS: List[str] = [
    "01*.HK", "02*.HK", "03*.HK", "06*.HK", "09*.HK",
]
# 每轮仅采部分港股分片，按轮转策略降低rt_hk_k频控触发概率
HK_PATTERNS_PER_ROUND = 1

# Canonical snapshot core fields (for delta comparison)
SNAPSHOT_CORE_FIELDS = [
    "open", "high", "low", "close", "vol", "amount",
    "pre_close", "pct_chg", "trade_time",
]
