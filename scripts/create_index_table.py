"""Create ods_idx_factor_pro table."""

from stock_datasource.models.database import db_client
import json

# 读取新的 schema
schema_path = 'src/stock_datasource/plugins/tushare_index_daily/schema.json'
with open(schema_path, 'r', encoding='utf-8') as f:
    schema = json.load(f)

table_name = schema['table_name']
print(f'Creating table: {table_name}')

# 构建建表 SQL
columns_sql = ',\n    '.join([
    f"{col['name']} {col['data_type']} COMMENT '{col['comment']}'" 
    for col in schema['columns']
])

create_sql = f'''
CREATE TABLE IF NOT EXISTS {table_name} (
    {columns_sql}
) ENGINE = {schema['engine']}({', '.join(schema['engine_params'])})
PARTITION BY {schema['partition_by']}
ORDER BY ({', '.join(schema['order_by'])})
COMMENT '{schema['comment']}'
'''

try:
    db_client.primary.client.execute(create_sql)
    print(f'\nTable {table_name} created successfully!')
except Exception as e:
    print(f'\nError creating table: {e}')
    import traceback
    traceback.print_exc()
