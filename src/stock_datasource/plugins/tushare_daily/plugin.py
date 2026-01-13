"""TuShare daily data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareDailyPlugin(BasePlugin):
    """TuShare daily stock data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_daily"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare daily stock price data"
    
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
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        This plugin depends on tushare_stock_basic to provide the list of stock codes.
        """
        return ["tushare_stock_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies.
        
        Adjustment factor is optionally synced with daily data.
        """
        return ["tushare_adj_factor"]
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract daily data from TuShare."""
        trade_date = kwargs.get('trade_date')
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting daily data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date)
        
        if data.empty:
            self.logger.warning(f"No daily data found for {trade_date}")
            return pd.DataFrame()
        
        # Ensure proper data types
        data['trade_date'] = trade_date
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} daily records for {trade_date}")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate daily data."""
        if data.empty:
            self.logger.warning("Empty daily data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Validate price relationships
        invalid_prices = data[
            (data['high'] < data['low']) |
            (data['high'] < data['open']) |
            (data['high'] < data['close']) |
            (data['low'] > data['open']) |
            (data['low'] > data['close'])
        ]
        
        if len(invalid_prices) > 0:
            self.logger.error(f"Found {len(invalid_prices)} records with invalid price relationships")
            return False
        
        self.logger.info(f"Daily data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Ensure proper data types
        numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        self.logger.info(f"Transformed {len(data)} daily records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load daily data into ODS and Fact tables.
        
        Args:
            data: Daily data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_daily")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_daily', ods_data)
            self.db.insert_dataframe('ods_daily', ods_data)
            
            results['tables_loaded'].append({
                'table': 'ods_daily',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_daily")
            
            # Load into Fact table
            self.logger.info(f"Loading {len(data)} records into fact_daily_bar")
            fact_data = data.copy()
            fact_data['created_at'] = datetime.now()
            fact_data['updated_at'] = datetime.now()
            
            fact_data = self._prepare_data_for_insert('fact_daily_bar', fact_data)
            self.db.insert_dataframe('fact_daily_bar', fact_data)
            
            results['tables_loaded'].append({
                'table': 'fact_daily_bar',
                'records': len(fact_data),
                'has_adj_factors': adj_factor_data is not None and not adj_factor_data.empty
            })
            results['total_records'] += len(fact_data)
            self.logger.info(f"Loaded {len(fact_data)} records into fact_daily_bar")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results
    



if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Daily Data Plugin")
    parser.add_argument("--date", required=True, help="Trade date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareDailyPlugin()
    
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
