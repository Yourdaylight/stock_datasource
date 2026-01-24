"""TuShare ETF基准指数列表 plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareETFIndexPlugin(BasePlugin):
    """TuShare ETF基准指数列表 plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_etf_index"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare ETF基准指数列表 from etf_index API"
    
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
        return PluginRole.AUXILIARY  # 辅助数据，为ETF提供基准指数信息
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []  # 无必须依赖
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return ["tushare_etf_basic"]  # 可选与ETF基础信息关联
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract ETF基准指数列表 from TuShare.
        
        Args:
            ts_code: 指数代码
            pub_date: 发布日期（格式：YYYYMMDD）
            base_date: 指数基期（格式：YYYYMMDD）
        """
        ts_code = kwargs.get('ts_code')
        pub_date = kwargs.get('pub_date')
        base_date = kwargs.get('base_date')
        
        self.logger.info(f"Extracting ETF基准指数列表")
        
        data = extractor.extract(
            ts_code=ts_code,
            pub_date=pub_date,
            base_date=base_date
        )
        
        if data.empty:
            self.logger.warning(f"No ETF基准指数 data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} ETF基准指数 records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate ETF基准指数列表 data."""
        if data.empty:
            self.logger.warning("Empty ETF基准指数列表 data")
            return False
        
        required_columns = ['ts_code']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Check for duplicates
        dup_count = data['ts_code'].duplicated().sum()
        if dup_count > 0:
            self.logger.warning(f"Found {dup_count} duplicate ts_code values")
        
        self.logger.info(f"ETF基准指数列表 data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date columns to YYYY-MM-DD string format
        # (using String type to avoid ClickHouse Date type range limitation: 1970-2149)
        date_columns = ['pub_date', 'base_date']
        for col in date_columns:
            if col in data.columns:
                # Convert YYYYMMDD to YYYY-MM-DD string
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce')
                data[col] = data[col].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notna(x) else '')
        
        # Convert numeric columns
        if 'bp' in data.columns:
            data['bp'] = pd.to_numeric(data['bp'], errors='coerce')
        
        # Fill NaN for string columns
        string_columns = ['indx_name', 'indx_csname', 'pub_party_name', 'adj_circle']
        for col in string_columns:
            if col in data.columns:
                data[col] = data[col].fillna('')
        
        self.logger.info(f"Transformed {len(data)} ETF基准指数 records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load ETF基准指数列表 data into ODS table.
        
        For basic/dimension tables, we use full_replace sync mode:
        1. Truncate the table first
        2. Insert all new data
        
        This ensures data consistency without duplicates.
        
        Args:
            data: ETF基准指数列表 data to load
        
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
            table_name = 'ods_etf_index'
            
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
    
    parser = argparse.ArgumentParser(description="TuShare ETF Index Plugin")
    parser.add_argument("--ts-code", help="指数代码")
    parser.add_argument("--pub-date", help="发布日期（格式：YYYYMMDD）")
    parser.add_argument("--base-date", help="指数基期（格式：YYYYMMDD）")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareETFIndexPlugin()
    
    # Run pipeline
    kwargs = {}
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.pub_date:
        kwargs['pub_date'] = args.pub_date
    if args.base_date:
        kwargs['base_date'] = args.base_date
    
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
