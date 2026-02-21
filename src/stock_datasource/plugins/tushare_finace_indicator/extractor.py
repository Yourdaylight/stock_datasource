"""TuShare financial indicators data extractor."""

import logging
import json
import time
import pandas as pd
from typing import Optional
from pathlib import Path
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class FinaIndicatorExtractor:
    """Extractor for TuShare financial indicators data."""
    
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
            result = api_func(**kwargs)
            if result is None or result.empty:
                logger.warning(f"API returned empty data")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    # TuShare fina_indicator 字段名 → schema 字段名的映射
    # TuShare 实际返回 grossprofit_margin / netprofit_margin（无下划线），
    # 而 schema 定义为 gross_profit_margin / net_profit_margin
    FIELD_RENAME_MAP = {
        'grossprofit_margin': 'gross_profit_margin',
        'netprofit_margin': 'net_profit_margin',
        'debt_to_eqt': 'debt_to_equity',
        'assets_turn': 'asset_turnover',
        'inv_turn': 'inventory_turnover',
        'ar_turn': 'receivable_turnover',
    }

    # 需要从 TuShare fina_indicator 获取的字段列表
    # 注意：只包含 schema.json 中定义的字段，多余字段会导致 INSERT 失败
    EXTRACT_FIELDS = ','.join([
        'ts_code', 'ann_date', 'end_date',
        'roe', 'roa',
        'grossprofit_margin', 'netprofit_margin',  # TuShare 实际字段名，rename 后对应 schema
        'eps', 'bps',
        'current_ratio', 'quick_ratio',
        'debt_to_assets', 'debt_to_eqt',  # TuShare 字段名，rename 后对应 schema
        'assets_turn', 'inv_turn', 'ar_turn',  # TuShare 字段名，rename 后对应 schema
    ])

    def extract(self, ts_code: Optional[str] = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Extract financial indicators data.
        
        Args:
            ts_code: Stock code (e.g., 002579.SZ). If not provided, gets all stocks
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
        
        Returns:
            DataFrame with financial indicators data
        """
        kwargs = {'fields': self.EXTRACT_FIELDS}
        if ts_code:
            kwargs['ts_code'] = ts_code
        if start_date:
            kwargs['start_date'] = start_date
        if end_date:
            kwargs['end_date'] = end_date
        
        df = self._call_api(self.pro.fina_indicator, **kwargs)
        
        # Rename TuShare field names to match our schema
        if not df.empty:
            rename_cols = {k: v for k, v in self.FIELD_RENAME_MAP.items() if k in df.columns}
            if rename_cols:
                df = df.rename(columns=rename_cols)
        
        return df


# Global extractor instance
extractor = FinaIndicatorExtractor()