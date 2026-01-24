"""TuShare index classify data plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIndexClassifyPlugin(BasePlugin):
    """TuShare index classify data plugin (申万行业分类)."""
    
    @property
    def name(self) -> str:
        return "tushare_index_classify"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare industry classification data (申万行业分类)"
    
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
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        level = kwargs.get('level')
        src = kwargs.get('src', 'SW2021')
        
        if level:
            data = extractor.extract(level=level, src=src)
        else:
            # Extract all levels
            data = extractor.extract_all_levels(src=src)
        
        return data
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return data
        
        # Ensure src column exists
        if 'src' not in data.columns:
            data['src'] = 'SW2021'
        
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
        required_columns = ['index_code', 'industry_name', 'level']
        return all(col in data.columns for col in required_columns)
