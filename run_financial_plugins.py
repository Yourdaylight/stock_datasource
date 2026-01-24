#!/usr/bin/env python3
"""Run financial statement plugins to extract data from TuShare API and load to backup database."""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from stock_datasource.core.plugin_manager import plugin_manager
from stock_datasource.models.database import db_client
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure to use backup database only
os.environ['BACKUP_CLICKHOUSE_HOST'] = os.getenv('BACKUP_CLICKHOUSE_HOST', '129.28.41.236')
os.environ['BACKUP_CLICKHOUSE_PORT'] = os.getenv('BACKUP_CLICKHOUSE_PORT', '9000')
os.environ['BACKUP_CLICKHOUSE_USER'] = os.getenv('BACKUP_CLICKHOUSE_USER', 'default')
os.environ['BACKUP_CLICKHOUSE_PASSWORD'] = os.getenv('BACKUP_CLICKHOUSE_PASSWORD', 'BB7rfRUdCPWLzkoy55hhKg3o')
os.environ['BACKUP_CLICKHOUSE_DATABASE'] = os.getenv('BACKUP_CLICKHOUSE_DATABASE', 'stock_datasource')

# Temporarily disable primary database to only use backup
os.environ['CLICKHOUSE_HOST'] = os.getenv('BACKUP_CLICKHOUSE_HOST')
os.environ['CLICKHOUSE_PORT'] = os.getenv('BACKUP_CLICKHOUSE_PORT')
os.environ['CLICKHOUSE_USER'] = os.getenv('BACKUP_CLICKHOUSE_USER')
os.environ['CLICKHOUSE_PASSWORD'] = os.getenv('BACKUP_CLICKHOUSE_PASSWORD')

PLUGINS = [
    'tushare_income',
    'tushare_balancesheet',
    'tushare_cashflow',
    'tushare_express',
    'tushare_forecast'
]

def run_plugin(plugin_name):
    """Run a single plugin to extract and load data."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Running plugin: {plugin_name}")
    print(f"{'='*60}\n")

    try:
        # Discover and get plugin
        plugin = plugin_manager.get_plugin(plugin_name)
        if not plugin:
            print(f"❌ Plugin {plugin_name} not found")
            return False

        # Extract data from TuShare API
        print(f"[{datetime.now()}] Extracting data from TuShare API...")
        data = plugin.extract_data()

        if data is None or data.empty:
            print(f"⚠️ No data extracted from TuShare API for {plugin_name}")
            return True

        print(f"[{datetime.now()}] Extracted {len(data)} records")

        # Transform data
        print(f"[{datetime.now()}] Transforming data...")
        data = plugin.transform_data(data)

        # Validate data
        print(f"[{datetime.now()}] Validating data...")
        if not plugin.validate_data(data):
            print(f"❌ Data validation failed for {plugin_name}")
            return False

        # Load data to backup database
        print(f"[{datetime.now()}] Loading data to backup database...")
        result = plugin.load_data(data)

        if result.get('status') == 'success':
            loaded = result.get('loaded_records', 0)
            print(f"✅ Successfully loaded {loaded} records to backup database")
            return True
        else:
            print(f"❌ Failed to load data: {result.get('error', 'Unknown error')}")
            return False

    except Exception as e:
        print(f"❌ Error running plugin {plugin_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all financial statement plugins."""
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Starting financial statement plugins")
    print(f"Target: Backup Database (129.28.41.236)")
    print(f"{'='*60}\n")

    # Discover all plugins
    print(f"[{datetime.now()}] Discovering plugins...")
    plugin_manager.discover_plugins()

    # Run each plugin
    results = {}
    for plugin_name in PLUGINS:
        results[plugin_name] = run_plugin(plugin_name)

    # Summary
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] Plugin Execution Summary")
    print(f"{'='*60}\n")

    success_count = 0
    for plugin_name, success in results.items():
        status = "✅" if success else "❌"
        print(f"{status} {plugin_name}")
        if success:
            success_count += 1

    print(f"\nTotal: {success_count}/{len(PLUGINS)} plugins completed successfully")
    print(f"{'='*60}\n")

    return success_count == len(PLUGINS)

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n\n[{datetime.now()}] ⚠️ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
