"""Demo script to run the Sentinel System scan cycle.

Adapts to the actual database schema:
- Table: ods_index_daily (not fact_index_daily)
- Table: ods_stock_basic (not dim_stock_basic)
- quant_core_pool is empty, so we use top stocks from fact_daily_bar
- CSI300 only has 54 days, so market_risk uses MA20 instead of MA250
"""

import asyncio
import json
import logging
import os
import sys

# Set environment variables before importing anything
os.environ.setdefault("CLICKHOUSE_HOST", "9.134.243.46")
os.environ.setdefault("CLICKHOUSE_PORT", "9000")
os.environ.setdefault("CLICKHOUSE_HTTP_PORT", "8123")
os.environ.setdefault("CLICKHOUSE_USER", "clickhouse")
os.environ.setdefault("CLICKHOUSE_PASSWORD", "clickhouse")
os.environ.setdefault("CLICKHOUSE_DATABASE", "stock_datasource")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
# Disable LLM for this demo (no API key configured)
os.environ.setdefault("SENTINEL_USE_LLM", "false")
# TuShare token (needed to import the package, even though we don't use it)
os.environ.setdefault("TUSHARE_TOKEN", "demo_token_not_used")

# Add project source to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Pre-create a fake tushare module to bypass import errors
import types
tushare_mock = types.ModuleType("tushare")
tushare_mock.pro = types.ModuleType("tushare.pro")
tushare_mock.pro.client = types.ModuleType("tushare.pro.client")
tushare_mock.pro.client.DataApi = type("DataApi", (), {"__init__": lambda self, *args, **kwargs: None})
sys.modules["tushare"] = tushare_mock
sys.modules["tushare.pro"] = tushare_mock.pro
sys.modules["tushare.pro.client"] = tushare_mock.pro.client
# Also mock langfuse and other optional deps
for mod_name in ["langfuse", "langfuse.decorators", "langfuse.callback",
                 "langchain", "langchain.tools", "langchain_core",
                 "langchain_core.tools", "langchain_openai",
                 "langgraph", "langgraph.graph", "langgraph.prebuilt",
                 "mcp", "mcp.client", "mcp.server"]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("clickhouse_driver").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger("sentinel_demo")


# ===========================================================================
# Monkey-patch db_client to work with actual table names
# ===========================================================================

def patch_db_client():
    """Create a minimal db_client that connects directly to ClickHouse."""
    import pandas as pd
    import io

    class MinimalClickHouseClient:
        """Minimal ClickHouse client using HTTP interface."""

        def __init__(self, host, port, user, password, database):
            self.host = host
            self.port = port
            self.user = user
            self.password = password
            self.database = database
            import requests
            self._session = requests.Session()
            self._session.trust_env = False
            self._base_url = f"http://{host}:{port}/"
            logger.info("  连接 ClickHouse: %s:%d/%s", host, port, database)

        def execute_query(self, query, params=None):
            """Execute a query and return a DataFrame."""
            # Apply table name remapping
            TABLE_REMAP = {
                "fact_index_daily": "ods_index_daily",
                "dim_stock_basic": "ods_stock_basic",
                "fact_fina_indicator": "ods_fina_indicator",
                "fact_income": "ods_income",
                "fact_balancesheet": "ods_balance_sheet",
                "fact_cashflow": "ods_cash_flow",
            }
            patched_query = query
            for expected, actual in TABLE_REMAP.items():
                patched_query = patched_query.replace(expected, actual)

            try:
                resp = self._session.get(
                    self._base_url,
                    params={
                        "database": self.database,
                        "query": patched_query + " FORMAT TabSeparatedWithNames",
                        "user": self.user,
                        "password": self.password,
                    },
                    timeout=30,
                )
                if resp.status_code != 200:
                    if "does not exist" in resp.text or "UNKNOWN_TABLE" in resp.text:
                        return pd.DataFrame()
                    raise Exception(f"ClickHouse error: {resp.text[:200]}")

                if not resp.text.strip():
                    return pd.DataFrame()

                return pd.read_csv(io.StringIO(resp.text), sep="\t")
            except Exception as e:
                if "does not exist" in str(e) or "UNKNOWN_TABLE" in str(e):
                    return pd.DataFrame()
                raise

        def insert_dataframe(self, table, df):
            """Insert a DataFrame into ClickHouse (for persistence)."""
            logger.debug("Would insert %d rows into %s (skipped in demo)", len(df), table)

    client = MinimalClickHouseClient(
        host="9.134.243.46",
        port=8123,
        user="clickhouse",
        password="clickhouse",
        database="stock_datasource",
    )
    return client

    original_execute = db_client.execute_query

    # Table name mappings (code expects → actual)
    TABLE_REMAP = {
        "fact_index_daily": "ods_index_daily",
        "dim_stock_basic": "ods_stock_basic",
        "fact_fina_indicator": "ods_fina_indicator",
        "fact_income": "ods_income",
        "fact_balancesheet": "ods_balance_sheet",
        "fact_cashflow": "ods_cash_flow",
        "ods_top_inst": "ods_top_list",
    }

    def patched_execute(query, params=None):
        # Remap table names
        patched_query = query
        for expected, actual in TABLE_REMAP.items():
            patched_query = patched_query.replace(expected, actual)
        try:
            return original_execute(patched_query, params)
        except Exception as e:
            if "does not exist" in str(e) or "UNKNOWN_TABLE" in str(e):
                import pandas as pd
                logger.debug("Table not found, returning empty DataFrame: %s", str(e)[:100])
                return pd.DataFrame()
            raise

    db_client.execute_query = patched_execute
    return db_client


# ===========================================================================
# Provide a fake pool since quant_core_pool is empty
# ===========================================================================

def seed_fake_core_pool(db_client):
    """Since quant_core_pool is empty, we create a temp list of stocks to monitor."""
    import pandas as pd

    # Get top 20 stocks with most recent data
    try:
        df = db_client.execute_query("""
            SELECT ts_code, count() as cnt
            FROM fact_daily_bar
            WHERE trade_date >= '2025-01-01'
            GROUP BY ts_code
            ORDER BY cnt DESC
            LIMIT 20
        """)
        if not df.empty:
            stocks = df["ts_code"].tolist()
            logger.info("  使用 fact_daily_bar 中数据最充分的 %d 只股票作为监控池", len(stocks))
            return stocks
    except Exception as e:
        logger.warning("  获取股票池失败: %s", e)
    return []


# ===========================================================================
# Custom lightweight sentinels that work with actual data
# ===========================================================================

async def run_lightweight_scan(db_client, stock_pool):
    """Run a lightweight sentinel scan adapted to available data."""
    import pandas as pd
    from stock_datasource.modules.sentinel.schemas import (
        AlertCategory, AlertSeverity, SentinelAlert
    )

    alerts = []

    # === Sentinel 1: Market Risk (CSI300 vs MA20 since we only have 54 days) ===
    logger.info("\n  🔍 [market_risk] 扫描市场风险...")
    try:
        df = db_client.execute_query("""
            SELECT trade_date, close
            FROM ods_index_daily
            WHERE ts_code = '000300.SH'
            ORDER BY trade_date ASC
        """)
        if not df.empty and len(df) >= 20:
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["ma20"] = df["close"].rolling(20).mean()
            valid = df.dropna(subset=["ma20"])
            if len(valid) >= 2:
                latest = valid.iloc[-1]
                prev = valid.iloc[-2]
                close = float(latest["close"])
                ma20 = float(latest["ma20"])
                prev_close = float(prev["close"])
                prev_ma20 = float(prev["ma20"])
                deviation = (close - ma20) / ma20 * 100

                if prev_close <= prev_ma20 and close > ma20:
                    alerts.append(SentinelAlert(
                        sentinel_type="market_risk",
                        category=AlertCategory.MARKET_RISK,
                        severity=AlertSeverity.WARNING,
                        index_code="000300.SH",
                        signal_type="ma20_golden_cross",
                        description=f"沪深300突破20日均线: 收盘{close:.2f}, MA20={ma20:.2f}, 偏离{deviation:.1f}%",
                        metric_value=close, threshold=ma20, deviation_pct=deviation,
                        context={"close": close, "ma20": round(ma20, 2), "trade_date": str(latest["trade_date"])}
                    ))
                elif prev_close >= prev_ma20 and close < ma20:
                    alerts.append(SentinelAlert(
                        sentinel_type="market_risk",
                        category=AlertCategory.MARKET_RISK,
                        severity=AlertSeverity.CRITICAL,
                        index_code="000300.SH",
                        signal_type="ma20_death_cross",
                        description=f"沪深300跌破20日均线: 收盘{close:.2f}, MA20={ma20:.2f}, 偏离{deviation:.1f}%",
                        metric_value=close, threshold=ma20, deviation_pct=deviation,
                        context={"close": close, "ma20": round(ma20, 2), "trade_date": str(latest["trade_date"])}
                    ))

                logger.info("    CSI300: close=%.2f, MA20=%.2f, deviation=%.1f%%", close, ma20, deviation)
        else:
            logger.info("    CSI300 数据不足20天")
    except Exception as e:
        logger.warning("    market_risk 扫描失败: %s", e)

    # === Sentinel 2: MA Crossover (MA25/MA120 for pool stocks) ===
    logger.info("  🔍 [ma_crossover] 扫描核心池MA交叉...")
    ma_cross_count = 0
    for ts_code in stock_pool[:15]:  # Limit to 15 for speed
        try:
            df = db_client.execute_query(f"""
                SELECT trade_date, close FROM fact_daily_bar
                WHERE ts_code = '{ts_code}'
                ORDER BY trade_date ASC
            """)
            if df.empty or len(df) < 125:
                continue

            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df["ma25"] = df["close"].rolling(25).mean()
            df["ma120"] = df["close"].rolling(120).mean()
            valid = df.dropna(subset=["ma25", "ma120"])
            if len(valid) < 2:
                continue

            curr = valid.iloc[-1]
            prev = valid.iloc[-2]
            curr_ma25, curr_ma120 = float(curr["ma25"]), float(curr["ma120"])
            prev_ma25, prev_ma120 = float(prev["ma25"]), float(prev["ma120"])

            if prev_ma25 <= prev_ma120 and curr_ma25 > curr_ma120:
                alerts.append(SentinelAlert(
                    sentinel_type="ma_crossover",
                    category=AlertCategory.TECHNICAL,
                    severity=AlertSeverity.WARNING,
                    ts_code=ts_code,
                    signal_type="golden_cross",
                    description=f"{ts_code} MA25上穿MA120金叉: MA25={curr_ma25:.2f}, MA120={curr_ma120:.2f}",
                    metric_value=curr_ma25, threshold=curr_ma120,
                    deviation_pct=round((curr_ma25/curr_ma120 - 1)*100, 2),
                    context={"close": float(curr["close"]), "ma25": round(curr_ma25, 2), "ma120": round(curr_ma120, 2)}
                ))
                ma_cross_count += 1
            elif prev_ma25 >= prev_ma120 and curr_ma25 < curr_ma120:
                alerts.append(SentinelAlert(
                    sentinel_type="ma_crossover",
                    category=AlertCategory.TECHNICAL,
                    severity=AlertSeverity.CRITICAL,
                    ts_code=ts_code,
                    signal_type="death_cross",
                    description=f"{ts_code} MA25下穿MA120死叉: MA25={curr_ma25:.2f}, MA120={curr_ma120:.2f}",
                    metric_value=curr_ma25, threshold=curr_ma120,
                    deviation_pct=round((curr_ma25/curr_ma120 - 1)*100, 2),
                    context={"close": float(curr["close"]), "ma25": round(curr_ma25, 2), "ma120": round(curr_ma120, 2)}
                ))
                ma_cross_count += 1
        except Exception:
            continue
    logger.info("    扫描了 %d 只股票, 发现 %d 个MA交叉信号", min(15, len(stock_pool)), ma_cross_count)

    # === Sentinel 3: Volume Anomaly ===
    logger.info("  🔍 [volume_anomaly] 扫描量能异常...")
    vol_count = 0
    for ts_code in stock_pool[:15]:
        try:
            df = db_client.execute_query(f"""
                SELECT trade_date, vol, pct_chg FROM fact_daily_bar
                WHERE ts_code = '{ts_code}'
                ORDER BY trade_date ASC
            """)
            if df.empty or len(df) < 25:
                continue

            df["vol"] = pd.to_numeric(df["vol"], errors="coerce")
            df["pct_chg"] = pd.to_numeric(df["pct_chg"], errors="coerce")
            avg_vol = df["vol"].iloc[-21:-1].mean()
            if avg_vol <= 0:
                continue

            latest_vol = float(df["vol"].iloc[-1])
            latest_pct = float(df["pct_chg"].iloc[-1]) if not pd.isna(df["pct_chg"].iloc[-1]) else 0
            vol_ratio = latest_vol / avg_vol

            if vol_ratio > 3.0:
                alerts.append(SentinelAlert(
                    sentinel_type="volume_anomaly",
                    category=AlertCategory.VOLUME,
                    severity=AlertSeverity.WARNING,
                    ts_code=ts_code,
                    signal_type="volume_spike",
                    description=f"{ts_code} 成交量暴增{vol_ratio:.1f}倍 (涨跌幅{latest_pct:.1f}%)",
                    metric_value=vol_ratio, threshold=3.0,
                    deviation_pct=round((vol_ratio-1)*100, 1),
                    context={"vol": latest_vol, "avg_vol_20d": round(avg_vol), "pct_chg": latest_pct}
                ))
                vol_count += 1
        except Exception:
            continue
    logger.info("    扫描了 %d 只股票, 发现 %d 个量能异常", min(15, len(stock_pool)), vol_count)

    # === Sentinel 4: Capital Flow (from ods_top_list) ===
    logger.info("  🔍 [capital_flow] 扫描龙虎榜资金...")
    try:
        df = db_client.execute_query("""
            SELECT ts_code, count() as cnt
            FROM ods_top_list
            WHERE trade_date >= toString(subtractDays(today(), 10))
            GROUP BY ts_code
            HAVING cnt >= 2
            ORDER BY cnt DESC
            LIMIT 10
        """)
        if not df.empty:
            for _, row in df.iterrows():
                alerts.append(SentinelAlert(
                    sentinel_type="capital_flow",
                    category=AlertCategory.CAPITAL,
                    severity=AlertSeverity.INFO,
                    ts_code=row["ts_code"],
                    signal_type="toplist_frequent",
                    description=f"{row['ts_code']} 近10日上榜{int(row['cnt'])}次，资金关注度高",
                    metric_value=float(row["cnt"]), threshold=2.0,
                    context={"appearances": int(row["cnt"])}
                ))
            logger.info("    发现 %d 只股票频繁上龙虎榜", len(df))
        else:
            logger.info("    近10日无龙虎榜数据")
    except Exception as e:
        logger.warning("    capital_flow 扫描失败: %s", e)

    return alerts


async def run_demo():
    """Run a full sentinel scan cycle demo."""
    logger.info("=" * 70)
    logger.info("  哨兵体系 (Sentinel System) — 演示运行")
    logger.info("=" * 70)

    # Patch db_client for table name compatibility
    db_client = patch_db_client()

    # Step 1: Test connections
    logger.info("\n[1/4] 测试连接...")
    try:
        df = db_client.execute_query("SELECT 1 as ok")
        logger.info("  ✅ ClickHouse 连接成功 (stock_datasource)")
    except Exception as e:
        logger.error("  ❌ ClickHouse 失败: %s", e)
        return

    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://localhost:6379/0")
        await r.ping()
        await r.close()
        logger.info("  ✅ Redis 连接成功")
    except Exception as e:
        logger.error("  ❌ Redis 失败: %s", e)
        return

    # Step 2: Get stock pool
    logger.info("\n[2/4] 构建监控股票池...")
    stock_pool = seed_fake_core_pool(db_client)
    if not stock_pool:
        logger.error("  无法获取股票池")
        return

    # Step 3: Run sentinels
    logger.info("\n[3/4] 执行哨兵扫描...")
    logger.info("-" * 70)
    alerts = await run_lightweight_scan(db_client, stock_pool)

    # Step 4: Summary + Redis publish
    logger.info("\n[4/4] 扫描结果汇总")
    logger.info("=" * 70)
    logger.info("  总告警数: %d", len(alerts))

    if alerts:
        # Group by type
        from collections import Counter
        type_counts = Counter(a.sentinel_type for a in alerts)
        for t, c in type_counts.items():
            logger.info("    [%s]: %d 条", t, c)

        # Publish to Redis for demo
        import redis.asyncio as aioredis
        r = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        for alert in alerts:
            channel = f"sentinel:{alert.sentinel_type}"
            if alert.ts_code:
                channel += f":{alert.ts_code}"
            await r.publish(channel, alert.model_dump_json())
        logger.info("\n  📡 已发布 %d 条告警到 Redis", len(alerts))
        await r.close()

        # Print alert details
        logger.info("\n  告警明细:")
        for i, alert in enumerate(alerts, 1):
            severity_icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(alert.severity.value, "•")
            logger.info("    %d. %s [%s] %s", i, severity_icon, alert.sentinel_type, alert.description)
    else:
        logger.info("  ℹ️ 无异常信号 — 所有哨兵保持沉默（这是正常状态！）")

    logger.info("\n✅ 演示完成!")


if __name__ == "__main__":
    asyncio.run(run_demo())
