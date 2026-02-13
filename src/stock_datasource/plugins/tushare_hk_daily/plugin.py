"""Hong Kong Stock Daily data plugin implementation using yfinance."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareHKDailyPlugin(BasePlugin):
    """Hong Kong Stock daily data plugin using yfinance.
    
    This plugin has been migrated from TuShare to yfinance to solve permission issues.
    Data format is kept compatible with TuShare format for backward compatibility.
    
    Note: The 'amount' (成交额) field is not available from yfinance and will be set to null.
    """
    
    @property
    def name(self) -> str:
        return "tushare_hk_daily"
    
    @property
    def version(self) -> str:
        return "2.0.0"
    
    @property
    def description(self) -> str:
        return "Hong Kong Stock daily price data using yfinance (TuShare format compatible)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 60)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_category(self) -> PluginCategory:
        """Get plugin category - Hong Kong Stock."""
        return PluginCategory.HK_STOCK
    
    def get_role(self) -> PluginRole:
        """Get plugin role - Primary data."""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        This plugin depends on tushare_hk_basic for getting stock list.
        """
        return ["tushare_hk_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies.
        
        No optional dependencies for this plugin.
        """
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract HK daily data from yfinance.
        
        Supports:
        - ts_code + start_date + end_date: Get a specific stock for a date range
        - start_date + end_date: Get all HK stocks for a date range (batch mode)
        - max_stocks: Limit number of stocks for testing
        
        Note: trade_date parameter is not recommended for yfinance.
        """
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        max_stocks = kwargs.get('max_stocks')
        
        if trade_date and not ts_code:
            self.logger.warning("Using trade_date without ts_code is not efficient for yfinance")
            self.logger.info("Consider using ts_code + start_date + end_date instead")
            raise ValueError("Use ts_code + start_date + end_date or start_date + end_date for batch mode")
        
        if ts_code:
            # Single stock mode
            self.logger.info(f"Extracting HK daily data for {ts_code}")
            if start_date and end_date:
                data = extractor.extract_by_date_range(ts_code, start_date, end_date)
            else:
                # Default: 1 year of data
                data = extractor.extract(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if data.empty:
                self.logger.warning(f"No data found for {ts_code}")
                return pd.DataFrame()
            
            self.logger.info(f"Extracted {len(data)} records for {ts_code}")
            
        else:
            # Batch mode: get all HK stocks
            if not start_date or not end_date:
                raise ValueError("Both start_date and end_date are required for batch mode")
            
            self.logger.info(f"Extracting HK daily data for all stocks from {start_date} to {end_date}")
            
            if not self.db:
                self.logger.error("Database not initialized for batch extraction")
                raise ValueError("Database connection required for batch mode")
            
            data = extractor.extract_all_hk_stocks(
                start_date=start_date,
                end_date=end_date,
                db_client=self.db,
                max_stocks=max_stocks
            )
            
            if data.empty:
                self.logger.warning("No HK daily data found")
                return pd.DataFrame()
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} HK daily records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate HK daily data."""
        if data.empty:
            self.logger.warning("Empty HK daily data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Validate price relationships
        invalid_prices = data[
            (data['high'] < data['low']) |
            (data['high'] < data['open']) |
            (data['high'] < data['close']) |
            (data['low'] > data['open']) |
            (data['low'] > data['close'])
        ]
        
        if len(invalid_prices) > 0:
            self.logger.warning(f"Found {len(invalid_prices)} records with invalid price relationships")
            # Don't fail validation for HK stocks as data quality may vary
        
        self.logger.info(f"HK daily data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Ensure proper data types
        numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'trade_date' in data.columns:
            # Handle both YYYYMMDD string format and datetime format
            if data['trade_date'].dtype == 'object':
                data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
            else:
                data['trade_date'] = pd.to_datetime(data['trade_date']).dt.date
        
        self.logger.info(f"Transformed {len(data)} HK daily records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load HK daily data into ClickHouse.
        
        Args:
            data: HK daily data to load
        
        Returns:
            Loading statistics
        """
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        results = {
            "status": "success",
            "tables_loaded": [],
            "total_records": 0
        }
        
        try:
            table_name = "ods_hk_daily"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            load_data = data.copy()
            load_data['version'] = int(datetime.now().timestamp())
            load_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            load_data = self._prepare_data_for_insert(table_name, load_data)
            self.db.insert_dataframe(table_name, load_data)
            
            results['tables_loaded'].append({
                'table': table_name,
                'records': len(load_data)
            })
            results['total_records'] += len(load_data)
            self.logger.info(f"Loaded {len(load_data)} records into {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="HK Daily Data Plugin (yfinance)")
    parser.add_argument("--ts_code", help="Stock code in TuShare format (e.g., 00001.HK)")
    parser.add_argument("--start_date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end_date", help="End date in YYYYMMDD format")
    parser.add_argument("--max_stocks", type=int, help="Maximum number of stocks (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareHKDailyPlugin()
    
    # Build kwargs
    kwargs = {}
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    if args.max_stocks:
        kwargs['max_stocks'] = args.max_stocks
    
    if not kwargs or (not args.ts_code and (not args.start_date or not args.end_date)):
        print("Error: Provide --ts_code, or both --start_date and --end_date")
        sys.exit(1)
    
    # Run pipeline
    result = plugin.run(**kwargs)
    
    # Print result
    print(f"\n{'='*60}")
    print(f"Plugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    print(f"{'='*60}")
    
    for step, step_result in result.get('steps', {}).items():
        status = step_result.get('status', 'unknown')
        records = step_result.get('records', 0)
        print(f"{step:15} : {status:10} ({records} records)")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
