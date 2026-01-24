"""TuShare index weekly data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIndexWeeklyPlugin(BasePlugin):
    """TuShare index weekly data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_index_weekly"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare 指数周线行情数据"
    
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
        """Get plugin category - 指数."""
        return PluginCategory.INDEX
    
    def get_role(self) -> PluginRole:
        """Get plugin role - 主数据."""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return ["tushare_index_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract index weekly data from TuShare."""
        ts_code = kwargs.get('ts_code')
        trade_date = kwargs.get('trade_date')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        self.logger.info(f"Extracting index weekly data with params: {kwargs}")
        
        data = extractor.extract(
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date,
        )
        
        if data.empty:
            self.logger.warning("No index weekly data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} index weekly records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate index weekly data."""
        if data.empty:
            self.logger.warning("Empty index weekly data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.warning(f"Found {null_ts_codes} null ts_code values")
        
        self.logger.info(f"Index weekly data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        if data.empty:
            return data
        
        # Ensure proper data types for numeric columns
        numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        self.logger.info(f"Transformed {len(data)} index weekly records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load index weekly data into database.
        
        Args:
            data: Index weekly data to load
        
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
            schema = self.get_schema()
            table_name = schema.get('table_name')
            
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            # Add system columns
            data = self._add_system_columns(data)
            
            # Prepare data types
            data = self._prepare_data_for_insert(table_name, data)
            
            # Insert into database
            self.db.insert_dataframe(table_name, data)
            
            results['tables_loaded'].append({
                'table': table_name,
                'records': len(data)
            })
            results['total_records'] = len(data)
            self.logger.info(f"Loaded {len(data)} records into {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Index Weekly Data Plugin")
    parser.add_argument("--ts_code", help="Index code, e.g., 000001.SH")
    parser.add_argument("--trade_date", help="Trade date in YYYYMMDD format")
    parser.add_argument("--start_date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end_date", help="End date in YYYYMMDD format")
    
    args = parser.parse_args()
    
    plugin = TuShareIndexWeeklyPlugin()
    
    params = {}
    if args.ts_code:
        params['ts_code'] = args.ts_code
    if args.trade_date:
        params['trade_date'] = args.trade_date
    if args.start_date:
        params['start_date'] = args.start_date
    if args.end_date:
        params['end_date'] = args.end_date
    
    result = plugin.run(**params)
    
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
