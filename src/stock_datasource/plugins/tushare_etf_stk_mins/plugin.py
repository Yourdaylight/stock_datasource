"""TuShare ETF stk_mins data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareETFStkMinsPlugin(BasePlugin):
    """TuShare ETF stk_mins data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_etf_stk_mins"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare ETF分钟数据 from stk_mins API"
    
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
        """Extract ETF stk_mins data from TuShare.
        
        Args:
            ts_code: ETF代码 (可选，不指定则获取所有ETF)
            freq: 分钟频度 1min/5min/15min/30min/60min (默认1min)
            start_date: 开始时间 格式：YYYY-MM-DD HH:MM:SS
            end_date: 结束时间 格式：YYYY-MM-DD HH:MM:SS
        """
        ts_code = kwargs.get('ts_code')
        freq = kwargs.get('freq', '1min')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        # If ts_code is specified, fetch only that ETF
        if ts_code:
            self.logger.info(f"Extracting ETF stk_mins data: ts_code={ts_code}, freq={freq}")
            data = extractor.extract(
                ts_code=ts_code,
                freq=freq,
                start_date=start_date,
                end_date=end_date
            )
        else:
            # Batch mode: fetch all ETF codes from database
            etf_codes = self._get_etf_codes()
            if not etf_codes:
                self.logger.warning("No ETF codes found in database. Please run tushare_etf_basic first.")
                return pd.DataFrame()
            
            self.logger.info(f"Batch extracting ETF stk_mins data for {len(etf_codes)} ETFs, freq={freq}")
            
            all_data = []
            success_count = 0
            error_count = 0
            
            for i, code in enumerate(etf_codes):
                try:
                    self.logger.info(f"[{i+1}/{len(etf_codes)}] Extracting {code}")
                    df = extractor.extract(
                        ts_code=code,
                        freq=freq,
                        start_date=start_date,
                        end_date=end_date
                    )
                    if not df.empty:
                        all_data.append(df)
                        success_count += 1
                        self.logger.info(f"  -> Got {len(df)} records")
                    else:
                        self.logger.info(f"  -> No data")
                except Exception as e:
                    error_count += 1
                    self.logger.warning(f"  -> Failed: {e}")
            
            self.logger.info(f"Batch extraction complete: {success_count} success, {error_count} errors")
            data = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        
        if data.empty:
            self.logger.warning("No ETF stk_mins data found")
            return pd.DataFrame()
        
        # Add freq column if not present
        if 'freq' not in data.columns:
            data['freq'] = freq
        
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data)} ETF stk_mins records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate ETF stk_mins data."""
        if data.empty:
            self.logger.warning("Empty ETF stk_mins data")
            return False
        
        required_columns = ['ts_code', 'trade_time', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        null_times = data['trade_time'].isnull().sum()
        
        if null_ts_codes > 0 or null_times > 0:
            self.logger.error(f"Found null values: ts_code={null_ts_codes}, trade_time={null_times}")
            return False
        
        # Validate price relationships (high >= low)
        if 'high' in data.columns and 'low' in data.columns:
            invalid_prices = data[data['high'] < data['low']]
            if len(invalid_prices) > 0:
                self.logger.warning(f"Found {len(invalid_prices)} records with high < low")
        
        self.logger.info(f"ETF stk_mins data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Convert trade_time column
        if 'trade_time' in data.columns:
            data['trade_time'] = pd.to_datetime(data['trade_time'])
        
        # Convert numeric columns
        numeric_columns = ['open', 'high', 'low', 'close', 'vol', 'amount']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} ETF stk_mins records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return ["tushare_etf_basic"]
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load ETF stk_mins data into ODS table.
        
        Args:
            data: ETF stk_mins data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_etf_stk_mins")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert('ods_etf_stk_mins', ods_data)
            
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_etf_stk_mins', ods_data, settings=settings)
            
            results['tables_loaded'].append({
                'table': 'ods_etf_stk_mins',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_etf_stk_mins")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare ETF Stk Mins Plugin")
    parser.add_argument("--ts-code", help="ETF code (optional, fetch all if not specified)")
    parser.add_argument("--freq", default="1min", choices=["1min", "5min", "15min", "30min", "60min"], help="Frequency")
    parser.add_argument("--start-date", help="Start time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--end-date", help="End time (YYYY-MM-DD HH:MM:SS)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareETFStkMinsPlugin()
    
    # Run pipeline
    result = plugin.run(
        ts_code=args.ts_code,
        freq=args.freq,
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
