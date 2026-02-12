"""TuShare Hong Kong Stock Trade Calendar plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, date, timedelta
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareHKTradeCalPlugin(BasePlugin):
    """TuShare Hong Kong Stock trade calendar plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_hk_tradecal"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare Hong Kong Stock trade calendar data (hk_tradecal API)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 120)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_category(self) -> PluginCategory:
        """Get plugin category - Hong Kong Stock."""
        return PluginCategory.HK_STOCK
    
    def get_role(self) -> PluginRole:
        """Get plugin role - System data (trade calendar)."""
        return PluginRole.AUXILIARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        Trade calendar has no dependencies.
        """
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies.
        
        No optional dependencies for trade calendar.
        """
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract HK trade calendar data from TuShare.
        
        If start_date and end_date are not provided, defaults to:
        - start_date: 2 years ago from today
        - end_date: 2 years from today (to cover future trading days)
        """
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        is_open = kwargs.get('is_open')
        
        # Default to 2 years back and 2 years forward if not provided
        if not start_date or not end_date:
            today = date.today()
            default_start = today - timedelta(days=730)  # ~2 years back
            default_end = today + timedelta(days=730)    # ~2 years forward
            start_date = start_date or default_start.strftime('%Y%m%d')
            end_date = end_date or default_end.strftime('%Y%m%d')
            self.logger.info(f"Using default date range: {start_date} to {end_date}")
        
        self.logger.info(f"Extracting HK trade calendar from {start_date} to {end_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(start_date=start_date, end_date=end_date, is_open=is_open)
        
        if data.empty:
            self.logger.warning(f"No HK trade calendar data found for {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        # Convert is_open to integer (ClickHouse UInt8)
        if 'is_open' in data.columns:
            data['is_open'] = data['is_open'].astype(int)
        
        # Convert date columns
        date_columns = ['cal_date', 'pretrade_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d').dt.date
        
        self.logger.info(f"Extracted {len(data)} HK trade calendar records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate HK trade calendar data."""
        if data.empty:
            self.logger.warning("Empty HK trade calendar data")
            return False
        
        required_columns = ['cal_date', 'is_open']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_dates = data['cal_date'].isnull().sum()
        
        if null_dates > 0:
            self.logger.error(f"Found {null_dates} null cal_date values")
            return False
        
        # Validate is_open values (should be 0 or 1)
        invalid_is_open = data[~data['is_open'].isin([0, 1])]
        if len(invalid_is_open) > 0:
            self.logger.error(f"Found {len(invalid_is_open)} invalid is_open values")
            return False
        
        self.logger.info(f"HK trade calendar data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} HK trade calendar records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load HK trade calendar data into ClickHouse.
        
        Args:
            data: HK trade calendar data to load
        
        Returns:
            Loading statistics
        """
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            table_name = "ods_hk_trade_calendar"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            load_data = data.copy()
            load_data['version'] = int(datetime.now().timestamp())
            load_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            load_data = self._prepare_data_for_insert(table_name, load_data)
            
            # For large date ranges, we need to increase max_partitions_per_insert_block
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe(table_name, load_data, settings=settings)
            
            self.logger.info(f"Loaded {len(load_data)} records into {table_name}")
            return {
                "status": "success",
                "table": table_name,
                "loaded_records": len(load_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare HK Trade Calendar Plugin")
    parser.add_argument("--start-date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", help="End date in YYYYMMDD format")
    parser.add_argument("--is-open", help="Filter by trading status (0=closed, 1=open)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareHKTradeCalPlugin()
    
    # Build kwargs
    kwargs = {}
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    if args.is_open:
        kwargs['is_open'] = args.is_open
    
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
