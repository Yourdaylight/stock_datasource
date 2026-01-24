"""TuShare ths_member data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareThsMemberPlugin(BasePlugin):
    """TuShare ths_member data plugin (同花顺概念成分)."""
    
    @property
    def name(self) -> str:
        return "tushare_ths_member"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare THS concept members (同花顺概念板块成分股)"
    
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
        return PluginCategory.REFERENCE
    
    def get_role(self) -> PluginRole:
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        return ["tushare_ths_index"]
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        ts_code = kwargs.get('ts_code')
        code = kwargs.get('code')
        
        if not ts_code:
            raise ValueError("ts_code is required")
        
        return extractor.extract(ts_code, code)
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return data
        
        # Convert date columns
        for col in ['in_date', 'out_date']:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        # Convert weight to numeric
        if 'weight' in data.columns:
            data['weight'] = pd.to_numeric(data['weight'], errors='coerce')
        
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
        required_columns = ['ts_code', 'code']
        return all(col in data.columns for col in required_columns)
