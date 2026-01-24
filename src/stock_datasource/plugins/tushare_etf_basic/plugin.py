"""TuShare ETF basic information plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareETFBasicPlugin(BasePlugin):
    """TuShare ETF basic information plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_etf_basic"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare ETF基础信息 from etf_basic API"
    
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
        """Get plugin category."""
        return PluginCategory.ETF_FUND
    
    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.BASIC
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []  # ETF basic has no dependencies
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract ETF basic information from TuShare.
        
        Args:
            list_status: 上市状态 L上市 D退市 P待上市 (default: L)
            exchange: 交易所 SH/SZ
            ts_code: ETF代码
            index_code: 跟踪指数代码
            mgr: 管理人简称
        """
        list_status = kwargs.get('list_status', 'L')
        exchange = kwargs.get('exchange')
        ts_code = kwargs.get('ts_code')
        index_code = kwargs.get('index_code')
        mgr = kwargs.get('mgr')
        
        self.logger.info(f"Extracting ETF basic information with list_status={list_status}")
        
        data = extractor.extract(
            list_status=list_status,
            exchange=exchange,
            ts_code=ts_code,
            index_code=index_code,
            mgr=mgr
        )
        
        if data.empty:
            self.logger.warning(f"No ETF basic data found")
            return pd.DataFrame()
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} ETF basic records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate ETF basic data."""
        if data.empty:
            self.logger.warning("Empty ETF basic data")
            return False
        
        required_columns = ['ts_code', 'list_status']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_status = data['list_status'].isnull().sum()
        
        if null_ts_codes > 0 or null_status > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, list_status={null_status}")
            return False
        
        # Validate list_status values
        valid_status = ['L', 'D', 'P']
        invalid_status = data[~data['list_status'].isin(valid_status)]
        if len(invalid_status) > 0:
            self.logger.error(f"Found {len(invalid_status)} invalid list_status values")
            return False
        
        self.logger.info(f"ETF basic data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date columns
        date_columns = ['setup_date', 'list_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        # Convert numeric columns
        if 'mgt_fee' in data.columns:
            data['mgt_fee'] = pd.to_numeric(data['mgt_fee'], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} ETF basic records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load ETF basic data into ODS table.
        
        For basic/dimension tables, we use full_replace sync mode:
        1. Truncate the table first
        2. Insert all new data
        
        This ensures data consistency without duplicates.
        
        Args:
            data: ETF basic data to load
        
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
            table_name = 'ods_etf_basic'
            
            # For full_replace mode, truncate table first
            if self.get_sync_mode() == 'full_replace':
                if not self._truncate_table(table_name):
                    return {"status": "failed", "error": f"Failed to truncate {table_name}"}
            
            # Load into ODS table
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert(table_name, ods_data)
            
            # Add ClickHouse settings for large inserts
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe(table_name, ods_data, settings=settings)
            
            results['tables_loaded'].append({
                'table': table_name,
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare ETF Basic Plugin")
    parser.add_argument("--list-status", default="L", help="List status (L/D/P, default: L)")
    parser.add_argument("--exchange", help="Exchange (SH/SZ)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareETFBasicPlugin()
    
    # Run pipeline
    result = plugin.run(list_status=args.list_status, exchange=args.exchange)
    
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
