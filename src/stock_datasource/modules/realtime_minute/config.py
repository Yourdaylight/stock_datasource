"""Dynamic configuration for realtime minute data collection.

Code lists are loaded from ClickHouse on startup and can be refreshed
via the /api/realtime/refresh-codes endpoint.
"""

import logging
import threading

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Market code lists — dynamically loaded from ClickHouse, with static fallbacks
# ---------------------------------------------------------------------------

# Major indices – rarely change
INDEX_CODES: list[str] = [
    "000001.SH",  # 上证指数
    "399001.SZ",  # 深证成指
    "399006.SZ",  # 创业板指
    "000016.SH",  # 上证50
    "000300.SH",  # 沪深300
    "000905.SH",  # 中证500
    "000852.SH",  # 中证1000
    "000688.SH",  # 科创50
]

# A-stock & ETF codes — populated from DB by refresh_codes_from_db()
# A+ETF 共享同一个采集通道（rt_min），合并管理
ASTOCK_CODES: list[str] = []
ETF_CODES: list[str] = []

# Thread lock for code list updates
_codes_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Batch & concurrency configuration
# ---------------------------------------------------------------------------

# TuShare rt_min supports up to 300 codes per request (comma-separated)
BATCH_SIZE = 300

# Number of concurrent coroutines for API calls
CONCURRENT_WORKERS = 50

# TuShare rate limit: 500 calls/min → 120ms per call minimum
# With 50 concurrency and batch=300, total batches ≈ 24, fits in 1 minute easily
RATE_LIMIT_PER_MINUTE = 500
MIN_CALL_INTERVAL = 60.0 / RATE_LIMIT_PER_MINUTE  # ~0.12s

# ---------------------------------------------------------------------------
# Collection configuration
# ---------------------------------------------------------------------------

# Default collection frequency per market (minutes)
COLLECT_FREQ: dict[str, int] = {
    "a_etf": 1,
    "index": 1,
}

# Tushare API frequency for minute bars (MUST be uppercase: 1MIN,5MIN,15MIN,30MIN,60MIN)
DEFAULT_BAR_FREQ = "1MIN"

# Retry
MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# SQLite 缓存配置（替代 Redis）
# ---------------------------------------------------------------------------

# SQLite 数据库文件路径（可通过环境变量 RT_MINUTE_SQLITE_PATH 覆盖）
import os as _os

SQLITE_DB_PATH = _os.environ.get(
    "RT_MINUTE_SQLITE_PATH",
    _os.path.join(_os.path.dirname(__file__), "rt_minute_cache.db"),
)

# 保留此常量名以兼容 cache_store.py 的 store_bars 接口签名（SQLite 版本不使用 TTL）
REDIS_DEFAULT_TTL = 18 * 3600  # 仅作接口兼容占位，SQLite 版本不使用

# ---------------------------------------------------------------------------
# Sync configuration
# ---------------------------------------------------------------------------

SYNC_TIME = "15:30"  # Default sync time after market close
CLEANUP_TIME = "03:00"  # Default cleanup time

# ClickHouse target tables (per market)
CLICKHOUSE_TABLES: dict[str, str] = {
    "a_stock": "ods_min_kline_cn",
    "etf": "ods_min_kline_etf",
    "index": "ods_min_kline_index",
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

# ---------------------------------------------------------------------------
# Dynamic code list management
# ---------------------------------------------------------------------------


def refresh_codes_from_db() -> dict[str, int]:
    """Load A-stock and ETF code lists from ClickHouse.

    Returns dict with counts per market.
    """
    global ASTOCK_CODES, ETF_CODES
    try:
        from stock_datasource.config.settings import settings
        from stock_datasource.models.database import db_client

        database = settings.CLICKHOUSE_DATABASE

        # A-stock codes
        astock_df = db_client.execute_query(
            f"SELECT ts_code FROM {database}.ods_stock_basic "
            f"WHERE ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ' OR ts_code LIKE '%.BJ' "
            f"ORDER BY ts_code"
        )
        new_astock = astock_df["ts_code"].tolist() if not astock_df.empty else []

        # ETF codes
        etf_df = db_client.execute_query(
            f"SELECT ts_code FROM {database}.ods_etf_basic "
            f"WHERE ts_code LIKE '%.SH' OR ts_code LIKE '%.SZ' "
            f"ORDER BY ts_code"
        )
        new_etf = etf_df["ts_code"].tolist() if not etf_df.empty else []

        with _codes_lock:
            ASTOCK_CODES = new_astock
            ETF_CODES = new_etf

        counts = {
            "a_stock": len(ASTOCK_CODES),
            "etf": len(ETF_CODES),
            "a_etf_total": len(ASTOCK_CODES) + len(ETF_CODES),
            "index": len(INDEX_CODES),
        }
        logger.info("Refreshed codes from DB: %s", counts)
        return counts

    except Exception as e:
        logger.error("Failed to refresh codes from DB: %s", e)
        return {
            "a_stock": len(ASTOCK_CODES),
            "etf": len(ETF_CODES),
            "a_etf_total": len(ASTOCK_CODES) + len(ETF_CODES),
            "index": len(INDEX_CODES),
        }


def get_all_astock_codes() -> list[str]:
    """Return current A-stock code list (thread-safe)."""
    with _codes_lock:
        return list(ASTOCK_CODES)


def get_all_etf_codes() -> list[str]:
    """Return current ETF code list (thread-safe)."""
    with _codes_lock:
        return list(ETF_CODES)


def get_all_a_etf_codes() -> list[str]:
    """Return merged A-stock + ETF code list for batch collection (thread-safe)."""
    with _codes_lock:
        return list(ASTOCK_CODES) + list(ETF_CODES)
