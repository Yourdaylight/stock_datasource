"""TuShare stk_mins (A股历史分钟行情) data extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from typing import Optional
from pathlib import Path
from datetime import datetime
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class StkMinsExtractor:
    """Independent extractor for TuShare stk_mins (A股历史分钟行情) data."""
    
    # Supported frequencies
    FREQUENCIES = ["1min", "5min", "15min", "30min", "60min"]
    
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
        
        self.fields = [
            "ts_code", "trade_time", "open", "close", "high", "low", "vol", "amount"
        ]
    
    def _rate_limit(self):
        """Apply rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self._last_call_time
        
        if time_since_last < self._min_interval:
            sleep_time = self._min_interval - time_since_last
            time.sleep(sleep_time)
        
        self._last_call_time = time.time()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_api(self, ts_code: str, freq: str, 
                  start_date: Optional[str] = None, 
                  end_date: Optional[str] = None) -> pd.DataFrame:
        """Call TuShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            params = {
                "ts_code": ts_code,
                "freq": freq
            }
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date
            
            result = self.pro.stk_mins(**params)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for {ts_code} {freq}")
                return pd.DataFrame()
            
            logger.info(f"API call successful for {ts_code} {freq}, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed for {ts_code} {freq}: {e}")
            raise
    
    def _process_data(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """Process extracted data."""
        if df.empty:
            return df
        
        # Add freq column
        df["freq"] = freq
        
        # Convert trade_time to datetime
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
        
        # Reorder columns
        col_order = ["ts_code", "freq", "trade_time", "open", "close", "high", "low", "vol", "amount"]
        existing_cols = [c for c in col_order if c in df.columns]
        df = df[existing_cols]
        
        return df
    
    def extract(
        self,
        ts_code: str,
        freq: str = "1min",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Extract minute-level historical data.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            freq: Frequency (1min/5min/15min/30min/60min)
            start_date: Start datetime (e.g., '2023-08-25 09:00:00')
            end_date: End datetime (e.g., '2023-08-25 15:00:00')
            
        Returns:
            DataFrame with minute K-line data
        """
        if freq not in self.FREQUENCIES:
            raise ValueError(f"Invalid freq: {freq}. Valid: {self.FREQUENCIES}")
        
        logger.info(f"Extracting stk_mins data for {ts_code} {freq}")
        
        df = self._call_api(ts_code, freq, start_date, end_date)
        
        if not df.empty:
            df = self._process_data(df, freq)
            logger.info(f"Extracted {len(df)} records")
        else:
            logger.warning("No data extracted")
            
        return df
    
    def extract_multiple_stocks(
        self,
        ts_codes: list,
        freq: str = "1min",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """Extract minute data for multiple stocks.
        
        Args:
            ts_codes: List of stock codes
            freq: Frequency
            start_date: Start datetime
            end_date: End datetime
            
        Returns:
            DataFrame with all stocks data
        """
        all_data = []
        
        for ts_code in ts_codes:
            try:
                df = self.extract(ts_code, freq, start_date, end_date)
                if not df.empty:
                    all_data.append(df)
            except Exception as e:
                logger.error(f"Failed to extract {ts_code}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame()


# Global extractor instance
extractor = StkMinsExtractor()
