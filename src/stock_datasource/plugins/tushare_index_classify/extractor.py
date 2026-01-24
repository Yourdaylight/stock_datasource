"""TuShare index classify data extractor."""

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


class IndexClassifyExtractor:
    """Extractor for TuShare index classify data (申万行业分类)."""
    
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
                result = self.pro.index_classify(**kwargs)
            return result if result is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def extract(self, level: Optional[str] = None, src: str = 'SW2021') -> pd.DataFrame:
        """Extract industry classification.
        
        Args:
            level: L1/L2/L3 for different levels, None for all
            src: SW2021 (申万2021版), SW (申万旧版), MSCI, etc.
        """
        kwargs = {'src': src}
        if level:
            kwargs['level'] = level
        return self._call_api(**kwargs)
    
    def extract_all_levels(self, src: str = 'SW2021') -> pd.DataFrame:
        """Extract all industry classification levels."""
        all_data = []
        for level in ['L1', 'L2', 'L3']:
            data = self.extract(level=level, src=src)
            if not data.empty:
                all_data.append(data)
        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


extractor = IndexClassifyExtractor()
