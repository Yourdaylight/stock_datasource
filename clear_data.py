#!/usr/bin/env python3
"""清空所有表的数据"""

import requests
import os

host = os.getenv('CLICKHOUSE_HOST', '129.28.41.236')
http_port = 8123
user = os.getenv('CLICKHOUSE_USER', 'default')
password = os.getenv('CLICKHOUSE_PASSWORD', '')

def execute_query(query):
    """使用 HTTP API 执行查询"""
    url = f"http://{host}:{http_port}/"
    params = {'query': query}
    response = requests.post(url, params=params, auth=(user, password))
    if response.status_code != 200:
        raise Exception(f"Query failed: {response.text}")
    return response.text

# 清空所有表
tables = [
    'ods_stock_basic', 'dim_security', 'fact_daily_bar', 'ods_daily_basic', 
    'ods_trade_calendar', 'ods_stk_limit', 'ods_suspend_d', 'ods_daily', 'ods_adj_factor'
]

print("=" * 60)
print("清空所有表数据")
print("=" * 60)

for table in tables:
    try:
        print(f"清空表: {table}...", end=" ")
        execute_query(f"TRUNCATE TABLE stock_datasource.{table}")
        print("✅")
    except Exception as e:
        print(f"❌ {str(e)[:50]}")

print("\n✅ 所有表已清空！")
