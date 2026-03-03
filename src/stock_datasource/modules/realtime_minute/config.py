"""Static configuration for realtime minute data collection.

Code lists are kept in-memory for fast access. Use the refresh API
(POST /api/realtime/refresh-codes) to update from database when needed.
"""

from typing import Dict, List

# ---------------------------------------------------------------------------
# Market code lists (static, updated quarterly or via API)
# ---------------------------------------------------------------------------

# Major indices – rarely change
INDEX_CODES: List[str] = [
    "000001.SH",  # 上证指数
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "000016.SH",  # 上证50
    "000300.SH",  # 沪深300
    "000905.SH",  # 中证500
    "000852.SH",  # 中证1000
    "000688.SH",  # 科创50
]

# Hot ETFs – update quarterly
HOT_ETF_CODES: List[str] = [
    "510050.SH",  # 上证50ETF
    "510300.SH",  # 沪深300ETF
    "510500.SH",  # 中证500ETF
    "159915.SZ",  # 创业板ETF
    "159919.SZ",  # 沪深300ETF
    "588000.SH",  # 科创50ETF
    "512010.SH",  # 医药ETF
    "512880.SH",  # 证券ETF
    "515790.SH",  # 光伏ETF
    "512660.SH",  # 军工ETF
    "159869.SZ",  # 新能源车ETF
    "516160.SH",  # 新能源ETF
    "512690.SH",  # 酒ETF
    "512200.SH",  # 房地产ETF
    "159941.SZ",  # 纳指ETF
    "513100.SH",  # 纳指100ETF
    "159920.SZ",  # 恒生ETF
    "513060.SH",  # 恒生医疗ETF
    "513180.SH",  # 恒生科技ETF
    "518880.SH",  # 黄金ETF
]

# A-stock batches – representative stocks, expand via refresh-codes API
# Keeping a manageable default; the real list can be loaded from DB.
ASTOCK_BATCHES: List[List[str]] = [
    # Batch 1 – Large caps
    [
        "600519.SH",  # 贵州茅台
        "601318.SH",  # 中国平安
        "600036.SH",  # 招商银行
        "601166.SH",  # 兴业银行
        "600276.SH",  # 恒瑞医药
        "000858.SZ",  # 五粮液
        "000333.SZ",  # 美的集团
        "002714.SZ",  # 牧原股份
        "300750.SZ",  # 宁德时代
        "601012.SH",  # 隆基绿能
    ],
]

# Hong Kong stocks – optional
HK_CODES: List[str] = [
    "00700.HK",  # 腾讯控股
    "09988.HK",  # 阿里巴巴
    "03690.HK",  # 美团
    "09999.HK",  # 网易
    "01024.HK",  # 快手
    "09888.HK",  # 百度
]

# ---------------------------------------------------------------------------
# Collection configuration
# ---------------------------------------------------------------------------

# Default collection frequency per market (minutes)
COLLECT_FREQ: Dict[str, int] = {
    "a_stock": 1,
    "etf": 1,
    "index": 1,
    "hk": 5,
}

# Tushare API frequency for minute bars
DEFAULT_BAR_FREQ = "1min"

# Rate limiting – max Tushare API calls per minute
RATE_LIMIT_PER_MINUTE = 120
MIN_CALL_INTERVAL = 60.0 / RATE_LIMIT_PER_MINUTE  # ~0.5s

# Retry
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Redis key configuration
# ---------------------------------------------------------------------------

REDIS_KEY_PREFIX_ZSET = "stock:rt_min:zset"
REDIS_KEY_PREFIX_LATEST = "stock:rt_min:latest"
REDIS_KEY_STATUS = "stock:rt_min:status"

# TTL for realtime data: expire at 03:00 next day (set dynamically)
REDIS_DEFAULT_TTL = 18 * 3600  # 18 hours fallback

# ---------------------------------------------------------------------------
# Sync configuration
# ---------------------------------------------------------------------------

SYNC_TIME = "15:30"          # Default sync time after market close
CLEANUP_TIME = "03:00"       # Default cleanup time

# ClickHouse target tables (per market)
CLICKHOUSE_TABLES: Dict[str, str] = {
    "a_stock": "ods_min_kline_cn",
    "etf": "ods_min_kline_etf",
    "index": "ods_min_kline_index",
    "hk": "ods_min_kline_hk",
}

# Default table (fallback)
CLICKHOUSE_TABLE_DEFAULT = "ods_min_kline_cn"


def get_table_for_market(market: str) -> str:
    """Return ClickHouse table name for a given market type."""
    return CLICKHOUSE_TABLES.get(market, CLICKHOUSE_TABLE_DEFAULT)

# ---------------------------------------------------------------------------
# Trading hours (for scheduler)
# ---------------------------------------------------------------------------

# A-share trading hours (UTC+8)
CN_TRADING_HOURS = [
    ("09:25", "11:35"),  # Morning session (including pre-open)
    ("12:55", "15:05"),  # Afternoon session
]

# HK trading hours (UTC+8)
HK_TRADING_HOURS = [
    ("09:15", "12:05"),  # Morning session
    ("12:55", "16:15"),  # Afternoon session
]
