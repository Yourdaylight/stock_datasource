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
    
    def _get_all_stock_codes(self) -> List[str]:
        """Get all stock codes from tushare_stock_basic plugin."""
        try:
            from stock_datasource.plugins.tushare_stock_basic.plugin import TuShareStockBasicPlugin
            
            self.logger.info("Fetching all stock codes from tushare_stock_basic")
            stock_plugin = TuShareStockBasicPlugin()
            stock_data = stock_plugin.extract_data()
            
            if stock_data.empty:
                self.logger.warning("No stock codes found")
                return []
            
            stock_codes = stock_data['ts_code'].tolist()
            self.logger.info(f"Found {len(stock_codes)} stock codes")
            return stock_codes
            
        except Exception as e:
            self.logger.error(f"Failed to get stock codes: {e}")
            return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract financial indicators data from TuShare.
        
        Args:
            ts_code: Optional stock code. If not provided, will fetch all stocks.
            start_date: Start date in YYYYMMDD format (required)
            end_date: End date in YYYYMMDD format (required)
            batch_size: Number of stocks to process in each batch (default: 10)
            max_stocks: Maximum number of stocks to process (for testing)
        """
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        batch_size = kwargs.get('batch_size', 10)
        max_stocks = kwargs.get('max_stocks')
        
        if not start_date or not end_date:
            raise ValueError("start_date and end_date are required")
        
        # If ts_code is provided, use single stock extraction
        if ts_code:
            self.logger.info(f"Extracting financial indicators data for {ts_code} from {start_date} to {end_date}")
            data = extractor.extract(ts_code=ts_code, start_date=start_date, end_date=end_date)
            
            if data.empty:
                self.logger.warning(f"No financial indicators data found for {ts_code} from {start_date} to {end_date}")
                return pd.DataFrame()
            
            # Ensure proper data types
            data['version'] = int(datetime.now().timestamp())
            data['_ingested_at'] = datetime.now()
            
            self.logger.info(f"Extracted {len(data)} financial indicators records")
            return data
        
        # If no ts_code provided, fetch all stocks and process one by one
        self.logger.info(f"Extracting financial indicators data for all stocks from {start_date} to {end_date}")
        
        # Get all stock codes
        stock_codes = self._get_all_stock_codes()
        if not stock_codes:
            self.logger.error("No stock codes available")
            return pd.DataFrame()
        
        # Apply max_stocks limit if specified (for testing)
        if max_stocks:
            stock_codes = stock_codes[:max_stocks]
            self.logger.info(f"Limited to first {max_stocks} stocks for testing")
        
        # Process stocks in batches
        all_data = []
        total_stocks = len(stock_codes)
        success_count = 0
        failed_count = 0
        
        self.logger.info(f"Processing {total_stocks} stocks in batches of {batch_size}")
        
        for i, code in enumerate(stock_codes, 1):
            try:
                self.logger.info(f"[{i}/{total_stocks}] Extracting data for {code}")
                
                # Extract data for single stock
                stock_data = extractor.extract(ts_code=code, start_date=start_date, end_date=end_date)
                
                if not stock_data.empty:
                    all_data.append(stock_data)
                    success_count += 1
                    self.logger.info(f"[{i}/{total_stocks}] {code}: {len(stock_data)} records")
                else:
                    self.logger.debug(f"[{i}/{total_stocks}] {code}: No data")
                
            except Exception as e:
                failed_count += 1
                self.logger.error(f"[{i}/{total_stocks}] {code}: Failed - {e}")
            
            # Log progress every batch_size stocks
            if i % batch_size == 0:
                self.logger.info(f"Progress: {i}/{total_stocks} stocks processed (success={success_count}, failed={failed_count})")
        
        # Combine all data
        if not all_data:
            self.logger.warning(f"No financial indicators data found for any stocks from {start_date} to {end_date}")
            return pd.DataFrame()
        
        combined_data = pd.concat(all_data, ignore_index=True)
        
        # Ensure proper data types
        combined_data['version'] = int(datetime.now().timestamp())
        combined_data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(combined_data)} financial indicators records from {success_count} stocks")
        self.logger.info(f"Summary: success={success_count}, failed={failed_count}, total={total_stocks}")
        
        return combined_data
    
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
    parser.add_argument("--ts-code", help="Stock code (e.g., 002579.SZ). If not provided, will process all stocks.")
    parser.add_argument("--start-date", required=True, help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", required=True, help="End date in YYYYMMDD format")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing multiple stocks (default: 10)")
    parser.add_argument("--max-stocks", type=int, help="Maximum number of stocks to process (for testing)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareFinaceIndicatorPlugin()
    
    # Prepare kwargs
    kwargs = {
        'start_date': args.start_date,
        'end_date': args.end_date,
        'batch_size': args.batch_size
    }
    
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    
    if args.max_stocks:
        kwargs['max_stocks'] = args.max_stocks
    
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
    
    print(f"\n✅ Successfully processed financial indicators data")
    sys.exit(0)