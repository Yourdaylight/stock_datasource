"""TuShare stock limit plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareStkLimitPlugin(BasePlugin):
    """TuShare stock limit (up/down) plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_stk_limit"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare stock limit prices from stk_limit API"
    
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
        """Extract stock limit data from TuShare."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting stock limit data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No stock limit data found for {trade_date}")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
        data['trade_date'] = trade_date
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} stock limit records for {trade_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate stock limit data."""
        if data.empty:
            self.logger.warning("Empty stock limit data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'up_limit', 'down_limit']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_dates = data['trade_date'].isnull().sum()
        
        if null_ts_codes > 0 or null_dates > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, trade_date={null_dates}")
            return False
        
        # Validate limit prices (should be positive if present)
        if 'up_limit' in data.columns and 'down_limit' in data.columns:
            valid_up_limits = data['up_limit'].dropna()
            valid_down_limits = data['down_limit'].dropna()
            
            if len(valid_up_limits) > 0 and (valid_up_limits <= 0).any():
                self.logger.warning("Found some non-positive up limit prices")
            
            if len(valid_down_limits) > 0 and (valid_down_limits <= 0).any():
                self.logger.warning("Found some non-positive down limit prices")
            
            # Check if up_limit > down_limit
            valid_limits = data[['up_limit', 'down_limit']].dropna()
            if len(valid_limits) > 0 and (valid_limits['up_limit'] <= valid_limits['down_limit']).any():
                self.logger.error("Found up_limit <= down_limit for some records")
                return False
        
        self.logger.info(f"Stock limit data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert numeric columns to proper types
        if 'up_limit' in data.columns:
            data['up_limit'] = pd.to_numeric(data['up_limit'], errors='coerce')
        
        if 'down_limit' in data.columns:
            data['down_limit'] = pd.to_numeric(data['down_limit'], errors='coerce')
        
        # Convert trade_date from YYYYMMDD string to date object
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Transformed {len(data)} stock limit records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load stock limit data into ODS table.
        
        Args:
            data: Stock limit data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_stk_limit")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_stk_limit', ods_data)
            self.db.insert_dataframe('ods_stk_limit', ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_stk_limit")
            return {
                "status": "success",
                "table": "ods_stk_limit",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Stock Limit Plugin")
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareStkLimitPlugin()
    
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
