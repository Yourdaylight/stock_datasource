"""TuShare daily basic indicators plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareDailyBasicPlugin(BasePlugin):
    """TuShare daily basic indicators plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_daily_basic"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare daily basic indicators from daily_basic API"
    
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
        """Extract daily basic indicators from TuShare."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting daily basic indicators for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No daily basic data found for {trade_date}")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
        data['trade_date'] = trade_date
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} daily basic records for {trade_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate daily basic data."""
        if data.empty:
            self.logger.warning("Empty daily basic data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_dates = data['trade_date'].isnull().sum()
        null_closes = data['close'].isnull().sum()
        
        if null_ts_codes > 0 or null_dates > 0 or null_closes > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, trade_date={null_dates}, close={null_closes}")
            return False
        
        # Validate close price (should be positive if present)
        if 'close' in data.columns:
            valid_closes = data['close'].dropna()
            if len(valid_closes) > 0 and (valid_closes <= 0).any():
                self.logger.warning("Found some non-positive close prices")
        
        # Validate turnover rate (should be between 0 and 100 if present)
        if 'turnover_rate' in data.columns:
            valid_turnover = data['turnover_rate'].dropna()
            if len(valid_turnover) > 0 and ((valid_turnover < 0) | (valid_turnover > 100)).any():
                self.logger.warning("Found some invalid turnover rate values")
        
        self.logger.info(f"Daily basic data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert numeric columns to proper types
        numeric_columns = [
            'close', 'turnover_rate', 'turnover_rate_f', 'volume_ratio',
            'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 'dv_ttm',
            'total_share', 'float_share', 'free_share', 'total_mv', 'circ_mv'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert trade_date from YYYYMMDD string to date object
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Transformed {len(data)} daily basic records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load daily basic data into ODS table.
        
        Args:
            data: Daily basic data to load (already transformed with proper types)
        
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
            # Load into ODS table (data is already transformed with proper types)
            self.logger.info(f"Loading {len(data)} records into ods_daily_basic")
            ods_data = self._prepare_data_for_insert('ods_daily_basic', data.copy())
            self.db.insert_dataframe('ods_daily_basic', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records into ods_daily_basic")
            return {
                "status": "success",
                "table": "ods_daily_basic",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Daily Basic Plugin")
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareDailyBasicPlugin()
    
    # Run pipeline
    result = plugin.run(trade_date=args.date)
    
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
