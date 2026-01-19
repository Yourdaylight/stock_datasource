#!/usr/bin/env python
"""Sync missing market data for 2026 January."""

import sys
import time
from datetime import datetime

# Add project to path
sys.path.insert(0, '/data/openresource/stock_datasource/src')

from stock_datasource.core.trade_calendar import trade_calendar_service
from stock_datasource.plugins.tushare_daily.plugin import TuShareDailyPlugin
from stock_datasource.plugins.tushare_daily_basic.plugin import TuShareDailyBasicPlugin
from stock_datasource.plugins.tushare_etf_fund_daily.plugin import TuShareETFFundDailyPlugin


def sync_daily_data(dates: list[str]):
    """Sync daily stock data for given dates."""
    plugin = TuShareDailyPlugin()
    
    for date in dates:
        print(f"\n{'='*60}")
        print(f"Syncing tushare_daily for {date}")
        print(f"{'='*60}")
        
        try:
            result = plugin.run(trade_date=date)
            status = result.get('status', 'unknown')
            total = result.get('steps', {}).get('load', {}).get('total_records', 0)
            print(f"Status: {status}, Records: {total}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Rate limit
        time.sleep(0.5)


def sync_daily_basic_data(dates: list[str]):
    """Sync daily basic data for given dates."""
    plugin = TuShareDailyBasicPlugin()
    
    for date in dates:
        print(f"\n{'='*60}")
        print(f"Syncing tushare_daily_basic for {date}")
        print(f"{'='*60}")
        
        try:
            result = plugin.run(trade_date=date)
            status = result.get('status', 'unknown')
            total = result.get('steps', {}).get('load', {}).get('total_records', 0)
            print(f"Status: {status}, Records: {total}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Rate limit
        time.sleep(0.5)


def sync_etf_daily_data(dates: list[str]):
    """Sync ETF daily data for given dates."""
    plugin = TuShareETFFundDailyPlugin()
    
    for date in dates:
        print(f"\n{'='*60}")
        print(f"Syncing tushare_etf_fund_daily for {date}")
        print(f"{'='*60}")
        
        try:
            result = plugin.run(trade_date=date)
            status = result.get('status', 'unknown')
            total = result.get('steps', {}).get('load', {}).get('total_records', 0)
            print(f"Status: {status}, Records: {total}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Rate limit
        time.sleep(0.5)


def main():
    # Get trading days from 2026-01-01 to 2026-01-13
    trading_days = trade_calendar_service.get_trading_days_between('20260101', '20260113')
    
    # Convert to YYYYMMDD format (already strings like '20260105')
    dates = [d.replace('-', '') if '-' in str(d) else str(d) for d in trading_days]
    # Ensure format is YYYYMMDD
    dates = [d[:8] if len(d) > 8 else d for d in dates]
    
    print(f"Trading days to sync: {dates}")
    print(f"Total: {len(dates)} days")
    
    # Sync all data types
    print("\n" + "="*80)
    print("SYNCING DAILY STOCK DATA")
    print("="*80)
    sync_daily_data(dates)
    
    print("\n" + "="*80)
    print("SYNCING DAILY BASIC DATA")
    print("="*80)
    sync_daily_basic_data(dates)
    
    print("\n" + "="*80)
    print("SYNCING ETF DAILY DATA")
    print("="*80)
    sync_etf_daily_data(dates)
    
    print("\n" + "="*80)
    print("SYNC COMPLETE")
    print("="*80)


if __name__ == "__main__":
    main()
