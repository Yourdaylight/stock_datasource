"""TuShare suspension data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareSuspendDPlugin(BasePlugin):
    """TuShare suspension data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_suspend_d"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare suspension data from suspend_d API"
    
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
        """Extract suspension data from TuShare."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting suspension data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No suspension data found for {trade_date}")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
        data['trade_date'] = trade_date
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} suspension records for {trade_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate suspension data."""
        if data.empty:
            self.logger.warning("Empty suspension data")
            return False
        
        required_columns = ['ts_code', 'trade_date']
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
        
        # Validate suspend_type if present
        if 'suspend_type' in data.columns:
            valid_suspend_types = ['S', 'R', 'P', 'T']  # S=盘中停牌, R=盘中复牌, P=停牌, T=复牌
            invalid_types = data[data['suspend_type'].notna() & ~data['suspend_type'].isin(valid_suspend_types)]
            if len(invalid_types) > 0:
                self.logger.warning(f"Found {len(invalid_types)} invalid suspend_type values")
        
        self.logger.info(f"Suspension data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} suspension records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load suspension data into ODS table.
        
        Args:
            data: Suspension data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_suspend_d")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_suspend_d', ods_data)
            self.db.insert_dataframe('ods_suspend_d', ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_suspend_d")
            return {
                "status": "success",
                "table": "ods_suspend_d",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Suspension Data Plugin")
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareSuspendDPlugin()
    
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
