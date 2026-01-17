"""TuShare THS daily data extractor - independent implementation."""

import json
import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


class THSDailyExtractor:
    """Independent extractor for TuShare THS sector index daily data."""

    def __init__(self):
        self.token = settings.TUSHARE_TOKEN

        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.rate_limit = config.get("rate_limit", 120)
        self.timeout = config.get("timeout", 30)
        self.retry_attempts = config.get("retry_attempts", 3)

        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")

        ts.set_token(self.token)
        try:
            self.pro = ts.pro_api(timeout=self.timeout)
        except TypeError:
            self.pro = ts.pro_api()
            if hasattr(self.pro, "timeout"):
                try:
                    self.pro.timeout = self.timeout
                except Exception:
                    pass

        self._last_call_time = 0
        self._min_interval = 60.0 / self.rate_limit

    def _rate_limit(self):
        """Apply rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        if time_since_last < self._min_interval:
            time.sleep(self._min_interval - time_since_last)
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

    def extract(
        self,
        trade_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ts_code: Optional[str] = None,
        fields: Optional[str] = None,
    ) -> pd.DataFrame:
        """Extract THS daily data.

        Args:
            trade_date: Trade date in YYYYMMDD format
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            ts_code: Optional THS index code
            fields: Optional fields string

        Returns:
            DataFrame with THS daily data
        """
        kwargs = {}
        if trade_date:
            kwargs["trade_date"] = trade_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        if ts_code:
            kwargs["ts_code"] = ts_code
        if fields:
            kwargs["fields"] = fields

        return self._call_api(self.pro.ths_daily, **kwargs)


extractor = THSDailyExtractor()
