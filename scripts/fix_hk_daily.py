"""One-time script to seed HK daily data using akshare (tushare rate-limited today).

Fetches recent HK daily data for all listed stocks and inserts into ods_hk_daily.
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import sys

from stock_datasource.models.database import db_client

# Get all listed HK stocks from ods_hk_basic
stocks_df = db_client.execute_query("""
    SELECT DISTINCT ts_code FROM ods_hk_basic 
""")
print(f"Total HK stocks: {len(stocks_df)}")

stock_codes = stocks_df['ts_code'].tolist()
target_start = pd.Timestamp('2026-02-03')

all_data = []
errors = []
total = len(stock_codes)

for i, ts_code in enumerate(stock_codes):
    code = ts_code.replace('.HK', '')
    
    if (i + 1) % 100 == 0 or i == 0:
        print(f"Progress: {i+1}/{total} ({len(all_data)} rows collected, {len(errors)} errors)")
        sys.stdout.flush()
    
    try:
        df = ak.stock_hk_daily(symbol=code, adjust="")
        if df is None or df.empty:
            continue
        
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Get one extra day before target for pre_close calculation
        mask_start = target_start - pd.Timedelta(days=7)  # buffer for weekends
        recent = df[df['date'] >= mask_start].copy()
        
        if recent.empty:
            continue
        
        # Calculate pre_close and pct_chg on the extended range
        recent['pre_close'] = recent['close'].shift(1)
        recent['change'] = recent['close'] - recent['pre_close']
        recent['pct_chg'] = np.where(
            recent['pre_close'] != 0,
            (recent['change'] / recent['pre_close']) * 100,
            0
        )
        recent['pct_chg'] = recent['pct_chg'].round(4)
        
        # Now filter to target dates only
        recent = recent[recent['date'] >= target_start]
        if recent.empty:
            continue
        
        # Map to ods_hk_daily schema
        result = pd.DataFrame({
            'ts_code': ts_code,
            'trade_date': recent['date'].dt.date.values,
            'open': recent['open'].values,
            'high': recent['high'].values,
            'low': recent['low'].values,
            'close': recent['close'].values,
            'pre_close': recent['pre_close'].values,
            'change': recent['change'].values,
            'pct_chg': recent['pct_chg'].values,
            'vol': recent['volume'].values,
            'amount': np.nan,  # not available from akshare
        })
        
        all_data.append(result)
        time.sleep(0.15)  # Rate limit
        
    except Exception as e:
        errors.append((ts_code, str(e)))
        time.sleep(0.3)

print(f"\nCollection complete: {len(all_data)} stocks, {len(errors)} errors")

if not all_data:
    print("No data collected!")
    sys.exit(1)

combined = pd.concat(all_data, ignore_index=True)
print(f"Total rows: {len(combined)}")
print(f"Date range: {combined['trade_date'].min()} to {combined['trade_date'].max()}")

# Add system columns
now = datetime.now().replace(microsecond=0)
combined['version'] = int(now.timestamp())
combined['_ingested_at'] = now.strftime('%Y-%m-%d %H:%M:%S')

# Insert in batches
batch_size = 10000
for start in range(0, len(combined), batch_size):
    batch = combined.iloc[start:start + batch_size]
    try:
        db_client.insert_dataframe('ods_hk_daily', batch)
        print(f"  Inserted rows {start}-{start + len(batch)}")
    except Exception as e:
        print(f"  Error inserting batch {start}: {e}")

# Optimize
print("\nOptimizing table...")
db_client.execute_query("OPTIMIZE TABLE ods_hk_daily FINAL")
time.sleep(3)

# Verify
result = db_client.execute_query("""
    SELECT trade_date, count() as cnt 
    FROM ods_hk_daily 
    GROUP BY trade_date 
    ORDER BY trade_date
""")
print("\nFinal data counts:")
print(result.to_string())

total_count = db_client.execute_query("SELECT count() as cnt FROM ods_hk_daily")
print(f"\nTotal: {total_count.iloc[0]['cnt']}")

if errors:
    print(f"\n{len(errors)} errors (first 5):")
    for code, err in errors[:5]:
        print(f"  {code}: {err}")
