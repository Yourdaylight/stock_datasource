"""TuShare index monthly data extractor."""

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


# Major indices to fetch by default
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


class IndexMonthlyExtractor:
    """Extractor for TuShare index monthly price data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Load config
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)
        self.timeout = config.get("timeout", 30)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")
        
        ts.set_token(self.token)
        try:
            self.pro = ts.pro_api(timeout=self.timeout)
        except TypeError:
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
        """Call TuShare API with rate limiting, retry and proxy."""
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
    
    def extract(
        self,
        ts_code: Optional[str] = None,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Extract index monthly data from TuShare.
        
        Args:
            ts_code: TS index code (e.g., 000001.SH)
            trade_date: Trade date in YYYYMMDD format
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with index monthly data
        """
        kwargs = {}
        if ts_code:
            kwargs['ts_code'] = ts_code
        if trade_date:
            kwargs['trade_date'] = trade_date
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        # If no specific code provided, fetch major indices
        if not ts_code and not trade_date:
            all_data = []
            for idx_code in MAJOR_INDICES:
                idx_kwargs = {**kwargs, 'ts_code': idx_code}
                data = self._call_api(self.pro.index_monthly, **idx_kwargs)
                if not data.empty:
                    all_data.append(data)
            
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            return pd.DataFrame()
        
        return self._call_api(self.pro.index_monthly, **kwargs)
    
    def extract_by_date_range(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Extract index monthly data for a date range.
        
        Args:
            ts_code: Index code
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with index monthly data
        """
        return self._call_api(
            self.pro.index_monthly,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )


# Global extractor instance
extractor = IndexMonthlyExtractor()
