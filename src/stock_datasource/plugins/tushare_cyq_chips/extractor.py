"""TuShare cyq_chips (筹码分布) data extractor."""

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


class CyqChipsExtractor:
    """Extractor for TuShare cyq_chips (筹码分布) data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)
        self.max_records = config.get("parameters", {}).get("max_records_per_request", 2000)
        
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
    def _call_api(self, **kwargs) -> pd.DataFrame:
        """Call TuShare cyq_chips API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            with proxy_context():
                result = self.pro.cyq_chips(**kwargs)
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
        ts_code: str, 
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Extract cyq_chips data for a specific stock.
        
        Args:
            ts_code: Stock code (required, e.g., 600000.SH)
            trade_date: Trade date in YYYYMMDD format (optional)
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
        
        Returns:
            DataFrame with cyq_chips data
        """
        kwargs = {'ts_code': ts_code}
        
        if trade_date:
            kwargs['trade_date'] = trade_date
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        return self._call_api(**kwargs)


# Global extractor instance
extractor = CyqChipsExtractor()
