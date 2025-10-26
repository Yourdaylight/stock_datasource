"""TuShare trade calendar plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareTradeCalendarPlugin(BasePlugin):
    """TuShare trade calendar plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_trade_calendar"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare trade calendar data from trade_cal API"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 500)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract trade calendar data from TuShare."""
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        self.logger.info(f"Extracting trade calendar from {start_date} to {end_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(start_date, end_date)
        
        if data.empty:
            self.logger.warning(f"No trade calendar data found for {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
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
        
        self.logger.info(f"Extracted {len(data)} trade calendar records for {start_date} to {end_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate trade calendar data."""
        if data.empty:
            self.logger.warning("Empty trade calendar data")
            return False
        
        required_columns = ['exchange', 'cal_date', 'is_open']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_exchanges = data['exchange'].isnull().sum()
        null_dates = data['cal_date'].isnull().sum()
        
        if null_exchanges > 0 or null_dates > 0:
            self.logger.error(f"Found null values: exchange={null_exchanges}, cal_date={null_dates}")
            return False
        
        # Validate is_open values (should be 0 or 1)
        invalid_is_open = data[~data['is_open'].isin([0, 1])]
        if len(invalid_is_open) > 0:
            self.logger.error(f"Found {len(invalid_is_open)} invalid is_open values")
            return False
        
        self.logger.info(f"Trade calendar data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} trade calendar records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load trade calendar data into ODS table.
        
        Args:
            data: Trade calendar data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_trade_calendar")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_trade_calendar', ods_data)
            
            # For large date ranges, we need to increase max_partitions_per_insert_block
            # since trade_calendar is partitioned by month (toYYYYMM)
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_trade_calendar', ods_data, settings=settings)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_trade_calendar")
            return {
                "status": "success",
                "table": "ods_trade_calendar",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Trade Calendar Plugin")
    parser.add_argument("--start-date", required=True, help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", required=True, help="End date in YYYYMMDD format")
    parser.add_argument("--exchange", default="SSE", help="Exchange code (SSE/SZSE, default: SSE)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareTradeCalendarPlugin()
    
    # Run pipeline
    result = plugin.run(start_date=args.start_date, end_date=args.end_date, exchange=args.exchange)
    
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
