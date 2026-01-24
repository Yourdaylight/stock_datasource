"""TuShare index monthly data extractor - independent implementation."""

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


MAJOR_INDICES = [
    "000001.SH", "399001.SZ", "000300.SH", "000905.SH",
    "000016.SH", "399006.SZ", "000852.SH", "000688.SH",
]


class IndexMonthlyExtractor:
    """Independent extractor for TuShare index monthly price data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
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
            self.pro = ts.pro_api()
        
        self._last_call_time = 0
        self._min_interval = 60.0 / self.rate_limit
    
    def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        if time_since_last < self._min_interval:
            time.sleep(self._min_interval - time_since_last)
        self._last_call_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_api(self, api_func, **kwargs) -> pd.DataFrame:
        self._rate_limit()
        try:
            with proxy_context():
                result = api_func(**kwargs)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, trade_date: str, ts_code: Optional[str] = None) -> pd.DataFrame:
        if ts_code:
            return self._call_api(self.pro.index_monthly, ts_code=ts_code, trade_date=trade_date)
        else:
            all_data = []
            for idx_code in MAJOR_INDICES:
                data = self._call_api(self.pro.index_monthly, ts_code=idx_code, trade_date=trade_date)
                if not data.empty:
                    all_data.append(data)
            return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    
    def extract_by_date_range(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        return self._call_api(self.pro.index_monthly, ts_code=ts_code, start_date=start_date, end_date=end_date)


extractor = IndexMonthlyExtractor()
