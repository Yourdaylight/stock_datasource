"""Tushare 业绩快报数据提取器"""

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


class TuShareExpressExtractor:
    """业绩快报数据提取器"""

    def __init__(self):
        self.token = settings.TUSHARE_TOKEN

        # Load rate_limit from config.json
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        rate_limit_config = config.get("rate_limit", 120)
        # rate_limit can be either a number or an object with calls_per_minute
        if isinstance(rate_limit_config, dict):
            self.rate_limit = rate_limit_config.get("calls_per_minute", 120)
        else:
            self.rate_limit = rate_limit_config

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
                logger.warning("API returned empty data")
                return pd.DataFrame()

            logger.info(f"API call successful, records: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise

    def extract(
        self,
        ts_code: str,
        ann_date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        提取业绩快报数据

        Args:
            ts_code: 股票代码
            ann_date: 公告日期
            start_date: 公告开始日期
            end_date: 公告结束日期
            period: 报告期

        Returns:
            业绩快报数据DataFrame
        """
        kwargs = {"ts_code": ts_code}

        if ann_date:
            kwargs["ann_date"] = ann_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        if period:
            kwargs["period"] = period

        return self._call_api(self.pro.express, **kwargs)


# Global extractor instance
extractor = TuShareExpressExtractor()
