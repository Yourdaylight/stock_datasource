"""TuShare stock basic information extractor - independent implementation."""

import logging
import os
import json
import time
import pandas as pd
from typing import Optional, List
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class StockBasicExtractor:
    """Independent extractor for TuShare stock basic information."""
    
    def __init__(self):
        self.token = os.getenv("TUSHARE_TOKEN")
        
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 500)  # Default to 500 if not specified
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN environment variable not set")
        
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
            result = api_func(**kwargs)
            if result is None or result.empty:
                logger.warning(f"API returned empty data")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, list_status: str = "L", 
                fields: Optional[List[str]] = None) -> pd.DataFrame:
        """Extract stock basic information.
        
        Args:
            list_status: List status ('L' for listed, 'D' for delisted, 'P' for paused)
            fields: Optional list of fields to retrieve
        
        Returns:
            DataFrame with stock basic information
        """
        if fields is None:
            fields = [
                'ts_code', 'symbol', 'name', 'area', 'industry',
                'list_date', 'delist_date', 'list_status'
            ]
        
        return self._call_api(
            self.pro.stock_basic,
            list_status=list_status,
            fields=','.join(fields)
        )


# Global extractor instance
extractor = StockBasicExtractor()
