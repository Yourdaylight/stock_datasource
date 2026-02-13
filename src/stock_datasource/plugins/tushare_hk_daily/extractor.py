"""YFinance Hong Kong Stock Daily data extractor."""

import logging
import json
import time
import pandas as pd
from typing import Optional, List
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


def ts_code_to_yf(ts_code: str) -> str:
    """Convert TuShare code format to yfinance format.
    
    TuShare format: 00700.HK (5 digits)
    yfinance format: 0700.HK (4 digits, remove leading zeros)
    
    Args:
        ts_code: TuShare format code (e.g., '00700.HK')
    
    Returns:
        yfinance format code (e.g., '0700.HK')
    """
    try:
        code, suffix = ts_code.split('.')
        code = code.lstrip('0') or '0'  # Remove leading zeros, but keep at least one digit
        return f"{code}.{suffix}"
    except Exception as e:
        logger.error(f"Failed to convert TuShare code {ts_code}: {e}")
        return ts_code


def yf_code_to_ts(yf_code: str) -> str:
    """Convert yfinance code format to TuShare format.
    
    yfinance format: 0700.HK (4 digits)
    TuShare format: 00700.HK (5 digits, pad with zeros)
    
    Args:
        yf_code: yfinance format code (e.g., '0700.HK')
    
    Returns:
        TuShare format code (e.g., '00700.HK')
    """
    try:
        code, suffix = yf_code.split('.')
        code = code.zfill(5)  # Pad to 5 digits
        return f"{code}.{suffix}"
    except Exception as e:
        logger.error(f"Failed to convert yfinance code {yf_code}: {e}")
        return yf_code


class YFinanceRateLimiter:
    """Rate limiter using token bucket algorithm."""
    
    def __init__(self, calls_per_minute: int = 60):
        """Initialize rate limiter.
        
        Args:
            calls_per_minute: Maximum calls per minute (default: 60)
        """
        self.calls_per_minute = calls_per_minute
        self.tokens = calls_per_minute
        self.last_update = time.time()
    
    def acquire(self):
        """Acquire a token, wait if necessary."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Replenish tokens
        self.tokens = min(
            self.calls_per_minute,
            self.tokens + elapsed * (self.calls_per_minute / 60)
        )
        
        # Wait if no tokens available
        if self.tokens < 1:
            sleep_time = (1 - self.tokens) * (60 / self.calls_per_minute)
            time.sleep(sleep_time)
            self.tokens = 0
        else:
            self.tokens -= 1
        
        self.last_update = time.time()


class HKDailyExtractor:
    """Extractor for Hong Kong Stock daily price data using yfinance."""
    
    def __init__(self):
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        self.rate_limit = config.get("rate_limit", 60)
        self.batch_size = config.get("batch_size", 10)
        self.delay_between_batches = config.get("delay_between_batches", 1.0)
        
        # Initialize rate limiter
        self.rate_limiter = YFinanceRateLimiter(calls_per_minute=self.rate_limit)
        
        logger.info(f"HKDailyExtractor initialized with rate_limit={self.rate_limit}, batch_size={self.batch_size}")
    
    def _map_yfinance_to_tushare(self, df: pd.DataFrame, ts_code: str) -> pd.DataFrame:
        """Map yfinance data format to TuShare format.
        
        Args:
            df: DataFrame from yfinance with columns: Open, High, Low, Close, Volume
            ts_code: TuShare format stock code
        
        Returns:
            DataFrame in TuShare format with columns: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        """
        if df.empty:
            return pd.DataFrame()
        
        # Create result DataFrame
        result = pd.DataFrame()
        
        # Add ts_code
        result['ts_code'] = ts_code
        
        # Convert date index to trade_date
        result['trade_date'] = df.index.strftime('%Y%m%d')
        
        # Map basic fields
        result['open'] = df['Open'].values
        result['high'] = df['High'].values
        result['low'] = df['Low'].values
        result['close'] = df['Close'].values
        result['vol'] = df['Volume'].values
        
        # Calculate pre_close, change, pct_chg
        # pre_close is the close price of the previous trading day
        result['pre_close'] = df['Close'].shift(1).values
        
        # change = close - pre_close
        result['change'] = result['close'] - result['pre_close']
        
        # pct_chg = (close - pre_close) / pre_close * 100
        result['pct_chg'] = (result['change'] / result['pre_close'] * 100).round(2)
        
        # amount is not available from yfinance, set to None
        result['amount'] = None
        
        # Reset index
        result = result.reset_index(drop=True)
        
        # Drop first row (no pre_close)
        result = result.dropna(subset=['pre_close'])
        
        return result
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_yfinance(self, yf_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Call yfinance API with rate limiting and retry.
        
        Args:
            yf_code: yfinance format stock code (e.g., '0700.HK')
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            DataFrame with historical data
        """
        # Apply rate limiting
        self.rate_limiter.acquire()
        
        try:
            logger.info(f"Fetching data for {yf_code} from {start_date} to {end_date}")
            
            # Get ticker
            ticker = yf.Ticker(yf_code)
            
            # Get historical data
            hist = ticker.history(start=start_date, end=end_date, auto_adjust=False)
            
            if hist.empty:
                logger.warning(f"No data returned for {yf_code}")
                return pd.DataFrame()
            
            logger.info(f"Successfully fetched {len(hist)} records for {yf_code}")
            return hist
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limit errors specifically
            if "Rate" in error_msg or "limit" in error_msg.lower() or "Too Many Requests" in error_msg:
                logger.warning(f"Rate limit hit for {yf_code}, waiting 60 seconds before retry...")
                time.sleep(60)  # Wait 60 seconds for rate limit to reset
                raise  # Re-raise to trigger retry
            
            logger.error(f"Failed to fetch data for {yf_code}: {e}")
            raise
    
    def extract(
        self,
        trade_date: Optional[str] = None,
        ts_code: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Extract Hong Kong stock daily data.
        
        Args:
            trade_date: Trade date in YYYYMMDD format (e.g., '20250110')
            ts_code: Stock code in TuShare format (e.g., '00001.HK')
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with HK daily data in TuShare format
        """
        # Convert date formats from YYYYMMDD to YYYY-MM-DD
        if start_date:
            start_date_dt = pd.to_datetime(start_date, format='%Y%m%d')
            start_date_str = start_date_dt.strftime('%Y-%m-%d')
        else:
            # Default: 1 year ago
            start_date_dt = datetime.now() - timedelta(days=365)
            start_date_str = start_date_dt.strftime('%Y-%m-%d')
        
        if end_date:
            end_date_dt = pd.to_datetime(end_date, format='%Y%m%d')
            end_date_str = end_date_dt.strftime('%Y-%m-%d')
        else:
            end_date_str = datetime.now().strftime('%Y-%m-%d')
        
        if ts_code:
            # Single stock
            yf_code = ts_code_to_yf(ts_code)
            hist_data = self._call_yfinance(yf_code, start_date_str, end_date_str)
            
            if hist_data.empty:
                return pd.DataFrame()
            
            return self._map_yfinance_to_tushare(hist_data, ts_code)
        
        elif trade_date:
            # Get all stocks for a specific date (not recommended for yfinance)
            logger.warning("Fetching all stocks for a specific date is not efficient with yfinance. Use start_date/end_date instead.")
            raise ValueError("Use ts_code + start_date/end_date or start_date/end_date for batch mode")
        
        else:
            # Batch mode: will be handled by extract_all_hk_stocks
            raise ValueError("For batch mode, use extract_all_hk_stocks method")
    
    def extract_by_date_range(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Extract Hong Kong stock daily data for a date range.
        
        Args:
            ts_code: Stock code in TuShare format (e.g., '00001.HK')
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with HK daily data in TuShare format
        """
        return self.extract(ts_code=ts_code, start_date=start_date, end_date=end_date)
    
    def extract_all_hk_stocks(
        self,
        start_date: str,
        end_date: str,
        db_client=None,
        batch_size: Optional[int] = None,
        max_stocks: Optional[int] = None,
    ) -> pd.DataFrame:
        """Extract daily data for all HK stocks.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            db_client: Database client for getting stock list
            batch_size: Number of stocks per batch (default from config)
            max_stocks: Maximum number of stocks to process (for testing)
        
        Returns:
            Combined DataFrame with all stocks' daily data
        """
        if db_client is None:
            logger.error("Database client is required for batch extraction")
            raise ValueError("Database client is required")
        
        # Get all HK stock codes from database
        query = "SELECT DISTINCT ts_code FROM ods_hk_basic WHERE list_status = 'L' ORDER BY ts_code"
        stocks_df = db_client.execute_query(query)
        
        if stocks_df.empty:
            logger.warning("No HK stocks found in ods_hk_basic table")
            return pd.DataFrame()
        
        stock_codes = stocks_df['ts_code'].tolist()
        logger.info(f"Found {len(stock_codes)} HK stocks")
        
        # Apply max_stocks limit
        if max_stocks:
            stock_codes = stock_codes[:max_stocks]
            logger.info(f"Limited to {max_stocks} stocks for testing")
        
        # Set batch size
        batch_size = batch_size or self.batch_size
        
        all_data = []
        success_count = 0
        failed_count = 0
        failed_stocks = []
        
        total = len(stock_codes)
        
        # Process in batches
        for i in range(0, total, batch_size):
            batch = stock_codes[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            logger.info(f"Processing batch {batch_num} ({i+1}-{min(i+batch_size, total)}/{total})")
            
            for j, ts_code in enumerate(batch, 1):
                try:
                    logger.info(f"[{i+j}/{total}] Fetching {ts_code}")
                    
                    data = self.extract(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    
                    if not data.empty:
                        all_data.append(data)
                        success_count += 1
                        logger.info(f"[{i+j}/{total}] {ts_code}: {len(data)} records")
                    else:
                        logger.warning(f"[{i+j}/{total}] {ts_code}: No data")
                    
                except Exception as e:
                    failed_count += 1
                    failed_stocks.append(ts_code)
                    logger.error(f"[{i+j}/{total}] {ts_code}: Failed - {e}")
            
            # Delay between batches
            if i + batch_size < total:
                logger.info(f"Waiting {self.delay_between_batches}s before next batch...")
                time.sleep(self.delay_between_batches)
            
            # Progress report
            if (i + batch_size) % (batch_size * 5) == 0 or (i + batch_size) >= total:
                logger.info(f"Progress: {min(i+batch_size, total)}/{total} (success={success_count}, failed={failed_count})")
        
        # Combine all data
        if not all_data:
            logger.warning("No data found for any HK stocks")
            return pd.DataFrame()
        
        combined = pd.concat(all_data, ignore_index=True)
        
        logger.info(f"=" * 80)
        logger.info(f"Batch extraction completed:")
        logger.info(f"  Total stocks: {total}")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"  Total records: {len(combined)}")
        
        if failed_stocks:
            logger.warning(f"Failed stocks: {', '.join(failed_stocks[:10])}" + 
                          (f" ... and {len(failed_stocks)-10} more" if len(failed_stocks) > 10 else ""))
        
        logger.info(f"=" * 80)
        
        return combined


# Global extractor instance
extractor = HKDailyExtractor()
