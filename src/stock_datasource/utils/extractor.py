"""Base TuShare data extractor with rate limiting and retry logic.

This module provides the base extractor class for TuShare API calls.
Specific API implementations should be in individual plugin extractors.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import pandas as pd
import tushare as ts
from tenacity import retry, stop_after_attempt, wait_exponential

from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class BaseTuShareExtractor:
    """Base TuShare data extractor with rate limiting and error handling.
    
    This class provides common functionality for TuShare API calls.
    Individual plugins should create their own extractors inheriting from this class.
    """
    
    def __init__(self):
        self.token = settings.TUSHARE_TOKEN
        self.rate_limit = settings.TUSHARE_RATE_LIMIT
        self.max_retries = settings.TUSHARE_MAX_RETRIES
        
        if not self.token:
            raise ValueError("TuShare token not configured")
        
        ts.set_token(self.token)
        self.pro = ts.pro_api()
        
        # Rate limiting
        self._last_call_time = 0
        self._min_interval = 60.0 / self.rate_limit  # seconds between calls
    
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
                api_name = getattr(api_func, '__name__', str(api_func))
                logger.warning(f"API returned empty data for {api_name}")
                return pd.DataFrame()
            
            api_name = getattr(api_func, '__name__', str(api_func))
            logger.info(f"API call successful: {api_name}, records: {len(result)}")
            return result
            
        except Exception as e:
            api_name = getattr(api_func, '__name__', str(api_func))
            logger.error(f"API call failed: {api_name}, error: {e}")
            raise


class TuShareExtractor(BaseTuShareExtractor):
    """Legacy TuShare extractor for backward compatibility.
    
    DEPRECATED: This class is kept for backward compatibility only.
    New code should use individual plugin extractors instead.
    """
    
    def get_trade_calendar(self, start_date: str, end_date: str, 
                          exchange: str = "SSE") -> pd.DataFrame:
        """Get trading calendar."""
        return self._call_api(
            self.pro.trade_cal,
            exchange=exchange,
            start_date=start_date,
            end_date=end_date
        )
    
    def get_stock_basic(self, list_status: str = "L", 
                       fields: Optional[List[str]] = None) -> pd.DataFrame:
        """Get stock basic information."""
        if fields is None:
            fields = [
                'ts_code', 'symbol', 'name', 'area', 'industry',
                'list_date', 'delist_date', 'list_status'
            ]
        
        return self._call_api(
            self.pro.stock_basic,
            list_status=list_status,
            fields=','.join(fields)
        )
    
    def get_daily_data(self, trade_date: str, 
                      ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get daily stock data for a specific date."""
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
        
        return self._call_api(self.pro.daily, **kwargs)
    
    def get_adj_factor(self, trade_date: str, 
                      ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get adjustment factors."""
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
            
        return self._call_api(self.pro.adj_factor, **kwargs)
    
    def get_daily_basic(self, trade_date: str, 
                       ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get daily basic indicators."""
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
            
        return self._call_api(self.pro.daily_basic, **kwargs)
    
    def get_suspend_data(self, trade_date: str, 
                        ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get suspension data."""
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
            
        return self._call_api(self.pro.suspend_d, **kwargs)
    
    def get_stk_limit(self, trade_date: str, 
                     ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get stock limit data (up/down limits)."""
        kwargs = {'trade_date': trade_date}
        if ts_code:
            kwargs['ts_code'] = ts_code
            
        return self._call_api(self.pro.stk_limit, **kwargs)
    
    def get_hk_basic(self, list_status: str = "L") -> pd.DataFrame:
        """Get Hong Kong stock basic information (placeholder)."""
        # HK data has very limited API calls (10/day), so this is mainly for structure
        logger.warning("HK basic data extraction is limited to 10 calls/day - using placeholder")
        
        # Return empty DataFrame with expected structure
        return pd.DataFrame(columns=[
            'ts_code', 'symbol', 'name', 'list_date', 'delist_date', 'list_status'
        ])
    
    def get_hk_daily(self, trade_date: str, 
                    ts_code: Optional[str] = None) -> pd.DataFrame:
        """Get Hong Kong daily data (placeholder)."""
        # HK data has very limited API calls (10/day), so this is mainly for structure
        logger.warning("HK daily data extraction is limited to 10 calls/day - using placeholder")
        
        # Return empty DataFrame with expected structure
        return pd.DataFrame(columns=[
            'ts_code', 'trade_date', 'open', 'high', 'low', 'close', 
            'pre_close', 'change', 'pct_chg', 'vol', 'amount'
        ])
    
    def batch_extract_daily_data(self, start_date: str, end_date: str,
                                ts_codes: Optional[List[str]] = None) -> pd.DataFrame:
        """Extract daily data for a date range."""
        all_data = []
        
        # Get trade calendar
        trade_cal = self.get_trade_calendar(start_date, end_date)
        trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        
        logger.info(f"Extracting daily data for {len(trade_dates)} trading days")
        
        for trade_date in trade_dates:
            try:
                daily_data = self.get_daily_data(trade_date)
                if not daily_data.empty:
                    all_data.append(daily_data)
                
                # Rate limiting is handled in _call_api
                logger.info(f"Extracted daily data for {trade_date}: {len(daily_data)} records")
                
            except Exception as e:
                logger.error(f"Failed to extract daily data for {trade_date}: {e}")
                continue
        
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"Total daily data extracted: {len(result)} records")
            return result
        else:
            return pd.DataFrame()
    
    def extract_all_data_for_date(self, trade_date: str, check_schedule: bool = True) -> Dict[str, pd.DataFrame]:
        """Extract all available data for a specific date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            check_schedule: Whether to check plugin schedule before extraction
        
        Returns:
            Dictionary with extracted data for each plugin
        """
        logger.info(f"Extracting all data for {trade_date}")
        
        from stock_datasource.core.plugin_manager import plugin_manager
        from stock_datasource.models.database import db_client
        from datetime import datetime
        
        # Discover plugins if not already done
        if not plugin_manager.plugins:
            plugin_manager.discover_plugins()
        
        # Parse trade_date to datetime.date for schedule checking
        trade_date_obj = datetime.strptime(trade_date, '%Y%m%d').date()
        
        data = {}
        
        # Extract data from each enabled plugin
        for plugin_name in plugin_manager.list_plugins():
            plugin = plugin_manager.get_plugin(plugin_name)
            
            if not plugin.is_enabled():
                logger.info(f"Plugin {plugin_name} is disabled, skipping")
                continue
            
            # Use plugin name as key (API name) for compatibility with loader
            api_name = plugin_name.replace('tushare_', '')
            
            # Check schedule if enabled
            should_skip_by_schedule = False
            if check_schedule and not plugin.should_run_today(trade_date_obj):
                # Check if table has data - if no data, must extract regardless of schedule
                schema = plugin.get_schema()
                table_name = schema.get('table_name')
                
                if table_name and db_client.table_exists(table_name):
                    try:
                        # Check if table has any data
                        query = f"SELECT COUNT(*) as cnt FROM {table_name} LIMIT 1"
                        result = db_client.execute_query(query)
                        record_count = result['cnt'].values[0] if len(result) > 0 else 0
                        
                        if record_count > 0:
                            # Table has data, skip based on schedule
                            logger.info(f"Plugin {plugin_name} not scheduled for {trade_date} and table has data, skipping")
                            should_skip_by_schedule = True
                        else:
                            # Table is empty, must extract
                            logger.info(f"Plugin {plugin_name} not scheduled for {trade_date} but table is empty, extracting anyway")
                    except Exception as e:
                        logger.warning(f"Failed to check table {table_name} data count: {e}, will extract")
                else:
                    # Table doesn't exist, skip
                    logger.info(f"Plugin {plugin_name} not scheduled for {trade_date}, skipping")
                    should_skip_by_schedule = True
            
            if should_skip_by_schedule:
                continue
            
            try:
                # Extract data using plugin
                # Handle special cases for plugins that need different parameters
                if plugin_name == 'tushare_trade_calendar':
                    # Trade calendar needs date range
                    extracted = plugin.extract_data(start_date=trade_date, end_date=trade_date)
                elif plugin_name == 'tushare_stock_basic':
                    # Stock basic doesn't need date
                    extracted = plugin.extract_data()
                else:
                    # Other plugins use trade_date
                    extracted = plugin.extract_data(trade_date=trade_date)
                
                data[api_name] = extracted
                logger.info(f"Extracted {api_name}: {len(extracted)} records")
                
            except Exception as e:
                logger.error(f"Failed to extract data from {plugin_name}: {e}")
                data[api_name] = pd.DataFrame()
        
        return data
    
    def validate_data_quality(self, data: pd.DataFrame, 
                            expected_date: str) -> Dict[str, Any]:
        """Basic data quality validation."""
        issues = []
        
        if data.empty:
            issues.append("DataFrame is empty")
            return {"valid": False, "issues": issues}
        
        # Check for required columns
        required_cols = ['ts_code', 'trade_date']
        missing_cols = [col for col in required_cols if col not in data.columns]
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
        
        # Check date consistency
        if 'trade_date' in data.columns:
            unique_dates = data['trade_date'].unique()
            if len(unique_dates) > 1:
                issues.append(f"Multiple trade dates found: {unique_dates}")
            elif len(unique_dates) == 1 and unique_dates[0] != expected_date:
                issues.append(f"Trade date mismatch: expected {expected_date}, got {unique_dates[0]}")
        
        # Check for null values in key fields
        if 'ts_code' in data.columns:
            null_codes = data['ts_code'].isnull().sum()
            if null_codes > 0:
                issues.append(f"Found {null_codes} null ts_code values")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "record_count": len(data),
            "column_count": len(data.columns)
        }


# Global extractor instance for backward compatibility
extractor = TuShareExtractor()
