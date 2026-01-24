"""TuShare stock company data extractor - independent implementation."""

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


class StockCompanyExtractor:
    """Independent extractor for TuShare stock company data."""
    
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
            "ts_code", "com_name", "com_id", "exchange", "chairman",
            "manager", "secretary", "reg_capital", "setup_date",
            "province", "city", "introduction", "website", "email",
            "office", "employees", "main_business", "business_scope"
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
    def _call_api(self, **kwargs) -> pd.DataFrame:
        """Call TuShare API with rate limiting and retry."""
        self._rate_limit()
        
        try:
            result = self.pro.stock_company(**kwargs, fields=",".join(self.fields))
            if result is None or result.empty:
                logger.warning("API returned empty data")
                return pd.DataFrame()
            
            logger.info(f"API call successful, records: {len(result)}")
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            raise
    
    def _process_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process extracted data."""
        if df.empty:
            return df
        
        # Convert setup_date to date format
        if "setup_date" in df.columns:
            df["setup_date"] = pd.to_datetime(df["setup_date"], format="%Y%m%d", errors="coerce")
        
        # Fill NaN string columns with empty string
        string_cols = ["com_name", "com_id", "chairman", "manager", "secretary",
                      "province", "city", "introduction", "website", "email",
                      "office", "main_business", "business_scope"]
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].fillna("")
        
        return df
    
    def extract(
        self,
        ts_code: Optional[str] = None,
        exchange: Optional[str] = None
    ) -> pd.DataFrame:
        """Extract stock company data.
        
        Args:
            ts_code: Stock code (e.g., 000001.SZ)
            exchange: Exchange code (SSE/SZSE/BSE)
            
        Returns:
            DataFrame with company data
        """
        params = {}
        if ts_code:
            params["ts_code"] = ts_code
        if exchange:
            params["exchange"] = exchange
            
        logger.info(f"Extracting stock company data with params: {params}")
        
        df = self._call_api(**params)
        
        if not df.empty:
            df = self._process_data(df)
            logger.info(f"Extracted {len(df)} company records")
        else:
            logger.warning("No data extracted")
            
        return df
    
    def extract_all(self) -> pd.DataFrame:
        """Extract all stock company data by exchange.
        
        Returns:
            DataFrame with all company data
        """
        all_data = []
        exchanges = ["SSE", "SZSE", "BSE"]
        
        for exchange in exchanges:
            try:
                df = self.extract(exchange=exchange)
                if not df.empty:
                    all_data.append(df)
                    logger.info(f"Extracted {len(df)} records from {exchange}")
            except Exception as e:
                logger.error(f"Failed to extract {exchange}: {e}")
                
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        return pd.DataFrame(columns=self.fields)


# Global extractor instance
extractor = StockCompanyExtractor()
