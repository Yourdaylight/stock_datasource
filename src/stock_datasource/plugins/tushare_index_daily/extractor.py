"""TuShare index daily data extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from typing import Optional
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


# Major indices to prioritize (from OverviewService)
MAJOR_INDICES = [
    "000001.SH",  # 上证指数
    "399001.SZ",  # 深证成指
    "000300.SH",  # 沪深300
    "000905.SH",  # 中证500
    "000016.SH",  # 上证50
    "399006.SZ",  # 创业板指
    "000852.SH",  # 中证1000
    "000688.SH",  # 科创50
]


class IndexDailyExtractor:
    """Independent extractor for TuShare index daily price data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 500)
        self.timeout = config.get("timeout", 30)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")
        
        ts.set_token(self.token)
        try:
            self.pro = ts.pro_api(timeout=self.timeout)
        except TypeError:
            # Fallback for older tushare versions
            self.pro = ts.pro_api()
            if hasattr(self.pro, "timeout"):
                try:
                    self.pro.timeout = self.timeout
                except Exception:
                    pass
        
        # Rate limiting
        self._last_call_time = 0
        self._min_interval = 60.0 / self.rate_limit
    
    def _rate_limit(self):
        """Apply rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        
        if time_since_last < self._min_interval:
            sleep_time = self._min_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_call_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_api(self, api_func, **kwargs) -> pd.DataFrame:
        """Call TuShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            with proxy_context():
                result = api_func(**kwargs)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for {kwargs}")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, trade_date: str, ts_code: Optional[str] = None) -> pd.DataFrame:
        """Extract index daily data for a specific trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            ts_code: Optional index code (if not provided, gets major indices only)
        
        Returns:
            DataFrame with index daily data (OHLCV)
        """
        if ts_code:
            # Get data for specific index
            kwargs = {'ts_code': ts_code, 'trade_date': trade_date}
            return self._call_api(self.pro.index_daily, **kwargs)
        else:
            # Get data for major indices only (to avoid too many API calls)
            all_data = []
            for idx_code in MAJOR_INDICES:
                kwargs = {'ts_code': idx_code, 'trade_date': trade_date}
                data = self._call_api(self.pro.index_daily, **kwargs)
                if not data.empty:
                    all_data.append(data)
            
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return pd.DataFrame()


# Global extractor instance
extractor = IndexDailyExtractor()
