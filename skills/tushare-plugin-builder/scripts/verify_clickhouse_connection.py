#!/usr/bin/env python3
"""
验证 ClickHouse 连接与表状态脚本。
用于 tushare-plugin-builder skill 生成插件后的数据库验证。

用法:
  python verify_clickhouse_connection.py                 # 仅测试连接
  python verify_clickhouse_connection.py --table TABLE  # 验证指定表
  python verify_clickhouse_connection.py --table TABLE --date 20250110  # 验证指定日期数据
"""

import argparse
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))

from stock_datasource.models.database import ClickHouseClient
from stock_datasource.config.settings import settings


def test_connection() -> bool:
    """测试 ClickHouse 连接。"""
    print(f"正在连接 ClickHouse: {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}")
    print(f"数据库: {settings.CLICKHOUSE_DATABASE}")
    try:
        client = ClickHouseClient()
        result = client.execute("SELECT 1")
        if result and result[0][0] == 1:
            print("✅ ClickHouse 连接成功")
            return True
        else:
            print("❌ ClickHouse 连接异常：返回值不正确")
            return False
    except Exception as e:
        print(f"❌ ClickHouse 连接失败: {e}")
        return False


def verify_table(table_name: str) -> bool:
    """验证表是否存在并输出表结构。"""
    print(f"\n正在验证表: {table_name}")
    try:
        client = ClickHouseClient()
        
        # 检查表是否存在
        if not client.table_exists(table_name):
            print(f"❌ 表 {table_name} 不存在")
            return False
        
        print(f"✅ 表 {table_name} 存在")
        
        # 获取表结构
        schema = client.get_table_schema(table_name)
        print(f"\n表结构 ({len(schema)} 列):")
        print("-" * 60)
        for col in schema:
            print(f"  {col['column_name']:30} {col['data_type']}")
        print("-" * 60)
        
        # 获取数据统计
        result = client.execute(f"SELECT count() FROM {table_name}")
        row_count = result[0][0]
        print(f"\n总行数: {row_count:,}")
        
        # 获取分区信息
        partitions = client.get_partition_info(table_name)
        if partitions:
            print(f"\n分区数: {len(partitions)}")
            print("最近分区:")
            for p in partitions[-5:]:
                print(f"  {p['partition']}: {p['rows']:,} 行")
        
        return True
    except Exception as e:
        print(f"❌ 验证表失败: {e}")
        return False


def verify_data(table_name: str, trade_date: str) -> bool:
    """验证指定日期的数据。"""
    print(f"\n正在验证 {table_name} 中 {trade_date} 的数据...")
    try:
        client = ClickHouseClient()
        
        # 格式化日期
        if len(trade_date) == 8:
            formatted_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:]}"
        else:
            formatted_date = trade_date
        
        # 查询数据统计
        query = """
        SELECT 
            count() as cnt,
            min(trade_date) as min_date,
            max(trade_date) as max_date
        FROM {table}
        WHERE trade_date = %(date)s
        """.format(table=table_name)
        
        result = client.execute_query(query, {"date": formatted_date})
        
        if result.empty or result.iloc[0]["cnt"] == 0:
            print(f"⚠️  未找到 {trade_date} 的数据")
            return False
        
        row = result.iloc[0]
        print(f"✅ 找到 {row['cnt']:,} 条 {trade_date} 的数据")
        
        # 查询样本数据
        sample_query = """
        SELECT * FROM {table}
        WHERE trade_date = %(date)s
        LIMIT 5
        """.format(table=table_name)
        
        sample_data = client.execute_query(sample_query, {"date": formatted_date})
        if not sample_data.empty:
            print(f"\n样本数据 (前5条):")
            print(sample_data.to_string(index=False))
        
        return True
    except Exception as e:
        print(f"❌ 验证数据失败: {e}")
        return False


def list_tables(pattern: str = None) -> None:
    """列出数据库中的表。"""
    try:
        client = ClickHouseClient()
        query = f"""
        SELECT name, total_rows, total_bytes
        FROM system.tables
        WHERE database = '{settings.CLICKHOUSE_DATABASE}'
        """
        if pattern:
            query += f" AND name LIKE '%{pattern}%'"
        query += " ORDER BY name"
        
        result = client.execute_query(query)
        print(f"\n数据库 {settings.CLICKHOUSE_DATABASE} 中的表:")
        print("-" * 70)
        for _, row in result.iterrows():
            size_mb = row["total_bytes"] / (1024 * 1024) if row["total_bytes"] else 0
            print(f"  {row['name']:40} {row['total_rows']:>12,} 行  {size_mb:>8.2f} MB")
        print("-" * 70)
        print(f"共 {len(result)} 张表")
    except Exception as e:
        print(f"❌ 列出表失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="验证 ClickHouse 连接与数据")
    parser.add_argument("--table", "-t", help="要验证的表名")
    parser.add_argument("--date", "-d", help="要验证的交易日期 (YYYYMMDD 或 YYYY-MM-DD)")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有表")
    parser.add_argument("--pattern", "-p", help="表名过滤模式 (与 --list 一起使用)")
    
    args = parser.parse_args()
    
    # 测试连接
    if not test_connection():
        sys.exit(1)
    
    # 列出表
    if args.list:
        list_tables(args.pattern)
        sys.exit(0)
    
    # 验证表
    if args.table:
        if not verify_table(args.table):
            sys.exit(1)
        
        # 验证数据
        if args.date:
            if not verify_data(args.table, args.date):
                sys.exit(1)
    
    print("\n✅ 验证完成")


if __name__ == "__main__":
    main()
