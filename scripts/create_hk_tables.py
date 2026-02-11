#!/usr/bin/env python3
"""创建 HK 插件的 ClickHouse 表"""
import json
import requests
from stock_datasource.utils.schema_manager import schema_manager, dict_to_schema

HOST = '9.134.243.46'
PORT = 8123
USER = 'clickhouse'
PASSWORD = 'clickhouse'
DATABASE = 'stock_datasource'

PLUGINS = [
    'tushare_hk_fina_indicator',
    'tushare_hk_balancesheet',
    'tushare_hk_income',
    'tushare_hk_cashflow',
]

for p in PLUGINS:
    with open(f'src/stock_datasource/plugins/{p}/schema.json') as f:
        schema_dict = json.load(f)
    schema = dict_to_schema(schema_dict)
    sql = schema_manager._build_create_table_sql(schema)

    resp = requests.post(
        f'http://{HOST}:{PORT}/',
        params={'database': DATABASE},
        data=sql.encode('utf-8'),
        auth=(USER, PASSWORD),
        headers={'Content-Type': 'text/plain; charset=utf-8'},
    )
    if resp.status_code == 200:
        print(f'✅ 建表成功: {schema.table_name}')
    else:
        print(f'❌ 建表失败: {schema.table_name}: {resp.status_code} {resp.text[:300]}')
