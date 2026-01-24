"""TuShare index weekly data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIndexWeeklyPlugin(BasePlugin):
    """TuShare index weekly data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_index_weekly"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare index weekly price data (指数周线行情)"
    
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
        return PluginCategory.INDEX
    
    def get_role(self) -> PluginRole:
        """Get plugin role."""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        This plugin depends on tushare_index_basic to provide list of index codes.
        """
        return ["tushare_index_basic"]
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract index weekly data from TuShare."""
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if ts_code and start_date and end_date:
            self.logger.info(f"Extracting index weekly data for {ts_code} from {start_date} to {end_date}")
            data = extractor.extract_by_date_range(ts_code, start_date, end_date)
        elif trade_date:
            self.logger.info(f"Extracting index weekly data for {trade_date}")
            data = extractor.extract(trade_date, ts_code)
        else:
            raise ValueError("Either trade_date or (ts_code, start_date, end_date) is required")
        
        if data.empty:
            self.logger.warning(f"No index weekly data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} index weekly records")
        return data
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        if data.empty:
            return data
        
        # Ensure proper data types
        numeric_columns = data.columns.difference(['ts_code', 'trade_date'])
        for col in numeric_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load index weekly data into database.
        
        Args:
            data: Index weekly data to load
        
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
            schema = self.get_schema()
            table_name = schema.get('table_name')
            
            # Load data into table
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            # Add system columns
            data['version'] = int(datetime.now().timestamp())
            data['_ingested_at'] = datetime.now()
            
            # Insert into database
            self.db.insert_dataframe(table_name, data)
            
            results['tables_loaded'].append({
                'table': table_name,
                'records': len(data)
            })
            results['total_records'] = len(data)
            self.logger.info(f"Loaded {len(data)} records into {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate index weekly data."""
        if data.empty:
            self.logger.warning("Empty index weekly data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        for col in required_columns:
            null_count = data[col].isnull().sum()
            if null_count > len(data) * 0.5:  # Allow up to 50% nulls
                self.logger.warning(f"Column {col} has {null_count} null values ({null_count/len(data)*100:.1f}%)")
        
        self.logger.info("Index weekly data validation passed")
        return True
