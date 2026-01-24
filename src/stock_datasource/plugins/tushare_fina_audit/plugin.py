"""TuShare financial audit opinion data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareFinaAuditPlugin(BasePlugin):
    """TuShare financial audit opinion data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_fina_audit"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare financial audit opinion data"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 120)
    
    def get_category(self) -> PluginCategory:
        """Return plugin category."""
        return PluginCategory.CN_STOCK
    
    def get_role(self) -> PluginRole:
        """Return plugin role."""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Return plugin dependencies."""
        return ["tushare_stock_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Return optional dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract financial audit opinion data from TuShare.
        
        Args:
            ts_code: Stock code (required, e.g., 600000.SH)
            ann_date: Announcement date in YYYYMMDD format
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            period: Report period (e.g., 20231231)
            trade_date: Trading date for batch mode
        """
        ts_code = kwargs.get('ts_code')
        ann_date = kwargs.get('ann_date')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        period = kwargs.get('period')
        trade_date = kwargs.get('trade_date')  # For batch mode
        
        # Batch mode: extract for all stocks if ts_code not provided
        if not ts_code:
            if not self.db:
                raise ValueError("Database not initialized for batch mode")
            
            self.logger.info("Extracting financial audit data for all stocks (batch mode)")
            
            # Get all stock codes from stock_basic table
            stocks_query = "SELECT DISTINCT ts_code FROM ods_stock_basic WHERE list_status = 'L'"
            stocks_df = self.db.execute_query(stocks_query)
            
            if stocks_df.empty:
                self.logger.warning("No stocks found in stock_basic table")
                return pd.DataFrame()
            
            all_data = []
            for idx, row in stocks_df.iterrows():
                stock_code = row['ts_code']
                try:
                    self.logger.info(f"Extracting financial audit data for {stock_code} ({idx+1}/{len(stocks_df)})")
                    
                    # Use trade_date as end_date if provided, otherwise use current date
                    if trade_date:
                        stock_end_date = trade_date.replace('-', '')
                    else:
                        stock_end_date = end_date
                    
                    data = extractor.extract(
                        ts_code=stock_code,
                        ann_date=ann_date,
                        start_date=start_date,
                        end_date=stock_end_date,
                        period=period
                    )
                    
                    if not data.empty:
                        all_data.append(data)
                    
                    # Rate limiting between API calls
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract financial audit for {stock_code}: {e}")
                    continue
            
            if not all_data:
                self.logger.warning("No financial audit data extracted for any stock")
                return pd.DataFrame()
            
            combined_data = pd.concat(all_data, ignore_index=True)
            # Add system columns for batch mode
            combined_data['version'] = int(datetime.now().timestamp())
            combined_data['_ingested_at'] = datetime.now()
            self.logger.info(f"Extracted {len(combined_data)} financial audit records from {len(all_data)} stocks")
            return combined_data
        
        # Single stock mode
        self.logger.info(f"Extracting financial audit data for {ts_code}")
        
        data = extractor.extract(
            ts_code=ts_code,
            ann_date=ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period
        )
        
        if data.empty:
            self.logger.warning(f"No financial audit data found for {ts_code}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} financial audit records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate financial audit data."""
        if data.empty:
            self.logger.warning("Empty financial audit data")
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
        
        null_end_dates = data['end_date'].isnull().sum()
        if null_end_dates > 0:
            self.logger.error(f"Found {null_end_dates} null end_date values")
            return False
        
        self.logger.info(f"Financial audit data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform financial audit data for database insertion."""
        # Numeric columns from financial audit
        numeric_columns = ['audit_fees']
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date columns
        date_columns = ['end_date', 'ann_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        self.logger.info(f"Transformed {len(data)} financial audit records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load financial audit data into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            self.logger.info(f"Loading {len(data)} records into ods_fina_audit")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_fina_audit', ods_data)
            self.db.insert_dataframe('ods_fina_audit', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": "ods_fina_audit"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Financial Audit Opinion Data Plugin")
    parser.add_argument("--ts-code", required=True, help="Stock code (e.g., 600000.SH)")
    parser.add_argument("--ann-date", help="Announcement date in YYYYMMDD format")
    parser.add_argument("--start-date", help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", help="End date in YYYYMMDD format")
    parser.add_argument("--period", help="Report period (e.g., 20231231)")
    
    args = parser.parse_args()
    
    plugin = TuShareFinaAuditPlugin()
    result = plugin.run(
        ts_code=args.ts_code,
        ann_date=args.ann_date,
        start_date=args.start_date,
        end_date=args.end_date,
        period=args.period
    )
    
    print(f"\nPlugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
