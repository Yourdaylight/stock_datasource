"""TuShare index basic info plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIndexBasicPlugin(BasePlugin):
    """TuShare index basic info data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_index_basic"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare index basic information data"
    
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
    
    def get_category(self) -> PluginCategory:
        """Get plugin category."""
        return PluginCategory.INDEX
    
    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.BASIC
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract index basic information from TuShare."""
        market = kwargs.get('market')
        ts_code = kwargs.get('ts_code')
        name = kwargs.get('name')
        publisher = kwargs.get('publisher')
        category = kwargs.get('category')
        
        self.logger.info(f"Extracting index basic information")
        
        # Use plugin's extractor instance
        data = extractor.extract(market=market, ts_code=ts_code, name=name,
                               publisher=publisher, category=category)
        
        if data.empty:
            self.logger.warning("No index basic information found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} index basic information records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate index basic information data."""
        if data.empty:
            self.logger.warning("Empty index basic information data")
            return False
        
        required_columns = ['ts_code', 'name', 'market', 'publisher']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Validate market values
        valid_markets = {'SSE', 'SZSE', 'CSI', 'CICC', 'SW', 'OTH'}
        invalid_markets = data[~data['market'].isin(valid_markets)]
        if len(invalid_markets) > 0:
            self.logger.warning(f"Found {len(invalid_markets)} records with invalid market values")
        
        self.logger.info(f"Index basic information data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date fields
        date_columns = ['base_date', 'list_date', 'exp_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        # Convert numeric fields
        numeric_columns = ['base_point']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} index basic information records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load index basic information into DIM table.
        
        Args:
            data: Index basic information data to load
        
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
            # Load into DIM table
            self.logger.info(f"Loading {len(data)} records into dim_index_basic")
            dim_data = data.copy()
            dim_data = self._add_system_columns(dim_data)
            
            # Prepare data types
            dim_data = self._prepare_data_for_insert('dim_index_basic', dim_data)
            self.db.insert_dataframe('dim_index_basic', dim_data)
            
            results['tables_loaded'].append({
                'table': 'dim_index_basic',
                'records': len(dim_data)
            })
            results['total_records'] += len(dim_data)
            self.logger.info(f"Loaded {len(dim_data)} records into dim_index_basic")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Index Basic Plugin")
    parser.add_argument("--market", required=False, help="Market code (SSE/SZSE/CSI/CICC/SW)")
    parser.add_argument("--ts-code", required=False, help="Index code")
    parser.add_argument("--name", required=False, help="Index name")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareIndexBasicPlugin()
    
    # Run pipeline
    kwargs = {}
    if args.market:
        kwargs['market'] = args.market
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.name:
        kwargs['name'] = args.name
    
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
