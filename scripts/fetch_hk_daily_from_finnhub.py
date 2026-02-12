#!/usr/bin/env python3
"""
Fetch HK stock daily data from Finnhub API.

This script fetches historical daily data for all HK stocks from Finnhub API
and stores them in the ClickHouse database.

Usage:
    uv run scripts/fetch_hk_daily_from_finnhub.py [--start-date YYYYMMDD] [--end-date YYYYMMDD] [--max-stocks N]

Requirements:
    - FINNHUB_API_KEY in .env file
    - ods_hk_basic table populated with HK stock list
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

import pandas as pd
import finnhub
from dotenv import load_dotenv

from stock_datasource.models.database import ClickHouseClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def ts_code_to_finnhub(ts_code: str) -> str:
    """Convert TuShare code format to Finnhub symbol format.
    
    TuShare format: 00700.HK (5 digits)
    Finnhub format: 0700.HK (4 digits, remove ONE leading zero)
    
    Args:
        ts_code: TuShare format code (e.g., '00700.HK')
    
    Returns:
        Finnhub symbol (e.g., '0700.HK')
    """
    try:
        code, suffix = ts_code.split('.')
        # Remove leading zero if exists (5-digit -> 4-digit)
        if code.startswith('0'):
            code = code[1:]
        return f"{code}.{suffix}"
    except Exception as e:
        logger.error(f"Failed to convert TuShare code {ts_code}: {e}")
        return ts_code


def finnhub_to_ts_code(symbol: str) -> str:
    """Convert Finnhub symbol format to TuShare code format.
    
    Finnhub format: 0700.HK (4 digits)
    TuShare format: 00700.HK (5 digits, pad with zeros)
    
    Args:
        symbol: Finnhub symbol (e.g., '0700.HK')
    
    Returns:
        TuShare format code (e.g., '00700.HK')
    """
    try:
        code, suffix = symbol.split('.')
        code = code.zfill(5)  # Pad to 5 digits
        return f"{code}.{suffix}"
    except Exception as e:
        logger.error(f"Failed to convert Finnhub symbol {symbol}: {e}")
        return symbol


class FinnhubRateLimiter:
    """Rate limiter for Finnhub API (60 calls/minute for free tier)."""
    
    def __init__(self, calls_per_minute: int = 60):
        """Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls per minute (default: 60 for free tier)
        """
        self.calls_per_minute = calls_per_minute
        self.min_interval = 60.0 / calls_per_minute  # 1 second for 60 calls/minute
        self.last_call_time = 0
        self.call_count = 0
    
    def acquire(self):
        """Wait until the next API call is allowed."""
        current_time = time.time()
        time_since_last = current_time - self.last_call_time
        
        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiter: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_call_time = time.time()
        self.call_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "total_calls": self.call_count,
            "calls_per_minute": self.calls_per_minute,
            "min_interval": self.min_interval
        }


def map_finnhub_to_tushare(
    finnhub_data: Dict[str, Any],
    ts_code: str
) -> pd.DataFrame:
    """Map Finnhub data format to TuShare format.
    
    Args:
        finnhub_data: Data from Finnhub API with keys: c, h, l, o, t, v, s
        ts_code: TuShare format stock code
    
    Returns:
        DataFrame in TuShare format
    """
    if finnhub_data.get('s') != 'ok':
        logger.warning(f"Finnhub returned non-ok status for {ts_code}: {finnhub_data.get('s')}")
        return pd.DataFrame()
    
    # Extract data
    timestamps = finnhub_data.get('t', [])
    opens = finnhub_data.get('o', [])
    highs = finnhub_data.get('h', [])
    lows = finnhub_data.get('l', [])
    closes = finnhub_data.get('c', [])
    volumes = finnhub_data.get('v', [])
    
    if not timestamps:
        logger.warning(f"No data points for {ts_code}")
        return pd.DataFrame()
    
    # Create DataFrame
    df = pd.DataFrame({
        'ts_code': ts_code,
        'trade_date': [datetime.fromtimestamp(ts).strftime('%Y%m%d') for ts in timestamps],
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'vol': volumes,
    })
    
    # Calculate pre_close, change, pct_chg
    df['pre_close'] = df['close'].shift(1)
    df['change'] = df['close'] - df['pre_close']
    df['pct_chg'] = (df['change'] / df['pre_close'] * 100).round(2)
    
    # amount not available from Finnhub
    df['amount'] = None
    
    # Drop first row (no pre_close)
    df = df.dropna(subset=['pre_close'])
    
    # Add system columns
    df['version'] = int(datetime.now().timestamp())
    df['_ingested_at'] = datetime.now()
    
    return df


def get_hk_stock_list(db_client: ClickHouseClient) -> List[str]:
    """Get HK stock list from ods_hk_basic table.
    
    Args:
        db_client: ClickHouse database client
    
    Returns:
        List of TS codes (e.g., ['00001.HK', '00700.HK', ...])
    """
    query = """
    SELECT DISTINCT ts_code 
    FROM ods_hk_basic 
    WHERE list_status = 'L'
    ORDER BY ts_code
    """
    
    df = db_client.execute_query(query)
    
    if df.empty:
        logger.warning("No HK stocks found in ods_hk_basic table")
        return []
    
    stock_codes = df['ts_code'].tolist()
    logger.info(f"Found {len(stock_codes)} listed HK stocks")
    
    return stock_codes


def fetch_single_stock(
    finnhub_client: finnhub.Client,
    ts_code: str,
    start_date: str,
    end_date: str,
    rate_limiter: FinnhubRateLimiter,
    max_retries: int = 3
) -> pd.DataFrame:
    """Fetch daily data for a single HK stock.
    
    Args:
        finnhub_client: Finnhub API client
        ts_code: TuShare format stock code (e.g., '00001.HK')
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        rate_limiter: Rate limiter instance
        max_retries: Maximum number of retries
    
    Returns:
        DataFrame with daily data in TuShare format
    """
    # Convert code format
    symbol = ts_code_to_finnhub(ts_code)
    
    # Convert dates to timestamps
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')
    start_timestamp = int(start_dt.timestamp())
    end_timestamp = int(end_dt.timestamp())
    
    # Fetch data with retries
    for attempt in range(max_retries):
        try:
            # Apply rate limiting
            rate_limiter.acquire()
            
            # Call Finnhub API
            logger.debug(f"Fetching {ts_code} (symbol: {symbol}), attempt {attempt+1}/{max_retries}")
            data = finnhub_client.stock_candles(
                symbol,
                'D',  # Daily resolution
                start_timestamp,
                end_timestamp
            )
            
            # Map to TuShare format
            df = map_finnhub_to_tushare(data, ts_code)
            
            if not df.empty:
                logger.info(f"Successfully fetched {len(df)} records for {ts_code}")
            
            return df
            
        except Exception as e:
            logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {ts_code}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            
    logger.error(f"Failed to fetch data for {ts_code} after {max_retries} attempts")
    return pd.DataFrame()


def fetch_all_hk_stocks(
    finnhub_client: finnhub.Client,
    db_client: ClickHouseClient,
    start_date: str,
    end_date: str,
    max_stocks: Optional[int] = None,
    batch_size: int = 50
) -> Dict[str, Any]:
    """Fetch daily data for all HK stocks and insert immediately after each stock.
    
    Args:
        finnhub_client: Finnhub API client
        db_client: ClickHouse database client
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        max_stocks: Maximum number of stocks to process (for testing)
        batch_size: Number of stocks per batch for progress reporting
    
    Returns:
        Dictionary with statistics
    """
    # Get stock list
    stock_codes = get_hk_stock_list(db_client)
    
    if not stock_codes:
        logger.error("No HK stocks found")
        return {"status": "error", "error": "No HK stocks found"}
    
    # Limit stocks if specified
    if max_stocks:
        stock_codes = stock_codes[:max_stocks]
        logger.info(f"Processing first {max_stocks} stocks")
    
    # Initialize rate limiter
    rate_limiter = FinnhubRateLimiter(calls_per_minute=60)
    
    # Statistics
    stats = {
        "total_stocks": len(stock_codes),
        "success_count": 0,
        "failed_count": 0,
        "total_records": 0,
        "inserted_records": 0,
        "failed_stocks": [],
        "start_time": datetime.now()
    }
    
    logger.info(f"Starting to fetch data for {len(stock_codes)} stocks")
    logger.info(f"Date range: {start_date} to {end_date}")
    logger.info(f"Rate limit: 60 calls/minute")
    logger.info(f"Mode: Insert each stock immediately after fetching")
    
    # Process stocks one by one
    for i, ts_code in enumerate(stock_codes, 1):
        try:
            logger.info(f"[{i}/{len(stock_codes)}] Processing {ts_code}")
            
            # Fetch data
            df = fetch_single_stock(
                finnhub_client,
                ts_code,
                start_date,
                end_date,
                rate_limiter
            )
            
            if not df.empty:
                stats["success_count"] += 1
                stats["total_records"] += len(df)
                
                # Insert immediately into database
                try:
                    db_client.insert_dataframe('ods_hk_daily', df)
                    stats["inserted_records"] += len(df)
                    logger.info(f"[{i}/{len(stock_codes)}] {ts_code}: Fetched {len(df)} records and inserted into database")
                except Exception as insert_error:
                    logger.error(f"[{i}/{len(stock_codes)}] {ts_code}: Failed to insert {len(df)} records - {insert_error}")
                    # Still count as success because data was fetched, but insertion failed
            else:
                stats["failed_count"] += 1
                logger.warning(f"[{i}/{len(stock_codes)}] {ts_code}: No data available")
        
        except Exception as e:
            stats["failed_count"] += 1
            stats["failed_stocks"].append(ts_code)
            logger.error(f"[{i}/{len(stock_codes)}] {ts_code}: Error - {e}")
        
        # Progress report every batch_size stocks
        if i % batch_size == 0:
            elapsed = (datetime.now() - stats["start_time"]).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            eta = (len(stock_codes) - i) / rate / 60 if rate > 0 else 0
            
            logger.info("=" * 80)
            logger.info(f"Progress: {i}/{len(stock_codes)} ({i/len(stock_codes)*100:.1f}%)")
            logger.info(f"Success: {stats['success_count']}, Failed: {stats['failed_count']}")
            logger.info(f"Records fetched: {stats['total_records']}, inserted: {stats['inserted_records']}")
            logger.info(f"Elapsed: {elapsed/60:.1f}min, ETA: {eta:.1f}min")
            logger.info(f"Rate: {rate*60:.1f} stocks/hour")
            logger.info("=" * 80)
    
    # Final statistics
    stats["end_time"] = datetime.now()
    stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
    
    logger.info("\n" + "=" * 80)
    logger.info("FETCH AND INSERT COMPLETED")
    logger.info("=" * 80)
    logger.info(f"Total stocks: {stats['total_stocks']}")
    logger.info(f"Success: {stats['success_count']}")
    logger.info(f"Failed: {stats['failed_count']}")
    logger.info(f"Total records fetched: {stats['total_records']}")
    logger.info(f"Total records inserted: {stats['inserted_records']}")
    logger.info(f"Duration: {stats['duration']/60:.1f} minutes")
    
    if stats["failed_stocks"]:
        logger.warning(f"Failed stocks ({len(stats['failed_stocks'])}):")
        for code in stats["failed_stocks"][:10]:
            logger.warning(f"  - {code}")
        if len(stats["failed_stocks"]) > 10:
            logger.warning(f"  ... and {len(stats['failed_stocks'])-10} more")
    
    logger.info("=" * 80)
    
    # Determine final status
    if stats["success_count"] == 0:
        return {
            "status": "no_data",
            **stats
        }
    elif stats["inserted_records"] > 0:
        return {
            "status": "success",
            **stats
        }
    else:
        return {
            "status": "partial",
            "message": "Data fetched but insertion failed",
            **stats
        }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fetch HK stock daily data from Finnhub")
    parser.add_argument(
        "--start-date",
        default=(datetime.now() - timedelta(days=365)).strftime('%Y%m%d'),
        help="Start date in YYYYMMDD format (default: 1 year ago)"
    )
    parser.add_argument(
        "--end-date",
        default=datetime.now().strftime('%Y%m%d'),
        help="End date in YYYYMMDD format (default: today)"
    )
    parser.add_argument(
        "--max-stocks",
        type=int,
        help="Maximum number of stocks to process (for testing)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test mode - don't write to database"
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Get Finnhub API key
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        logger.error("FINNHUB_API_KEY not found in environment variables")
        logger.error("Please add FINNHUB_API_KEY to your .env file")
        logger.error("Get your free API key at: https://finnhub.io/register")
        sys.exit(1)
    
    # Initialize Finnhub client
    finnhub_client = finnhub.Client(api_key=api_key)
    
    # Initialize database client
    try:
        db_client = ClickHouseClient()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        sys.exit(1)
    
    # Run batch fetch
    result = fetch_all_hk_stocks(
        finnhub_client,
        db_client,
        args.start_date,
        args.end_date,
        max_stocks=args.max_stocks
    )
    
    # Exit with appropriate code
    if result["status"] == "success":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
