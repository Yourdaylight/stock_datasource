"""TuShare institutional survey data extractor."""

import logging
import json
import time
import pandas as pd
from typing import Optional
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import apply_proxy_settings

logger = logging.getLogger(__name__)


class StkSurvExtractor:
    """Extractor for TuShare institutional survey (机构调研) data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Apply proxy settings before making any API calls
        apply_proxy_settings()
        
        # Load config
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 60)
        self.batch_size = config.get("batch_size", 100)
        
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
        """Call TuShare stk_surv API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            result = self.pro.stk_surv(**kwargs)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for {kwargs}")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract_by_date(self, trade_date: str) -> pd.DataFrame:
        """Extract institutional survey data for a specific date.
        
        Args:
            trade_date: Date in YYYYMMDD format
        
        Returns:
            DataFrame with survey data
        """
        logger.info(f"Extracting institutional survey data for {trade_date}")
        
        all_data = []
        offset = 0
        
        while True:
            data = self._call_api(
                trade_date=trade_date,
                limit=self.batch_size,
                offset=offset
            )
            
            if data.empty:
                break
            
            all_data.append(data)
            
            if len(data) < self.batch_size:
                break
            
            offset += self.batch_size
            time.sleep(0.1)  # Additional delay between pages
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total records extracted for {trade_date}: {len(result)}")
            return result
        
        return pd.DataFrame()
    
    def extract_by_stock(self, ts_code: str, start_date: Optional[str] = None, 
                         end_date: Optional[str] = None) -> pd.DataFrame:
        """Extract institutional survey data for a specific stock.
        
        Args:
            ts_code: Stock code (e.g., '000001.SZ')
            start_date: Optional start date in YYYYMMDD format
            end_date: Optional end date in YYYYMMDD format
        
        Returns:
            DataFrame with survey data
        """
        logger.info(f"Extracting institutional survey data for {ts_code}")
        
        kwargs = {'ts_code': ts_code}
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        all_data = []
        offset = 0
        
        while True:
            data = self._call_api(
                **kwargs,
                limit=self.batch_size,
                offset=offset
            )
            
            if data.empty:
                break
            
            all_data.append(data)
            
            if len(data) < self.batch_size:
                break
            
            offset += self.batch_size
            time.sleep(0.1)
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total records extracted for {ts_code}: {len(result)}")
            return result
        
        return pd.DataFrame()
    
    def extract_date_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Extract institutional survey data for a date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with survey data
        """
        logger.info(f"Extracting institutional survey data from {start_date} to {end_date}")
        
        all_data = []
        offset = 0
        
        while True:
            data = self._call_api(
                start_date=start_date,
                end_date=end_date,
                limit=self.batch_size,
                offset=offset
            )
            
            if data.empty:
                break
            
            all_data.append(data)
            
            if len(data) < self.batch_size:
                break
            
            offset += self.batch_size
            time.sleep(0.1)
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total records extracted: {len(result)}")
            return result
        
        return pd.DataFrame()


# Global extractor instance
extractor = StkSurvExtractor()
