"""TuShare stk_mins plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import StkMinsExtractor


class TuShareStkMinsPlugin(BasePlugin):
    """TuShare stk_mins plugin - A股历史分钟行情."""
    
    @property
    def name(self) -> str:
        return "tushare_stk_mins"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare A股历史分钟行情 from stk_mins API"
    
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
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract minute-level historical data from TuShare.
        
        Args:
            ts_code: Stock code (required, e.g., 600000.SH)
            freq: Frequency (1min/5min/15min/30min/60min), default: 1min
            start_date: Start datetime (e.g., '2023-08-25 09:00:00')
            end_date: End datetime (e.g., '2023-08-25 15:00:00')
        """
        ts_code = kwargs.get('ts_code')
        freq = kwargs.get('freq', '1min')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if not ts_code:
            raise ValueError("ts_code is required")
        
        self.logger.info(f"Extracting stk_mins data (ts_code={ts_code}, freq={freq})")
        
        extractor = StkMinsExtractor()
        data = extractor.extract(
            ts_code=ts_code, 
            freq=freq, 
            start_date=start_date, 
            end_date=end_date
        )
        
        if data.empty:
            self.logger.warning("No stk_mins data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} stk_mins records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate minute K-line data."""
        if data.empty:
            self.logger.warning("Empty stk_mins data")
            return False
        
        required_columns = ['ts_code', 'trade_time', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_times = data['trade_time'].isnull().sum()
        
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        if null_times > 0:
            self.logger.error(f"Found {null_times} null trade_time values")
            return False
        
        self.logger.info(f"stk_mins data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Transformed {len(data)} stk_mins records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load minute K-line data into ODS table.
        
        Args:
            data: stk_mins data to load
        
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
            table_name = "ods_stk_mins"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert(table_name, data)
            self.db.insert_dataframe(table_name, ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            return {
                "status": "success",
                "table": table_name,
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare A股历史分钟行情 Plugin")
    parser.add_argument("--ts-code", type=str, required=True, help="Stock code (e.g., 600000.SH)")
    parser.add_argument("--freq", type=str, default="1min",
                       choices=["1min", "5min", "15min", "30min", "60min"],
                       help="Frequency")
    parser.add_argument("--start-date", type=str, help="Start datetime (e.g., '2023-08-25 09:00:00')")
    parser.add_argument("--end-date", type=str, help="End datetime (e.g., '2023-08-25 15:00:00')")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareStkMinsPlugin()
    
    # Build kwargs
    kwargs = {
        "ts_code": args.ts_code,
        "freq": args.freq
    }
    if args.start_date:
        kwargs["start_date"] = args.start_date
    if args.end_date:
        kwargs["end_date"] = args.end_date
    
    # Run pipeline
    result = plugin.run(**kwargs)
    
    # Print result
    print(f"\n{'='*60}")
    print(f"Plugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    print(f"{'='*60}")
    
    for step, step_result in result.get('steps', {}).items():
        status = step_result.get('status', 'unknown')
        records = step_result.get('records', step_result.get('loaded_records', 0))
        print(f"{step:15} : {status:10} ({records} records)")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
