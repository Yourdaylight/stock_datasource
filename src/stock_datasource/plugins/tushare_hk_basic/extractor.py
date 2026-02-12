"""TuShare Hong Kong Stock Basic Info extractor."""

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


class HKBasicExtractor:
    """Extractor for TuShare Hong Kong Stock basic info data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        
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
                logger.warning(f"API returned empty data for params: {kwargs}")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(
        self,
        ts_code: Optional[str] = None,
        list_status: Optional[str] = None,
    ) -> pd.DataFrame:
        """Extract Hong Kong Stock basic info data.
        
        Args:
            ts_code: TS code (e.g., '00001.HK')
            list_status: Listing status (L=Listed, D=Delisted, P=Paused)
        
        Returns:
            DataFrame with HK stock basic info
        """
        kwargs = {}
        
        if ts_code:
            kwargs['ts_code'] = ts_code
        if list_status:
            kwargs['list_status'] = list_status
        
        return self._call_api(self.pro.hk_basic, **kwargs)
    
    def extract_all(self) -> pd.DataFrame:
        """Extract all Hong Kong stocks (listed, delisted, paused).
        
        Returns:
            DataFrame with all HK stocks
        """
        all_data = []
        
        for status in ['L', 'D', 'P']:
            data = self.extract(list_status=status)
            if not data.empty:
                all_data.append(data)
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()


# Global extractor instance
extractor = HKBasicExtractor()
