"""TuShare index weight plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareIndexWeightPlugin(BasePlugin):
    """TuShare index weight data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_index_weight"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare index weight data (constituent stocks and weights)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 30)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract index weight data from TuShare."""
        config = self.get_config()
        index_code = kwargs.get('index_code') or config.get('parameters', {}).get('index_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        trade_date = kwargs.get('trade_date')
        
        # Normalize date formats to YYYYMMDD as required by TuShare
        def _normalize(date_str: Any) -> Any:
            if not date_str or not isinstance(date_str, str):
                return date_str
            return date_str.replace('-', '')
        
        start_date = _normalize(start_date)
        end_date = _normalize(end_date)
        trade_date = _normalize(trade_date)
        
        if not index_code:
            raise ValueError("index_code is required (set in task params or config.parameters.index_code)")
        
        self.logger.info(f"Extracting index weight data for {index_code}")
        
        # Use plugin's extractor instance
        data = extractor.extract(index_code=index_code, start_date=start_date,
                               end_date=end_date, trade_date=trade_date)
        
        if data.empty:
            self.logger.warning(f"No index weight data found for {index_code}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} index weight records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate index weight data."""
        if data.empty:
            self.logger.warning("Empty index weight data")
            return False
        
        required_columns = ['index_code', 'con_code', 'trade_date', 'weight']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_index_codes = data['index_code'].isnull().sum()
        if null_index_codes > 0:
            self.logger.error(f"Found {null_index_codes} null index_code values")
            return False
        
        null_con_codes = data['con_code'].isnull().sum()
        if null_con_codes > 0:
            self.logger.error(f"Found {null_con_codes} null con_code values")
            return False
        
        # Validate weight values (should be between 0 and 100)
        if 'weight' in data.columns:
            invalid_weights = data[(data['weight'] < 0) | (data['weight'] > 100)]
            if len(invalid_weights) > 0:
                self.logger.warning(f"Found {len(invalid_weights)} records with invalid weight values")
        
        self.logger.info(f"Index weight data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Convert weight to numeric
        if 'weight' in data.columns:
            data['weight'] = pd.to_numeric(data['weight'], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} index weight records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []  # No dependencies for index weight data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load index weight data into ODS table.
        
        Args:
            data: Index weight data to load
        
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
            # Load into ODS table
            self.logger.info(f"Loading {len(data)} records into ods_index_weight")
            ods_data = data.copy()
            ods_data = self._add_system_columns(ods_data)
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_index_weight', ods_data)
            self.db.insert_dataframe('ods_index_weight', ods_data)
            
            results['tables_loaded'].append({
                'table': 'ods_index_weight',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_index_weight")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Index Weight Plugin")
    parser.add_argument("--index-code", required=True, help="Index code (e.g., 399300.SZ)")
    parser.add_argument("--start-date", required=False, help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", required=False, help="End date in YYYYMMDD format")
    parser.add_argument("--trade-date", required=False, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareIndexWeightPlugin()
    
    # Run pipeline
    kwargs = {'index_code': args.index_code}
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    if args.trade_date:
        kwargs['trade_date'] = args.trade_date
    
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
