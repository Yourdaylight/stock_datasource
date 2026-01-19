"""Sync index daily data for 2026-01."""

from stock_datasource.models.database import db_client
from datetime import datetime
import pandas as pd
import time

# 直接使用插件同步
from stock_datasource.core.plugin_manager import plugin_manager

# 确保插件已注册
plugin_manager.discover_plugins()

dates = ['20260105', '20260106', '20260107', '20260108', '20260109', '20260112', '20260113']

print('Syncing index daily data...')
total_inserted = 0

for date in dates:
    try:
        plugin = plugin_manager.get_plugin('tushare_index_daily')
        if not plugin:
            print(f'  {date}: Plugin not found')
            continue
        
        data = plugin.extract_data(trade_date=date)
        if data.empty:
            print(f'  {date}: No data')
            continue
        
        # Transform data
        data = plugin.transform_data(data)
        
        if plugin.validate_data(data):
            # Load data using plugin's load_data method
            result = plugin.load_data(data)
            if result.get('status') == 'success':
                count = result.get('total_records', 0)
                total_inserted += count
                print(f'  {date}: {count} records inserted')
            else:
                print(f'  {date}: Load failed - {result.get("error", "Unknown error")}')
        
        time.sleep(1)  # Rate limiting
    except Exception as e:
        print(f'  {date}: ERROR - {str(e)[:100]}')
        import traceback
        traceback.print_exc()

print(f'\nTotal: {total_inserted} records inserted')
