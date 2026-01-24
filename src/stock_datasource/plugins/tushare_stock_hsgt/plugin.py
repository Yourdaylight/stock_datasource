"""TuShare stock HSGT plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareStockHSGTPlugin(BasePlugin):
    """TuShare stock HSGT plugin - 获取沪深港通股票列表."""
    
    # Valid HSGT types
    VALID_TYPES = ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']
    
    @property
    def name(self) -> str:
        return "tushare_stock_hsgt"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare 沪深港通股票列表 from stock_hsgt API"
    
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
        return PluginCategory.CN_STOCK
    
    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.AUXILIARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract stock HSGT data from TuShare."""
        hsgt_type = kwargs.get('type')
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        # If no type specified, fetch all types
        if not hsgt_type:
            self.logger.info("No type specified, fetching all HSGT types")
            all_data = []
            for t in self.VALID_TYPES:
                self.logger.info(f"Extracting HSGT data for type={t}")
                data = extractor.extract(
                    hsgt_type=t,
                    trade_date=trade_date,
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
                if not data.empty:
                    all_data.append(data)
            
            if not all_data:
                self.logger.warning("No stock HSGT data found")
                return pd.DataFrame()
            
            data = pd.concat(all_data, ignore_index=True)
        else:
            self.logger.info(f"Extracting stock HSGT data: type={hsgt_type}, trade_date={trade_date}")
            data = extractor.extract(
                hsgt_type=hsgt_type,
                trade_date=trade_date,
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
        
        if data.empty:
            self.logger.warning("No stock HSGT data found")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        # Convert trade_date to Date type
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        self.logger.info(f"Extracted {len(data)} stock HSGT records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate stock HSGT data."""
        if data.empty:
            self.logger.warning("Empty stock HSGT data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'type']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_dates = data['trade_date'].isnull().sum()
        null_types = data['type'].isnull().sum()
        
        if null_ts_codes > 0 or null_dates > 0 or null_types > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, trade_date={null_dates}, type={null_types}")
            return False
        
        # Validate type values
        invalid_types = data[~data['type'].isin(self.VALID_TYPES)]
        if len(invalid_types) > 0:
            self.logger.error(f"Found {len(invalid_types)} invalid type values")
            return False
        
        self.logger.info(f"Stock HSGT data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} stock HSGT records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load stock HSGT data into ODS table.
        
        Args:
            data: Stock HSGT data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_stock_hsgt")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_stock_hsgt', ods_data)
            self.db.insert_dataframe('ods_stock_hsgt', ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_stock_hsgt")
            return {
                "status": "success",
                "table": "ods_stock_hsgt",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Stock HSGT Plugin")
    parser.add_argument("--date", help="Trade date in YYYYMMDD format")
    parser.add_argument("--type", choices=['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'], 
                        help="HSGT type (if not specified, fetches all types)")
    parser.add_argument("--ts-code", help="Stock code")
    parser.add_argument("--start-date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", help="End date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareStockHSGTPlugin()
    
    # Build kwargs
    run_kwargs = {}
    if args.date:
        run_kwargs['trade_date'] = args.date
    if args.type:
        run_kwargs['type'] = args.type
    if args.ts_code:
        run_kwargs['ts_code'] = args.ts_code
    if args.start_date:
        run_kwargs['start_date'] = args.start_date
    if args.end_date:
        run_kwargs['end_date'] = args.end_date
    
    # Run pipeline
    result = plugin.run(**run_kwargs)
    
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
