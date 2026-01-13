"""TuShare top institutional seats data plugin implementation."""

import pandas as pd
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareTopInstPlugin(BasePlugin):
    """TuShare top institutional seats (机构席位) data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_top_inst"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare top institutional seats (机构席位) data"
    
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
        """Extract institutional seats data from TuShare."""
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        
        if not trade_date:
            raise ValueError("trade_date is required")
        
        self.logger.info(f"Extracting institutional seats data for {trade_date}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(trade_date, ts_code)
        
        if data.empty:
            self.logger.warning(f"No institutional seats data found for {trade_date}")
            return pd.DataFrame()
        
        # Data validation and cleaning
        data = self._validate_and_clean_data(data)
        
        self.logger.info(f"Successfully extracted {len(data)} institutional seats records for {trade_date}")
        return data
    
    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean the extracted data."""
        if data.empty:
            return data
        
        # Convert trade_date to proper date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        # Ensure numeric columns are properly typed
        numeric_columns = ['buy', 'buy_rate', 'sell', 'sell_rate', 'net_buy']
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Remove rows with invalid ts_code or exalter
        if 'ts_code' in data.columns:
            data = data[data['ts_code'].notna() & (data['ts_code'] != '')]
        
        if 'exalter' in data.columns:
            data = data[data['exalter'].notna() & (data['exalter'] != '')]
        
        return data
    
    def _classify_seat_type(self, exalter: str) -> str:
        """Classify seat type based on exalter name."""
        if pd.isna(exalter) or exalter == '':
            return 'unknown'
        
        exalter = str(exalter).strip()
        
        # Institution patterns
        institution_patterns = [
            r'机构专用',
            r'基金专用',
            r'保险专用',
            r'社保基金',
            r'QFII专用',
            r'券商自营',
            r'信托专用',
            r'私募专用'
        ]
        
        for pattern in institution_patterns:
            if re.search(pattern, exalter):
                return 'institution'
        
        # Hot money patterns (游资)
        hot_money_patterns = [
            r'营业部',
            r'证券.*营业部',
            r'.*路.*营业部',
            r'.*街.*营业部',
            r'.*区.*营业部'
        ]
        
        for pattern in hot_money_patterns:
            if re.search(pattern, exalter):
                return 'hot_money'
        
        return 'unknown'
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform the extracted data."""
        if data.empty:
            return data
        
        # Add seat type classification
        if 'exalter' in data.columns:
            data['seat_type'] = data['exalter'].apply(self._classify_seat_type)
        else:
            data['seat_type'] = 'unknown'
        
        # Add version column for idempotency
        data['version'] = int(datetime.now().timestamp())
        
        # Ensure all required columns exist
        schema = self.get_schema()
        required_columns = [col['name'] for col in schema['columns'] 
                          if not col.get('default') and col['name'] not in ['version', '_ingested_at']]
        
        for col in required_columns:
            if col not in data.columns:
                if col in ['buy', 'buy_rate', 'sell', 'sell_rate', 'net_buy']:
                    data[col] = None
                elif col == 'seat_type':
                    data[col] = 'unknown'
                else:
                    data[col] = ''
        
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate the transformed data."""
        if data.empty:
            self.logger.warning("Data is empty")
            return False
        
        # Check required columns
        required_columns = ['trade_date', 'ts_code', 'exalter']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in required columns
        for col in required_columns:
            if data[col].isnull().any():
                self.logger.error(f"Found null values in required column: {col}")
                return False
        
        # Validate ts_code format
        invalid_codes = data[~data['ts_code'].str.match(r'^\d{6}\.(SZ|SH)$', na=False)]
        if not invalid_codes.empty:
            self.logger.warning(f"Found {len(invalid_codes)} records with invalid ts_code format")
        
        # Validate seat_type values
        valid_seat_types = ['institution', 'hot_money', 'unknown']
        invalid_seat_types = data[~data['seat_type'].isin(valid_seat_types)]
        if not invalid_seat_types.empty:
            self.logger.error(f"Found {len(invalid_seat_types)} records with invalid seat_type")
            return False
        
        self.logger.info(f"Data validation passed for {len(data)} records")
        return True