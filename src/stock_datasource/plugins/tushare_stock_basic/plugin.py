"""TuShare stock basic information plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareStockBasicPlugin(BasePlugin):
    """TuShare stock basic information plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_stock_basic"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare stock basic information from stock_basic API"
    
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
        """Extract stock basic information from TuShare."""
        list_status = kwargs.get('list_status', 'L')  # Default to listed stocks
        
        self.logger.info(f"Extracting stock basic information with list_status={list_status}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(list_status=list_status)
        
        if data.empty:
            self.logger.warning(f"No stock basic data found for list_status={list_status}")
            return pd.DataFrame()
        
        # Add market column based on ts_code suffix (.SZ or .SH)
        if 'ts_code' in data.columns:
            data['market'] = data['ts_code'].apply(
                lambda x: 'SZSE' if x.endswith('.SZ') else ('SSE' if x.endswith('.SH') else 'OTHER')
            )
        
        # Ensure proper data types and add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        # Convert date columns
        if 'list_date' in data.columns:
            data['list_date'] = pd.to_datetime(data['list_date'], format='%Y%m%d', errors='coerce').dt.date
        
        if 'delist_date' in data.columns:
            data['delist_date'] = pd.to_datetime(data['delist_date'], format='%Y%m%d', errors='coerce').dt.date
        
        self.logger.info(f"Extracted {len(data)} stock basic records for list_status={list_status}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate stock basic data."""
        if data.empty:
            self.logger.warning("Empty stock basic data")
            return False
        
        required_columns = ['ts_code', 'symbol', 'name', 'list_status']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_symbols = data['symbol'].isnull().sum()
        null_names = data['name'].isnull().sum()
        null_status = data['list_status'].isnull().sum()
        
        if null_ts_codes > 0 or null_symbols > 0 or null_names > 0 or null_status > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, symbol={null_symbols}, name={null_names}, list_status={null_status}")
            return False
        
        # Validate list_status values
        valid_status = ['L', 'D', 'P']
        invalid_status = data[~data['list_status'].isin(valid_status)]
        if len(invalid_status) > 0:
            self.logger.error(f"Found {len(invalid_status)} invalid list_status values")
            return False
        
        self.logger.info(f"Stock basic data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} stock basic records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load stock basic data into ODS and DIM tables.
        
        Args:
            data: Stock basic data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_stock_basic")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert('ods_stock_basic', ods_data)
            
            # Add ClickHouse settings for large inserts
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_stock_basic', ods_data, settings=settings)
            
            results['tables_loaded'].append({
                'table': 'ods_stock_basic',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_stock_basic")
            
            # Load into DIM table
            self.logger.info(f"Loading {len(data)} records into dim_security")
            dim_data = data.copy()
            
            # Map columns
            column_mapping = {
                'ts_code': 'ts_code',
                'symbol': 'ticker',
                'name': 'name',
                'list_date': 'list_date',
                'delist_date': 'delist_date',
                'list_status': 'status'
            }
            
            # Select and rename columns
            available_cols = [col for col in column_mapping.keys() if col in dim_data.columns]
            dim_data = dim_data[available_cols].rename(columns=column_mapping)
            
            # Add market column
            dim_data['market'] = 'CN'
            
            # Ensure required columns exist
            required_cols = ['ts_code', 'ticker', 'name', 'list_date', 'status']
            for col in required_cols:
                if col not in dim_data.columns:
                    if col == 'status':
                        dim_data[col] = 'L'  # Default to Listed
                    else:
                        self.logger.warning(f"Missing required column {col} in stock basic data")
            
            # Convert date formats
            if 'list_date' in dim_data.columns:
                dim_data['list_date'] = pd.to_datetime(dim_data['list_date']).dt.date
            
            if 'delist_date' in dim_data.columns:
                dim_data['delist_date'] = pd.to_datetime(dim_data['delist_date'], errors='coerce').dt.date
            
            # Add timestamps and version
            now = datetime.now()
            dim_data['created_at'] = now
            dim_data['updated_at'] = now
            dim_data['version'] = int(now.timestamp())
            
            dim_data = self._prepare_data_for_insert('dim_security', dim_data)
            self.db.insert_dataframe('dim_security', dim_data)
            
            results['tables_loaded'].append({
                'table': 'dim_security',
                'records': len(dim_data)
            })
            results['total_records'] += len(dim_data)
            self.logger.info(f"Loaded {len(dim_data)} records into dim_security")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Stock Basic Plugin")
    parser.add_argument("--list-status", default="L", help="List status (L/D/P, default: L)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareStockBasicPlugin()
    
    # Run pipeline
    result = plugin.run(list_status=args.list_status)
    
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
