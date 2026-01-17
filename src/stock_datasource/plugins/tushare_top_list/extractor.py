"""TuShare top list data extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from typing import Optional, Dict, Any
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


class TopListExtractor:
    """Independent extractor for TuShare top list (龙虎榜) data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)  # Default to 120 if not specified
        
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
                logger.warning(f"API returned empty data for {kwargs}")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract_top_list(self, trade_date: str, ts_code: Optional[str] = None) -> pd.DataFrame:
        """Extract top list data for a specific trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            ts_code: Optional stock code (if not provided, gets all stocks)
        
        Returns:
            DataFrame with top list data
        """
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
        
        logger.info(f"Extracting top list data for {trade_date}")
        return self._call_api(self.pro.top_list, **kwargs)
    
    def extract_top_inst(self, trade_date: str, ts_code: Optional[str] = None) -> pd.DataFrame:
        """Extract institutional seats data for a specific trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format  
            ts_code: Optional stock code (if not provided, gets all stocks)
        
        Returns:
            DataFrame with institutional seats data
        """
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
        
        logger.info(f"Extracting institutional seats data for {trade_date}")
        return self._call_api(self.pro.top_inst, **kwargs)
    
    def extract_batch_data(self, start_date: str, end_date: str) -> Dict[str, pd.DataFrame]:
        """Batch extract historical data for a date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            Dictionary containing 'top_list' and 'top_inst' DataFrames
        """
        results = {'top_list': pd.DataFrame(), 'top_inst': pd.DataFrame()}
        
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        for date in date_range:
            trade_date = date.strftime('%Y%m%d')
            logger.info(f"Processing batch data for {trade_date}")
            
            try:
                # 获取龙虎榜数据
                top_list_df = self.extract_top_list(trade_date)
                if not top_list_df.empty:
                    results['top_list'] = pd.concat([results['top_list'], top_list_df], ignore_index=True)
                
                # 获取机构席位数据
                top_inst_df = self.extract_top_inst(trade_date)
                if not top_inst_df.empty:
                    results['top_inst'] = pd.concat([results['top_inst'], top_inst_df], ignore_index=True)
                
                # Additional rate limiting for batch operations
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Failed to extract data for {trade_date}: {e}")
                continue
        
        logger.info(f"Batch extraction completed. Top list records: {len(results['top_list'])}, "
                   f"Institution records: {len(results['top_inst'])}")
        
        return results


# Global extractor instance
extractor = TopListExtractor()