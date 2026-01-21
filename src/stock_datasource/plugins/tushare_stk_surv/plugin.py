"""TuShare institutional survey data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class TuShareStkSurvPlugin(BasePlugin):
    """TuShare institutional survey (机构调研) data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_stk_surv"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare institutional survey (机构调研) data - 上市公司机构调研记录"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 60)
    
    def get_dependencies(self) -> List[str]:
        """This plugin depends on stock basic info."""
        return ["tushare_stock_basic"]
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract institutional survey data from TuShare.
        
        Supports three modes:
        1. By trade_date: Get all surveys on a specific date
        2. By ts_code: Get all surveys for a specific stock
        3. By date range: Get surveys in a date range (start_date, end_date)
        """
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if ts_code:
            self.logger.info(f"Extracting survey data for stock {ts_code}")
            data = extractor.extract_by_stock(ts_code, start_date, end_date)
        elif trade_date:
            self.logger.info(f"Extracting survey data for date {trade_date}")
            data = extractor.extract_by_date(trade_date)
        elif start_date and end_date:
            self.logger.info(f"Extracting survey data from {start_date} to {end_date}")
            data = extractor.extract_date_range(start_date, end_date)
        else:
            raise ValueError("Must provide trade_date, ts_code, or (start_date, end_date)")
        
        if data.empty:
            self.logger.warning("No survey data found")
            return pd.DataFrame()
        
        data = self._validate_and_clean_data(data)
        self.logger.info(f"Successfully extracted {len(data)} survey records")
        return data
    
    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean the extracted data."""
        if data.empty:
            return data
        
        # Rename surv_date if it comes as trade_date
        if 'trade_date' in data.columns and 'surv_date' not in data.columns:
            data = data.rename(columns={'trade_date': 'surv_date'})
        
        # Convert surv_date to proper date format
        if 'surv_date' in data.columns:
            data['surv_date'] = pd.to_datetime(data['surv_date'], format='%Y%m%d').dt.date
        
        # Remove rows with invalid ts_code
        if 'ts_code' in data.columns:
            data = data[data['ts_code'].notna() & (data['ts_code'] != '')]
        
        # Fill missing string columns with empty string
        string_columns = ['name', 'fund_visitors', 'rece_place', 'rece_mode', 
                         'rece_org', 'org_type', 'comp_rece', 'content']
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
                data[col] = ''
        
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate the transformed data."""
        if data.empty:
            self.logger.warning("Data is empty")
            return False
        
        # Check required columns
        required_columns = ['surv_date', 'ts_code']
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
        invalid_codes = data[~data['ts_code'].str.match(r'^\d{6}\.(SZ|SH|BJ)$', na=False)]
        if not invalid_codes.empty:
            self.logger.warning(f"Found {len(invalid_codes)} records with invalid ts_code format")
        
        self.logger.info(f"Data validation passed for {len(data)} records")
        return True
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load institutional survey data into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            self.logger.info(f"Loading {len(data)} records into ods_stk_surv")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_stk_surv', ods_data)
            
            # Insert data
            self.db.insert_dataframe('ods_stk_surv', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records into ods_stk_surv")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": "ods_stk_surv"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
