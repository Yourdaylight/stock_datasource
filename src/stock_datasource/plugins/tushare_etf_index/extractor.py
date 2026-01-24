"""TuShare ETF基准指数列表 extractor."""

import logging
import json
import time
import pandas as pd
from typing import Optional, List
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


class ETFIndexExtractor:
    """Extractor for TuShare ETF基准指数列表."""
    
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
                logger.warning("API returned empty data")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(
        self,
        ts_code: Optional[str] = None,
        pub_date: Optional[str] = None,
        base_date: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Extract ETF基准指数列表.
        
        Args:
            ts_code: 指数代码
            pub_date: 发布日期（格式：YYYYMMDD）
            base_date: 指数基期（格式：YYYYMMDD）
            fields: 返回字段列表
        
        Returns:
            DataFrame with ETF基准指数列表
        """
        if fields is None:
            fields = [
                'ts_code', 'indx_name', 'indx_csname', 'pub_party_name',
                'pub_date', 'base_date', 'bp', 'adj_circle'
            ]
        
        kwargs = {'fields': ','.join(fields)}
        
        if ts_code:
            kwargs['ts_code'] = ts_code
        if pub_date:
            kwargs['pub_date'] = pub_date
        if base_date:
            kwargs['base_date'] = base_date
        
        return self._call_api(self.pro.etf_index, **kwargs)


# Global extractor instance
extractor = ETFIndexExtractor()
