"""AKShare Hong Kong daily data extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from pathlib import Path
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class HKDailyExtractor:
    """Independent extractor for AKShare Hong Kong daily data."""
    
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
    def _call_api(self, symbol: str, start_date: Optional[str] = None, 
                  end_date: Optional[str] = None) -> pd.DataFrame:
        """Call AKShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            import akshare as ak
            
            # Build parameters - convert YYYYMMDD to YYYY-MM-DD format if needed
            kwargs = {'symbol': symbol, 'period': 'daily'}
            if start_date:
                # Convert YYYYMMDD to YYYY-MM-DD
                if len(start_date) == 8:
                    start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
                kwargs['start_date'] = start_date
            if end_date:
                # Convert YYYYMMDD to YYYY-MM-DD
                if len(end_date) == 8:
                    end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
                kwargs['end_date'] = end_date
            
            result = ak.stock_hk_hist(**kwargs)
            
            if result is None or result.empty:
                logger.warning(f"API returned empty data for symbol {symbol}")
                return pd.DataFrame()
            
            logger.info(f"API call successful for {symbol}, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed for {symbol}: {e}")
            raise
    
    def extract(self, symbol: str, start_date: Optional[str] = None, 
                end_date: Optional[str] = None) -> pd.DataFrame:
        """Extract Hong Kong daily data.
        
        Args:
            symbol: Hong Kong stock symbol (e.g., 00700)
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
        
        Returns:
            DataFrame with Hong Kong daily data
        """
        return self._call_api(symbol, start_date, end_date)


# Global extractor instance
extractor = HKDailyExtractor()
