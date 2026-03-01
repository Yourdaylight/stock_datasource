"""TuShare rt_idx_k extractor."""

import json
import logging
import time
import threading
from pathlib import Path

import pandas as pd
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


class RtIdxKExtractor:
    API_NAME = "rt_idx_k"

    def __init__(self):
        token = settings.TUSHARE_TOKEN
        if not token:
            raise ValueError("TUSHARE_TOKEN not configured")
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        self.rate_limit = min(config.get("rate_limit", 120), 48)
        self._min_interval = 60.0 / self.rate_limit
        self._last_call_time = 0.0
        self._rate_lock = threading.Lock()
        ts.set_token(token)
        self.pro = ts.pro_api()

    def _rate_limit(self):
        with self._rate_lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call_time = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def extract(self, ts_code: str, fields: str | None = None) -> pd.DataFrame:
        self._rate_limit()
        try:
            fn = getattr(self.pro, self.API_NAME)
            params = {"ts_code": ts_code}
            if fields:
                params["fields"] = fields
            with proxy_context():
                result = fn(**params)
            if result is None or result.empty:
                return pd.DataFrame()
            return result
        except Exception as e:
            logger.error("%s failed for %s (fields=%s): %s", self.API_NAME, ts_code, fields, e)
            raise


extractor = RtIdxKExtractor()
