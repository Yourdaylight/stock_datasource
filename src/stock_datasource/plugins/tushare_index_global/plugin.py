"""TuShare index global data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIndexGlobalPlugin(BasePlugin):
    """TuShare index global data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_index_global"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare global index daily data (国际指数日线行情)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 500)
    
    def get_schema(self) -> Dict[str, Any]:
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_category(self) -> PluginCategory:
        return PluginCategory.INDEX
    
    def get_role(self) -> PluginRole:
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        trade_date = kwargs.get('trade_date')
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if ts_code and start_date and end_date:
            data = extractor.extract_by_date_range(ts_code, start_date, end_date)
        elif trade_date:
            # Support trade_date for scheduled tasks
            data = extractor.extract(trade_date, ts_code)
        elif start_date and end_date:
            # Support date range without ts_code (fetch all)
            data = extractor.extract_by_date_range(ts_code, start_date, end_date)
        else:
            # For scheduled tasks without parameters, this plugin requires trade_date
            self.logger.warning("No parameters provided, skipping extraction")
            return pd.DataFrame()
        return data
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return data
        numeric_columns = data.columns.difference(['ts_code', 'trade_date'])
        for col in numeric_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        if not self.db:
            return {"status": "failed", "error": "Database not initialized"}
        if data.empty:
            return {"status": "no_data", "loaded_records": 0}
        
        results = {"status": "success", "tables_loaded": [], "total_records": 0}
        try:
            schema = self.get_schema()
            table_name = schema.get('table_name')
            data['version'] = int(datetime.now().timestamp())
            data['_ingested_at'] = datetime.now()
            self.db.insert_dataframe(table_name, data)
            results['tables_loaded'].append({'table': table_name, 'records': len(data)})
            results['total_records'] = len(data)
        except Exception as e:
            results['status'] = 'failed'
            results['error'] = str(e)
        return results
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        if data.empty:
            return False
        required_columns = ['ts_code', 'trade_date', 'close']
        return all(col in data.columns for col in required_columns)
