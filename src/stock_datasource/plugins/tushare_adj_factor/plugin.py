"""TuShare adjustment factor plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareAdjFactorPlugin(BasePlugin):
    """TuShare adjustment factor plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_adj_factor"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare adjustment factor data from adj_factor API"
    
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
        return PluginCategory.STOCK
    
    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.DERIVED
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        This plugin depends on tushare_stock_basic to provide the list of stock codes.
        """
        return ["tushare_stock_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract adjustment factor data from TuShare."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting adjustment factor data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No adjustment factor data found for {trade_date}")
            return pd.DataFrame()
        
        # Ensure proper data types and add system columns
        data['trade_date'] = trade_date
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} adjustment factor records for {trade_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate adjustment factor data."""
        if data.empty:
            self.logger.warning("Empty adjustment factor data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'adj_factor']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_dates = data['trade_date'].isnull().sum()
        
        if null_ts_codes > 0 or null_dates > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, trade_date={null_dates}")
            return False
        
        # Validate adj_factor values (should be positive if present)
        if 'adj_factor' in data.columns:
            valid_adj_factors = data['adj_factor'].dropna()
            if len(valid_adj_factors) > 0 and (valid_adj_factors <= 0).any():
                self.logger.warning("Found some non-positive adjustment factor values")
        
        self.logger.info(f"Adjustment factor data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Ensure adj_factor is numeric
        if 'adj_factor' in data.columns:
            data['adj_factor'] = pd.to_numeric(data['adj_factor'], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} adjustment factor records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load adjustment factor data into ODS table.
        
        Args:
            data: Adjustment factor data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_adj_factor")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_adj_factor', ods_data)
            self.db.insert_dataframe('ods_adj_factor', ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_adj_factor")
            return {
                "status": "success",
                "table": "ods_adj_factor",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Adjustment Factor Plugin")
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareAdjFactorPlugin()
    
    # Run pipeline
    result = plugin.run(trade_date=args.date)
    
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
