"""TuShare financial indicators data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareFinaceIndicatorPlugin(BasePlugin):
    """TuShare financial indicators data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_finace_indicator"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare financial indicators data"
    
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
        """Extract financial indicators data from TuShare."""
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        self.logger.info(f"Extracting financial indicators data for {ts_code or 'all stocks'} from {start_date} to {end_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if data.empty:
            self.logger.warning(f"No financial indicators data found for {ts_code or 'all stocks'} from {start_date} to {end_date}")
            return pd.DataFrame()
        
        # Ensure proper data types
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} financial indicators records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate financial indicators data."""
        if data.empty:
            self.logger.warning("Empty financial indicators data")
            return False
        
        required_columns = ['ts_code', 'end_date']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Validate date format
        try:
            pd.to_datetime(data['end_date'], format='%Y%m%d')
        except Exception as e:
            self.logger.error(f"Invalid end_date format: {e}")
            return False
        
        # Validate financial ratios (basic sanity checks)
        if 'roe' in data.columns:
            invalid_roe = data[(data['roe'] < -100) | (data['roe'] > 1000)]
            if len(invalid_roe) > 0:
                self.logger.warning(f"Found {len(invalid_roe)} records with potentially invalid ROE values")
        
        if 'net_profit_margin' in data.columns:
            invalid_margin = data[(data['net_profit_margin'] < -100) | (data['net_profit_margin'] > 100)]
            if len(invalid_margin) > 0:
                self.logger.warning(f"Found {len(invalid_margin)} records with potentially invalid profit margin values")
        
        self.logger.info(f"Financial indicators data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Ensure proper data types for numeric columns
        # Common financial indicators columns
        numeric_columns = [
            'roe', 'roa', 'gross_profit_margin', 'net_profit_margin',
            'eps', 'bps', 'total_revenue', 'net_profit', 'total_assets',
            'total_liab', 'total_equity', 'current_ratio', 'quick_ratio',
            'debt_to_assets', 'debt_to_equity', 'asset_turnover',
            'inventory_turnover', 'receivable_turnover'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'end_date' in data.columns:
            data['end_date'] = pd.to_datetime(data['end_date'], format='%Y%m%d').dt.date
        
        if 'ann_date' in data.columns:
            data['ann_date'] = pd.to_datetime(data['ann_date'], format='%Y%m%d').dt.date
        
        self.logger.info(f"Transformed {len(data)} financial indicators records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return ['tushare_stock_basic']  # Need stock basic info for validation
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load financial indicators data into ODS table.
        
        Args:
            data: Financial indicators data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_fina_indicator")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_fina_indicator', ods_data)
            self.db.insert_dataframe('ods_fina_indicator', ods_data)
            
            results['tables_loaded'].append({
                'table': 'ods_fina_indicator',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_fina_indicator")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Financial Indicators Data Plugin")
    parser.add_argument("--ts-code", help="Stock code (e.g., 002579.SZ)")
    parser.add_argument("--start-date", required=True, help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", required=True, help="End date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareFinaIndicatorPlugin()
    
    # Run pipeline
    result = plugin.run(ts_code=args.ts_code, start_date=args.start_date, end_date=args.end_date)
    
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