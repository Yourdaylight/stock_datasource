"""TuShare Hong Kong Stock Adjustment Factor plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareHKAdjFactorPlugin(BasePlugin):
    """TuShare Hong Kong Stock adjustment factor plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_hk_adjfactor"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare Hong Kong Stock daily adjustment factor data"
    
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
        """Get plugin role - Derived data."""
        return PluginRole.DERIVED
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return ["tushare_hk_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract HK adjustment factor data from TuShare."""
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if trade_date:
            self.logger.info(f"Extracting HK adjfactor for trade_date: {trade_date}")
            data = extractor.extract(trade_date=trade_date)
        elif ts_code and start_date and end_date:
            self.logger.info(f"Extracting HK adjfactor for {ts_code} from {start_date} to {end_date}")
            data = extractor.extract_by_date_range(ts_code, start_date, end_date)
        elif start_date and end_date:
            self.logger.info(f"Extracting HK adjfactor from {start_date} to {end_date}")
            data = extractor.extract(start_date=start_date, end_date=end_date)
        else:
            raise ValueError("Either trade_date, or (ts_code + start_date + end_date), or (start_date + end_date) is required")
        
        if data.empty:
            self.logger.warning(f"No HK adjfactor data found for params: {kwargs}")
            return pd.DataFrame()
        
        # Filter invalid records
        original_count = len(data)
        data = data[data['ts_code'].notna() & (data['ts_code'] != '')]
        if len(data) < original_count:
            self.logger.info(f"Filtered out {original_count - len(data)} invalid records")
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} HK adjfactor records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate HK adjustment factor data."""
        if data.empty:
            self.logger.warning("Empty HK adjfactor data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'cum_adjfactor']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Validate adj_factor is positive
        if 'cum_adjfactor' in data.columns:
            invalid = data[(data['cum_adjfactor'].notna()) & (data['cum_adjfactor'] <= 0)]
            if len(invalid) > 0:
                self.logger.warning(f"Found {len(invalid)} records with invalid cum_adjfactor <= 0")
        
        self.logger.info(f"HK adjfactor validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        numeric_columns = ['cum_adjfactor', 'close_price']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        if 'trade_date' in data.columns:
            if data['trade_date'].dtype == 'object':
                data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
            else:
                data['trade_date'] = pd.to_datetime(data['trade_date']).dt.date
        
        self.logger.info(f"Transformed {len(data)} HK adjfactor records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load HK adjustment factor data into ClickHouse."""
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
            table_name = "ods_hk_adjfactor"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            load_data = data.copy()
            load_data['version'] = int(datetime.now().timestamp())
            load_data['_ingested_at'] = datetime.now()
            
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
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare HK Adjustment Factor Plugin")
    parser.add_argument("--date", help="Trade date in YYYYMMDD format")
    parser.add_argument("--ts_code", help="Stock code (e.g., 00001.HK)")
    parser.add_argument("--start_date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end_date", help="End date in YYYYMMDD format")
    
    args = parser.parse_args()
    
    plugin = TuShareHKAdjFactorPlugin()
    
    kwargs = {}
    if args.date:
        kwargs['trade_date'] = args.date
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    
    if not kwargs:
        print("Error: At least one of --date, --ts_code, or --start_date/--end_date is required")
        sys.exit(1)
    
    result = plugin.run(**kwargs)
    
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
