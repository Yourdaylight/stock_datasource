"""TuShare index member data plugin implementation."""

import logging
import time
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor

logger = logging.getLogger(__name__)


class TuShareIndexMemberPlugin(BasePlugin):
    """TuShare index member data plugin (指数成分股)."""
    
    @property
    def name(self) -> str:
        return "tushare_index_member"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare index member data (指数成分股)"
    
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
        return ["tushare_index_basic"]
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        index_code = kwargs.get('index_code')
        is_new = kwargs.get('is_new')
        
        if index_code:
            return extractor.extract(index_code, is_new)
        
        # Batch mode: iterate over known index codes from ods_index_basic
        self.logger.info("Batch mode: fetching index members for all known indices")
        if not self.db:
            raise ValueError("Database not initialized for batch mode")
        
        indices_df = self.db.execute_query(
            "SELECT DISTINCT ts_code FROM ods_index_basic WHERE ts_code IS NOT NULL LIMIT 200"
        )
        if indices_df.empty:
            self.logger.warning("No index codes found in ods_index_basic")
            return pd.DataFrame()
        
        all_data = []
        total = len(indices_df)
        for i, row in indices_df.iterrows():
            code = row['ts_code']
            try:
                self.logger.info(f"[{i+1}/{total}] Extracting members for {code}")
                data = extractor.extract(code, is_new='Y')
                if not data.empty:
                    all_data.append(data)
                time.sleep(0.15)
            except Exception as e:
                self.logger.warning(f"[{i+1}/{total}] {code}: Failed - {e}")
        
        if not all_data:
            self.logger.warning("No index member data extracted")
            return pd.DataFrame()
        
        combined = pd.concat(all_data, ignore_index=True)
        self.logger.info(f"Extracted {len(combined)} index member records from {len(all_data)} indices")
        return combined
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if data.empty:
            return data
        
        # Convert date columns
        for col in ['in_date', 'out_date']:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
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
        required_columns = ['index_code', 'con_code']
        return all(col in data.columns for col in required_columns)
