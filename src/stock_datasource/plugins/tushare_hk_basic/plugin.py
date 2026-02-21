"""TuShare Hong Kong Stock Basic Info plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareHKBasicPlugin(BasePlugin):
    """TuShare Hong Kong Stock basic info plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_hk_basic"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare Hong Kong Stock basic info data (hk_basic API)"
    
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
        """Get plugin role - Auxiliary data (stock list)."""
        return PluginRole.AUXILIARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        HK basic has no dependencies.
        """
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies.
        
        No optional dependencies.
        """
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract HK stock basic info from TuShare.
        
        Args:
            ts_code: Optional TS code to filter
            list_status: Optional listing status filter (L/D/P)
            all: If True, extract all stocks (L+D+P)
        """
        ts_code = kwargs.get('ts_code')
        list_status = kwargs.get('list_status')
        extract_all = kwargs.get('all', False)
        
        if extract_all:
            self.logger.info("Extracting all HK stocks (L+D+P)")
            data = extractor.extract_all()
        else:
            status_desc = f"list_status={list_status}" if list_status else "default(L)"
            self.logger.info(f"Extracting HK stock basic info: {status_desc}")
            data = extractor.extract(ts_code=ts_code, list_status=list_status)
        
        if data.empty:
            self.logger.warning("No HK stock basic data found")
            return pd.DataFrame()
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} HK stock basic records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate HK stock basic data."""
        if data.empty:
            self.logger.warning("Empty HK stock basic data")
            return False
        
        required_columns = ['ts_code', 'name']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null ts_codes
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Check for duplicate ts_codes
        duplicates = data['ts_code'].duplicated().sum()
        if duplicates > 0:
            self.logger.warning(f"Found {duplicates} duplicate ts_codes")
        
        self.logger.info(f"HK stock basic data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date columns
        date_columns = ['list_date', 'delist_date']
        for col in date_columns:
            if col in data.columns:
                # Handle both YYYYMMDD string format and datetime format
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        # Ensure list_status has default value
        if 'list_status' in data.columns:
            data['list_status'] = data['list_status'].fillna('L')
        
        self.logger.info(f"Transformed {len(data)} HK stock basic records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load HK stock basic data into ClickHouse.
        
        Args:
            data: HK stock basic data to load
        
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
            table_name = "ods_hk_basic"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            load_data = data.copy()
            load_data['version'] = int(datetime.now().timestamp())
            load_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            load_data = self._prepare_data_for_insert(table_name, load_data)
            self.db.insert_dataframe(table_name, load_data)
            
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
    
    parser = argparse.ArgumentParser(description="TuShare HK Basic Info Plugin")
    parser.add_argument("--ts-code", help="TS code (e.g., 00001.HK)")
    parser.add_argument("--list-status", choices=['L', 'D', 'P'], help="Listing status")
    parser.add_argument("--all", action="store_true", help="Extract all stocks (L+D+P)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareHKBasicPlugin()
    
    # Build kwargs
    kwargs = {}
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.list_status:
        kwargs['list_status'] = args.list_status
    if args.all:
        kwargs['all'] = True
    
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
