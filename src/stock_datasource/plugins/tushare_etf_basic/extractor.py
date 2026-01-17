"""TuShare ETF basic information extractor."""

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


class ETFBasicExtractor:
    """Extractor for TuShare ETF basic information."""
    
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
        list_status: Optional[str] = None,
        exchange: Optional[str] = None,
        ts_code: Optional[str] = None,
        index_code: Optional[str] = None,
        mgr: Optional[str] = None,
        fields: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Extract ETF basic information.
        
        Args:
            list_status: 上市状态 L上市 D退市 P待上市
            exchange: 交易所 SH/SZ
            ts_code: ETF代码
            index_code: 跟踪指数代码
            mgr: 管理人简称
            fields: 返回字段列表
        
        Returns:
            DataFrame with ETF basic information
        """
        if fields is None:
            fields = [
                'ts_code', 'csname', 'extname', 'cname', 'index_code', 'index_name',
                'setup_date', 'list_date', 'list_status', 'exchange', 'mgr_name',
                'custod_name', 'mgt_fee', 'etf_type'
            ]
        
        kwargs = {'fields': ','.join(fields)}
        
        if list_status:
            kwargs['list_status'] = list_status
        if exchange:
            kwargs['exchange'] = exchange
        if ts_code:
            kwargs['ts_code'] = ts_code
        if index_code:
            kwargs['index_code'] = index_code
        if mgr:
            kwargs['mgr'] = mgr
        
        return self._call_api(self.pro.etf_basic, **kwargs)


# Global extractor instance
extractor = ETFBasicExtractor()
