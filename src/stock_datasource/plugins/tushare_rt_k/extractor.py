"""TuShare rt_k (realtime daily K-line) data extractor - independent implementation."""

import logging
import json
import time
import pandas as pd
from typing import Optional, List
from pathlib import Path
from datetime import datetime
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class RtKExtractor:
    """Independent extractor for TuShare rt_k (realtime daily K-line) data."""
    
    # Market code patterns
    MARKET_PATTERNS = {
        "SH_MAIN": "6*.SH",      # 沪市主板
        "SH_KCB": "68*.SH",      # 科创板
        "SZ_MAIN": "0*.SZ",      # 深市主板
        "SZ_CYB": "3*.SZ",       # 创业板
        "BJ": "*.BJ",            # 北交所
    }
    
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
            "ts_code", "name", "pre_close", "high", "open", "low", "close",
            "vol", "amount", "num", "ask_price1", "ask_volume1",
            "bid_price1", "bid_volume1", "trade_time"
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
    def _call_api(self, ts_code: str) -> pd.DataFrame:
        """Call TuShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            result = self.pro.rt_k(ts_code=ts_code)
            if result is None or result.empty:
                logger.warning(f"API returned empty data for {ts_code}")
                return pd.DataFrame()
            
            logger.info(f"API call successful for {ts_code}, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed for {ts_code}: {e}")
            raise
    
    def _process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process extracted data."""
        if df.empty:
            return df
        
        # Convert trade_time to datetime
        if "trade_time" in df.columns:
            df["trade_time"] = pd.to_datetime(df["trade_time"], errors="coerce")
            # If trade_time is NaT, use current time
            df["trade_time"] = df["trade_time"].fillna(datetime.now())
        else:
            df["trade_time"] = datetime.now()
        
        # Fill NaN for name
        if "name" in df.columns:
            df["name"] = df["name"].fillna("")
        
        return df
    
    def extract(self, ts_code: str) -> pd.DataFrame:
        """Extract realtime K-line data.
        
        Args:
            ts_code: Stock code or pattern (e.g., '600000.SH', '3*.SZ')
            
        Returns:
            DataFrame with realtime K-line data
        """
        logger.info(f"Extracting rt_k data for: {ts_code}")
        
        df = self._call_api(ts_code)
        
        if not df.empty:
            df = self._process_data(df)
            logger.info(f"Extracted {len(df)} records")
        else:
            logger.warning("No data extracted")
            
        return df
    
    def extract_by_market(self, market: str) -> pd.DataFrame:
        """Extract realtime K-line data by market.
        
        Args:
            market: Market key (SH_MAIN/SH_KCB/SZ_MAIN/SZ_CYB/BJ)
            
        Returns:
            DataFrame with realtime K-line data
        """
        pattern = self.MARKET_PATTERNS.get(market)
        if not pattern:
            raise ValueError(f"Unknown market: {market}. Valid: {list(self.MARKET_PATTERNS.keys())}")
        
        return self.extract(pattern)
    
    def extract_all_markets(self) -> pd.DataFrame:
        """Extract realtime K-line data for all markets.
        
        Note: This makes multiple API calls. Consider using batched extraction.
        
        Returns:
            DataFrame with all market data
        """
        all_data = []
        
        for market, pattern in self.MARKET_PATTERNS.items():
            try:
                df = self.extract(pattern)
                if not df.empty:
                    all_data.append(df)
                    logger.info(f"Extracted {len(df)} records from {market}")
            except Exception as e:
                logger.error(f"Failed to extract {market}: {e}")
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame(columns=self.fields)


# Global extractor instance
extractor = RtKExtractor()
