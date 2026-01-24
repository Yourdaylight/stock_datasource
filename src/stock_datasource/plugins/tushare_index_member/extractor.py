"""TuShare index member data extractor."""

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


class IndexMemberExtractor:
    """Extractor for TuShare index member data (指数成分股)."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 500)
        self.timeout = config.get("timeout", 30)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured")
        
        ts.set_token(self.token)
        try:
            self.pro = ts.pro_api(timeout=self.timeout)
        except TypeError:
            self.pro = ts.pro_api()
        
        self._last_call_time = 0
        self._min_interval = 60.0 / self.rate_limit
    
    def _rate_limit(self):
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        if time_since_last < self._min_interval:
            time.sleep(self._min_interval - time_since_last)
        self._last_call_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _call_api(self, **kwargs) -> pd.DataFrame:
        self._rate_limit()
        try:
            with proxy_context():
                result = self.pro.index_member(**kwargs)
            return result if result is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, index_code: str, is_new: Optional[str] = None) -> pd.DataFrame:
        """Extract index members.
        
        Args:
            index_code: Index code (e.g., 000300.SH)
            is_new: Y for current members only, N for historical
        """
        kwargs = {'index_code': index_code}
        if is_new:
            kwargs['is_new'] = is_new
        return self._call_api(**kwargs)


extractor = IndexMemberExtractor()
