"""AKShare Hong Kong stock list plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import extractor


class AKShareHKStockListPlugin(BasePlugin):
    """AKShare Hong Kong stock list plugin."""
    
    @property
    def name(self) -> str:
        return "akshare_hk_stock_list"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "AKShare Hong Kong stock list from hk_stock_list API"
    
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
        """Extract Hong Kong stock list from AKShare."""
        self.logger.info("Extracting Hong Kong stock list")
        
        # Use the plugin's extractor instance
        data = extractor.extract()
        
        if data.empty:
            self.logger.warning("No Hong Kong stock list data found")
            return pd.DataFrame()
        
        # Map AKShare columns to our schema
        # AKShare returns: 序号, 代码, 名称, 最新价, 涨跌额, 涨跌幅, 今开, 最高, 最低, 昨收, 成交量, 成交额
        data_mapped = pd.DataFrame()
        data_mapped['symbol'] = data['代码']
        data_mapped['name'] = data['名称']
        data_mapped['code'] = data['代码']
        data_mapped['market'] = 'HK'
        
        # Ensure proper data types and add system columns
        data_mapped['version'] = int(datetime.now().timestamp())
        data_mapped['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(data_mapped)} Hong Kong stock records")
        return data_mapped
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate Hong Kong stock list data."""
        if data.empty:
            self.logger.warning("Empty Hong Kong stock list data")
            return False
        
        required_columns = ['symbol', 'name']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_symbols = data['symbol'].isnull().sum()
        null_names = data['name'].isnull().sum()
        
        if null_symbols > 0 or null_names > 0:
            self.logger.error(f"Found null values: symbol={null_symbols}, name={null_names}")
            return False
        
        self.logger.info(f"Hong Kong stock list data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Data is already properly formatted in extract_data
        self.logger.info(f"Transformed {len(data)} Hong Kong stock records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load Hong Kong stock list data into ODS table.
        
        Args:
            data: Hong Kong stock list data to load
        
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
            self.logger.info(f"Loading {len(data)} records into ods_hk_stock_list")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_hk_stock_list', ods_data)
            
            # Add ClickHouse settings for large inserts
            settings = {
                'max_partitions_per_insert_block': 1000
            }
            self.db.insert_dataframe('ods_hk_stock_list', ods_data, settings=settings)
            
            self.logger.info(f"Loaded {len(ods_data)} records into ods_hk_stock_list")
            return {
                "status": "success",
                "table": "ods_hk_stock_list",
                "loaded_records": len(ods_data)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}
