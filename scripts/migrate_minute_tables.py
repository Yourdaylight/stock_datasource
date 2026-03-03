"""数据迁移脚本：将旧分钟K线表数据迁移到统一表。

迁移映射：
  ods_stk_mins      → ods_min_kline_cn   (A股, vol Int64→Float64)
  ods_etf_stk_mins  → ods_min_kline_etf  (ETF)

使用方法：
  python scripts/migrate_minute_tables.py              # dry-run 模式
  python scripts/migrate_minute_tables.py --execute    # 执行迁移
  python scripts/migrate_minute_tables.py --verify     # 仅验证
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from stock_datasource.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MIGRATIONS = [
    {
        "name": "A股分钟K线",
        "source": "ods_stk_mins",
        "target": "ods_min_kline_cn",
        "sql": """
            INSERT INTO {db}.ods_min_kline_cn
                (ts_code, freq, trade_time, open, close, high, low, vol, amount, version, _ingested_at)
            SELECT
                ts_code, freq, trade_time, open, close, high, low,
                toFloat64(vol),
                amount, version, _ingested_at
            FROM {db}.ods_stk_mins
        """,
    },
    {
        "name": "ETF分钟K线",
        "source": "ods_etf_stk_mins",
        "target": "ods_min_kline_etf",
        "sql": """
            INSERT INTO {db}.ods_min_kline_etf
                (ts_code, freq, trade_time, open, close, high, low, vol, amount, version, _ingested_at)
            SELECT
                ts_code, freq, trade_time, open, close, high, low, vol, amount, version, _ingested_at
            FROM {db}.ods_etf_stk_mins
        """,
    },
]


def get_db():
    """Get ClickHouse client."""
    try:
        from stock_datasource.core.database import get_clickhouse_client
        return get_clickhouse_client()
    except Exception:
        import clickhouse_connect
        return clickhouse_connect.get_client(
            host=settings.CLICKHOUSE_HOST,
            port=getattr(settings, "CLICKHOUSE_HTTP_PORT", 8123),
            database=settings.CLICKHOUSE_DATABASE,
        )


def table_exists(client, db: str, table: str) -> bool:
    """Check if a table exists."""
    result = client.execute(
        "SELECT count() FROM system.tables WHERE database = %(db)s AND name = %(table)s",
        {"db": db, "table": table},
    )
    return result[0][0] > 0 if result else False


def get_row_count(client, db: str, table: str) -> int:
    """Get row count for a table."""
    result = client.execute(f"SELECT count() FROM {db}.{table}")
    return result[0][0] if result else 0


def run_migration(execute: bool = False, verify_only: bool = False):
    """Run or preview the migration."""
    client = get_db()
    db = settings.CLICKHOUSE_DATABASE

    logger.info(f"Database: {db}")
    logger.info(f"Mode: {'EXECUTE' if execute else 'VERIFY' if verify_only else 'DRY-RUN'}")
    logger.info("=" * 60)

    for m in MIGRATIONS:
        source, target = m["source"], m["target"]
        logger.info(f"\n--- {m['name']}: {source} → {target} ---")

        src_exists = table_exists(client, db, source)
        tgt_exists = table_exists(client, db, target)

        if not src_exists:
            logger.warning(f"  源表 {source} 不存在，跳过")
            continue

        if not tgt_exists:
            logger.warning(f"  目标表 {target} 不存在，跳过（请先运行 sync_service 创建表）")
            continue

        src_count = get_row_count(client, db, source)
        tgt_count_before = get_row_count(client, db, target)
        logger.info(f"  源表行数: {src_count:,}")
        logger.info(f"  目标表行数(迁移前): {tgt_count_before:,}")

        if src_count == 0:
            logger.info("  源表为空，无需迁移")
            continue

        if verify_only:
            logger.info(f"  [验证] 预计迁移 {src_count:,} 行")
            continue

        if not execute:
            logger.info(f"  [DRY-RUN] 将执行: {m['sql'].format(db=db).strip()[:200]}...")
            continue

        # Execute migration
        logger.info(f"  开始迁移 {src_count:,} 行 ...")
        sql = m["sql"].format(db=db)
        client.execute(sql)

        tgt_count_after = get_row_count(client, db, target)
        added = tgt_count_after - tgt_count_before
        logger.info(f"  迁移完成: 目标表行数 {tgt_count_before:,} → {tgt_count_after:,} (新增 {added:,})")

        if added < src_count:
            logger.info(f"  注: 新增行数({added:,}) < 源表行数({src_count:,})，"
                       f"可能是 ReplacingMergeTree 去重了重复数据")

    logger.info("\n" + "=" * 60)
    logger.info("完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="迁移旧分钟K线表到统一表")
    parser.add_argument("--execute", action="store_true", help="实际执行迁移（默认为 dry-run）")
    parser.add_argument("--verify", action="store_true", help="仅验证表状态")
    args = parser.parse_args()

    run_migration(execute=args.execute, verify_only=args.verify)
