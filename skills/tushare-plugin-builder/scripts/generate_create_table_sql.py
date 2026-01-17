#!/usr/bin/env python3
"""
根据 schema.json 生成 ClickHouse CREATE TABLE SQL。
用于 tushare-plugin-builder skill 生成插件后的建表。

用法:
  python generate_create_table_sql.py path/to/schema.json
  python generate_create_table_sql.py path/to/schema.json --execute  # 直接执行
"""

import argparse
import json
import sys
from pathlib import Path

# 将项目根目录加入 sys.path
project_root = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(project_root / "src"))


def load_schema(schema_path: str) -> dict:
    """加载 schema.json 文件。"""
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_create_table_sql(schema: dict) -> str:
    """根据 schema 生成 CREATE TABLE SQL。"""
    table_name = schema["table_name"]
    columns = schema["columns"]
    engine = schema.get("engine", "ReplacingMergeTree()")
    engine_params = schema.get("engine_params", [])
    partition_by = schema.get("partition_by", "")
    order_by = schema.get("order_by", [])
    
    # 构建列定义
    column_defs = []
    for col in columns:
        col_name = col["name"]
        # 支持 type 或 data_type 字段
        col_type = col.get("type") or col.get("data_type", "String")
        col_comment = col.get("comment", "")
        col_default = col.get("default", "")
        
        col_def = f"    {col_name} {col_type}"
        if col_default:
            col_def += f" DEFAULT {col_default}"
        if col_comment:
            col_def += f" COMMENT '{col_comment}'"
        column_defs.append(col_def)
    
    columns_sql = ",\n".join(column_defs)
    
    # 构建引擎字符串
    if engine_params:
        engine_str = f"{engine}({', '.join(engine_params)})"
    elif "(" not in engine:
        engine_str = f"{engine}()"
    else:
        engine_str = engine
    
    # 构建 SQL
    sql_parts = [
        f"CREATE TABLE IF NOT EXISTS {table_name}",
        "(",
        columns_sql,
        ")",
        f"ENGINE = {engine_str}",
    ]
    
    if partition_by:
        sql_parts.append(f"PARTITION BY {partition_by}")
    
    if order_by:
        if isinstance(order_by, list):
            order_by_str = ", ".join(order_by)
        else:
            order_by_str = order_by
        sql_parts.append(f"ORDER BY ({order_by_str})")
    
    # 添加 settings
    settings = schema.get("settings", {})
    if settings:
        settings_str = ", ".join(f"{k} = {v}" for k, v in settings.items())
        sql_parts.append(f"SETTINGS {settings_str}")
    
    return "\n".join(sql_parts) + ";"


def execute_sql(sql: str) -> bool:
    """在 ClickHouse 中执行 SQL。"""
    try:
        from stock_datasource.models.database import ClickHouseClient
        from stock_datasource.config.settings import settings
        
        print(f"正在连接 ClickHouse: {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}")
        client = ClickHouseClient()
        
        print("正在执行建表 SQL...")
        client.execute(sql)
        print("✅ 表创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="根据 schema.json 生成建表 SQL")
    parser.add_argument("schema_path", help="schema.json 文件路径")
    parser.add_argument("--execute", "-e", action="store_true", help="直接在 ClickHouse 中执行")
    parser.add_argument("--output", "-o", help="输出 SQL 文件路径")
    
    args = parser.parse_args()
    
    # 加载 schema
    schema_path = Path(args.schema_path)
    if not schema_path.exists():
        print(f"❌ 文件不存在: {schema_path}")
        sys.exit(1)
    
    try:
        schema = load_schema(schema_path)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}")
        sys.exit(1)
    
    # 生成 SQL
    sql = generate_create_table_sql(schema)
    
    print("=" * 70)
    print("生成的 CREATE TABLE SQL:")
    print("=" * 70)
    print(sql)
    print("=" * 70)
    
    # 输出到文件
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(sql, encoding="utf-8")
        print(f"\n✅ SQL 已保存到: {output_path}")
    
    # 执行 SQL
    if args.execute:
        print()
        if not execute_sql(sql):
            sys.exit(1)
    else:
        print("\n提示: 使用 --execute 参数可直接在 ClickHouse 中执行")
    
    print("\n✅ 完成")


if __name__ == "__main__":
    main()
