"""TuShare HK cash flow statement data extractor."""

import logging
import json
import time
import pandas as pd
from typing import Optional
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class HKCashflowExtractor:
    """Extractor for TuShare HK cash flow statement data (EAV model)."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        
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
    def _call_api(self, **kwargs) -> pd.DataFrame:
        """Call TuShare HK cashflow API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            result = self.pro.hk_cashflow(**kwargs)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for params: {kwargs}")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, ts_code: str, period: Optional[str] = None,
                report_type: Optional[str] = None,
                start_date: Optional[str] = None,
                end_date: Optional[str] = None) -> pd.DataFrame:
        """Extract HK cash flow statement data.
        
        Args:
            ts_code: HK stock code (required, e.g., 00700.HK)
            period: Report period (e.g., 20241231)
            report_type: Report type (Q1/Q2/Q3/Q4)
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with HK cash flow data (EAV: ts_code, end_date, ind_name, ind_value)
        """
        kwargs = {'ts_code': ts_code}
        
        if period:
            kwargs['period'] = period
        if report_type:
            kwargs['report_type'] = report_type
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        return self._call_api(**kwargs)


# Global extractor instance
extractor = HKCashflowExtractor()
