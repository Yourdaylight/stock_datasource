"""TuShare rt_min (A股实时分钟K线) data extractor."""

import logging
import json
import time
import threading
import pandas as pd
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings
from stock_datasource.core.proxy import proxy_context

logger = logging.getLogger(__name__)


# Valid frequency values
VALID_FREQS = ["1MIN", "5MIN", "15MIN", "30MIN", "60MIN"]


class RtMinExtractor:
    """Extractor for TuShare rt_min (A股实时分钟K线) data."""
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.rate_limit_val = config.get("rate_limit", 120)
        
        if not self.token:
            raise ValueError("TUSHARE_TOKEN not configured in settings")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        
        # Rate limiting
        self._last_call_time = 0
        self.rate_limit_val = min(self.rate_limit_val, 48)
        self._min_interval = 60.0 / self.rate_limit_val
        self._rate_lock = threading.Lock()
        
        self.fields = [
            "ts_code", "time", "open", "close", "high", "low", "vol", "amount"
        ]
    
    def _apply_rate_limit(self):
        """Apply thread-safe rate limiting."""
        with self._rate_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_call_time
            if time_since_last < self._min_interval:
                sleep_time = self._min_interval - time_since_last
                time.sleep(sleep_time)
            self._last_call_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, ts_code: str, freq: str) -> pd.DataFrame:
        """Call TuShare rt_min API with rate limiting and retry.
        
        Args:
            ts_code: Stock code(s), comma-separated for multiple
            freq: K-line frequency (1MIN/5MIN/15MIN/30MIN/60MIN)
        """
        self._apply_rate_limit()
        
        try:
            with proxy_context():
                result = self.pro.rt_min(ts_code=ts_code, freq=freq)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for ts_code={ts_code}, freq={freq}")
                return pd.DataFrame()
            
            logger.info(f"API call successful: ts_code={ts_code}, freq={freq}, records={len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: ts_code={ts_code}, freq={freq}, error={e}")
            raise
    
    def _process_data(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """Process extracted data."""
        if df.empty:
            return df
        
        # Rename 'time' column to 'trade_time' for ClickHouse
        if "time" in df.columns:
            df = df.rename(columns={"time": "trade_time"})
        
        # Convert trade_time to datetime
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
            df["trade_time"] = df["trade_time"].fillna(datetime.now())
        else:
            df["trade_time"] = datetime.now()
        
        # Add freq column
        df["freq"] = freq
        
        # Convert numeric columns
        numeric_cols = ["open", "close", "high", "low", "vol", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        
        return df
    
    def extract(self, ts_code: str, freq: str = "1MIN") -> pd.DataFrame:
        """Extract realtime minute K-line data for A-share stocks.
        
        Args:
            ts_code: Stock code(s), supports comma-separated (e.g., '600000.SH,000001.SZ')
            freq: K-line frequency (1MIN/5MIN/15MIN/30MIN/60MIN)
            
        Returns:
            DataFrame with minute K-line data
        """
        freq = freq.upper()
        if freq not in VALID_FREQS:
            raise ValueError(f"Invalid freq: {freq}. Valid: {VALID_FREQS}")
        
        logger.info(f"Extracting rt_min: ts_code={ts_code}, freq={freq}")
        
        df = self._call_api(ts_code, freq)
        
        if not df.empty:
            df = self._process_data(df, freq)
            logger.info(f"Extracted {len(df)} minute records")
        else:
            logger.warning("No minute data extracted")
            
        return df
    
    def extract_batch(self, ts_codes: List[str], freq: str = "1MIN", batch_size: int = 10) -> pd.DataFrame:
        """Extract minute data for multiple stocks in batches.
        
        Tushare rt_min supports comma-separated codes (max ~10 per call for 1000 row limit).
        
        Args:
            ts_codes: List of stock codes
            freq: K-line frequency
            batch_size: Number of codes per API call
            
        Returns:
            Combined DataFrame
        """
        all_data = []
        
        for i in range(0, len(ts_codes), batch_size):
            batch = ts_codes[i:i + batch_size]
            codes_str = ",".join(batch)
            
            try:
                df = self.extract(codes_str, freq)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.error(f"Failed to extract batch {i//batch_size}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()
