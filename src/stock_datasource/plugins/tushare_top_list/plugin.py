"""TuShare top list data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareTopListPlugin(BasePlugin):
    """TuShare top list (龙虎榜) data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_top_list"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare top list (龙虎榜) data"
    
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
        """Extract top list data from TuShare."""
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting top list data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract_top_list(trade_date, ts_code)
        
        if data.empty:
            self.logger.warning(f"No top list data found for {trade_date}")
            return pd.DataFrame()
        
        # Data validation and cleaning
        data = self._validate_and_clean_data(data)
        
        self.logger.info(f"Successfully extracted {len(data)} top list records for {trade_date}")
        return data
    
    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean the extracted data."""
        if data.empty:
            return data
        
        # Convert trade_date to proper date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Ensure numeric columns are properly typed
        numeric_columns = [
            'close', 'pct_chg', 'turnover_rate', 'amount', 
            'l_sell', 'l_buy', 'l_amount', 'net_amount', 
            'net_rate', 'amount_rate', 'float_values'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Remove rows with invalid ts_code
        if 'ts_code' in data.columns:
            data = data[data['ts_code'].notna() & (data['ts_code'] != '')]
        
        # Fill missing string columns with empty string
        string_columns = ['name', 'reason']
        for col in string_columns:
            if col in data.columns:
                data[col] = data[col].fillna('')
        
        return data
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform the extracted data."""
        if data.empty:
            return data
        
        # Add version column for idempotency
        data['version'] = int(datetime.now().timestamp())
        
        # Ensure all required columns exist
        schema = self.get_schema()
        required_columns = [col['name'] for col in schema['columns'] 
                          if not col.get('default') and col['name'] not in ['version', '_ingested_at']]
        
        for col in required_columns:
            if col not in data.columns:
                if col in ['close', 'pct_chg', 'turnover_rate', 'amount', 
                          'l_sell', 'l_buy', 'l_amount', 'net_amount', 
                          'net_rate', 'amount_rate', 'float_values']:
                    data[col] = None
                else:
                    data[col] = ''
        
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate the transformed data."""
        if data.empty:
            self.logger.warning("Data is empty")
            return False
        
        # Check required columns
        required_columns = ['trade_date', 'ts_code']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in required columns
        for col in required_columns:
            if data[col].isnull().any():
                self.logger.error(f"Found null values in required column: {col}")
                return False
        
        # Validate ts_code format (should be like 000001.SZ)
        invalid_codes = data[~data['ts_code'].str.match(r'^\d{6}\.(SZ|SH)$', na=False)]
        if not invalid_codes.empty:
            self.logger.warning(f"Found {len(invalid_codes)} records with invalid ts_code format")
        
        self.logger.info(f"Data validation passed for {len(data)} records")
        return True
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load top list data into ODS table.
        
        Args:
            data: Top list data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_top_list")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_top_list', ods_data)
            
            # Insert data
            self.db.insert_dataframe('ods_top_list', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records into ods_top_list")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": "ods_top_list"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}