"""TuShare ETF fund daily data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareETFFundDailyPlugin(BasePlugin):
    """TuShare ETF fund daily data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_etf_fund_daily"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare ETF日线行情 from fund_daily API"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 30)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_etf_codes(self) -> List[str]:
        """Get ETF code list from database."""
        if not self.db:
            self.logger.warning("Database not initialized, cannot get ETF codes")
            return []
        
        try:
            query = "SELECT ts_code FROM ods_etf_basic WHERE list_status = 'L'"
            df = self.db.execute_query(query)
            return df['ts_code'].tolist() if not df.empty else []
        except Exception as e:
            self.logger.warning(f"Failed to get ETF codes from database: {e}")
            return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract ETF fund daily data from TuShare.
        
        Args:
            ts_code: ETF代码
            trade_date: 交易日期 YYYYMMDD格式
            start_date: 开始日期 YYYYMMDD格式
            end_date: 结束日期 YYYYMMDD格式
        """
        ts_code = kwargs.get('ts_code')
        trade_date = kwargs.get('trade_date')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        self.logger.info(f"Extracting ETF fund daily data: ts_code={ts_code}, trade_date={trade_date}")
        
        data = extractor.extract(
            ts_code=ts_code,
            trade_date=trade_date,
            start_date=start_date,
            end_date=end_date
        )
        
        if data.empty:
            self.logger.warning("No ETF fund daily data found")
            return pd.DataFrame()
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} ETF fund daily records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate ETF fund daily data."""
        if data.empty:
            self.logger.warning("Empty ETF fund daily data")
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
        
        # Validate price relationships (high >= low)
        if 'high' in data.columns and 'low' in data.columns:
            invalid_prices = data[data['high'] < data['low']]
            if len(invalid_prices) > 0:
                self.logger.warning(f"Found {len(invalid_prices)} records with high < low")
        
        self.logger.info(f"ETF fund daily data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert date column
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Convert numeric columns
        numeric_columns = ['open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_chg', 'vol', 'amount']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} ETF fund daily records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return ["tushare_etf_basic"]
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load ETF fund daily data into ODS table.
        
        Args:
            data: ETF fund daily data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_etf_fund_daily")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert('ods_etf_fund_daily', ods_data)
            
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_etf_fund_daily', ods_data, settings=settings)
            
            results['tables_loaded'].append({
                'table': 'ods_etf_fund_daily',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_etf_fund_daily")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare ETF Fund Daily Plugin")
    parser.add_argument("--date", help="Trade date in YYYYMMDD format")
    parser.add_argument("--ts-code", help="ETF code")
    parser.add_argument("--start-date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", help="End date in YYYYMMDD format")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareETFFundDailyPlugin()
    
    # Run pipeline
    result = plugin.run(
        trade_date=args.date,
        ts_code=args.ts_code,
        start_date=args.start_date,
        end_date=args.end_date
    )
    
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
