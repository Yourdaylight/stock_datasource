"""AKShare Hong Kong stock list extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class HKStockListExtractor:
    """Independent extractor for AKShare Hong Kong stock list."""
    
    def __init__(self):
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 60)  # Default to 60 if not specified
        
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
    def _call_api(self) -> pd.DataFrame:
        """Call AKShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            import akshare as ak
            result = ak.stock_hk_spot_em()
            
            if result is None or result.empty:
                logger.warning(f"API returned empty data")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self) -> pd.DataFrame:
        """Extract Hong Kong stock list.
        
        Returns:
            DataFrame with Hong Kong stock list data
        """
        return self._call_api()


# Global extractor instance
extractor = HKStockListExtractor()
