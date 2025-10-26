"""AKShare Hong Kong daily data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class AKShareHKDailyPlugin(BasePlugin):
    """AKShare Hong Kong daily data plugin."""
    
    @property
    def name(self) -> str:
        return "akshare_hk_daily"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "AKShare Hong Kong daily data from hk_daily API"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 60)
    
    def get_schema(self) -> Dict[str, Any]:
        """Get table schema from separate JSON file."""
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract Hong Kong daily data from AKShare."""
        symbol = kwargs.get('symbol')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if not symbol:
            raise ValueError("symbol is required")
        
        self.logger.info(f"Extracting Hong Kong daily data for {symbol}")
        
        # Use the plugin's extractor instance
        data = extractor.extract(symbol, start_date, end_date)
        
        if data.empty:
            self.logger.warning(f"No Hong Kong daily data found for {symbol}")
            return pd.DataFrame()
        
        # Map AKShare columns to our schema
        # AKShare returns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        data_mapped = pd.DataFrame()
        data_mapped['symbol'] = symbol
        data_mapped['trade_date'] = pd.to_datetime(data['日期']).dt.date
        data_mapped['open'] = pd.to_numeric(data['开盘'], errors='coerce')
        data_mapped['high'] = pd.to_numeric(data['最高'], errors='coerce')
        data_mapped['low'] = pd.to_numeric(data['最低'], errors='coerce')
        data_mapped['close'] = pd.to_numeric(data['收盘'], errors='coerce')
        data_mapped['volume'] = pd.to_numeric(data['成交量'], errors='coerce').astype('Int64')
        data_mapped['amount'] = pd.to_numeric(data['成交额'], errors='coerce')
        
        # Ensure proper data types and add system columns
        data_mapped['version'] = int(datetime.now().timestamp())
        data_mapped['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data_mapped)} Hong Kong daily records for {symbol}")
        return data_mapped
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate Hong Kong daily data."""
        if data.empty:
            self.logger.warning("Empty Hong Kong daily data")
            return False
        
        required_columns = ['symbol', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_symbols = data['symbol'].isnull().sum()
        null_dates = data['trade_date'].isnull().sum()
        null_close = data['close'].isnull().sum()
        
        if null_symbols > 0 or null_dates > 0:
            self.logger.error(f"Found null values: symbol={null_symbols}, trade_date={null_dates}")
            return False
        
        self.logger.info(f"Hong Kong daily data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} Hong Kong daily records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load Hong Kong daily data into ODS table.
        
        Args:
            data: Hong Kong daily data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_hk_daily")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_hk_daily', ods_data)
            
            # Add ClickHouse settings for large inserts
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_hk_daily', ods_data, settings=settings)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_hk_daily")
            return {
                "status": "success",
                "table": "ods_hk_daily",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
