"""TuShare stock company plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import StockCompanyExtractor


class TuShareStockCompanyPlugin(BasePlugin):
    """TuShare stock_company plugin - 上市公司基础信息."""
    
    @property
    def name(self) -> str:
        return "tushare_stock_company"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare stock company information from stock_company API"
    
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
        """Extract stock company data from TuShare.
        
        Args:
            ts_code: Optional stock code (e.g., 000001.SZ)
            exchange: Optional exchange code (SSE/SZSE/BSE)
        """
        ts_code = kwargs.get('ts_code')
        exchange = kwargs.get('exchange')
        
        self.logger.info(f"Extracting stock company data (ts_code={ts_code}, exchange={exchange})")
        
        extractor = StockCompanyExtractor()
        
        if ts_code or exchange:
            data = extractor.extract(ts_code=ts_code, exchange=exchange)
        else:
            data = extractor.extract_all()
        
        if data.empty:
            self.logger.warning("No stock company data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} company records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate stock company data."""
        if data.empty:
            self.logger.warning("Empty stock company data")
            return False
        
        required_columns = ['ts_code', 'com_name', 'exchange']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        self.logger.info(f"Stock company data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Transformed {len(data)} company records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load stock company data into ODS table.
        
        Args:
            data: Stock company data to load
        
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
            table_name = "ods_stock_company"
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
    
    parser = argparse.ArgumentParser(description="TuShare Stock Company Plugin")
    parser.add_argument("--ts-code", type=str, help="Stock code (e.g., 000001.SZ)")
    parser.add_argument("--exchange", type=str, choices=["SSE", "SZSE", "BSE"],
                       help="Exchange code")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareStockCompanyPlugin()
    
    # Build kwargs
    kwargs = {}
    if args.ts_code:
        kwargs["ts_code"] = args.ts_code
    if args.exchange:
        kwargs["exchange"] = args.exchange
    
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
