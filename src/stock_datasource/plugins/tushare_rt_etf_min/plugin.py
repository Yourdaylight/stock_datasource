"""TuShare rt_etf_min plugin - ETF实时分钟K线."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import RtEtfMinExtractor


class TuShareRtEtfMinPlugin(BasePlugin):
    """TuShare rt_etf_min plugin - ETF实时分钟K线数据."""
    
    @property
    def name(self) -> str:
        return "tushare_rt_etf_min"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare ETF实时分钟K线 from rt_min API"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 120)
    
    def get_category(self) -> PluginCategory:
        return PluginCategory.ETF_FUND
    
    def get_role(self) -> PluginRole:
        return PluginRole.PRIMARY
    
    def get_schema(self) -> Dict[str, Any]:
        schema_file = Path(__file__).parent / "schema.json"
        with open(schema_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract realtime minute K-line data for ETFs.
        
        Args:
            ts_code: ETF code(s), comma-separated for multiple
            freq: K-line frequency (1MIN/5MIN/15MIN/30MIN/60MIN), default 1MIN
            ts_codes: List of ETF codes for batch extraction
        """
        ts_code = kwargs.get('ts_code')
        ts_codes = kwargs.get('ts_codes')
        freq = kwargs.get('freq', '1MIN')
        
        self.logger.info(f"Extracting rt_etf_min data (ts_code={ts_code}, freq={freq})")
        
        extractor = RtEtfMinExtractor()
        
        if ts_codes:
            data = extractor.extract_batch(ts_codes, freq)
        elif ts_code:
            data = extractor.extract(ts_code, freq)
        else:
            self.logger.warning("No ts_code or ts_codes provided")
            return pd.DataFrame()
        
        if data.empty:
            self.logger.warning("No rt_etf_min data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} rt_etf_min records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        if data.empty:
            self.logger.warning("Empty rt_etf_min data")
            return False
        
        required_columns = ['ts_code', 'trade_time']
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            self.logger.error(f"Missing required columns: {missing}")
            return False
        
        null_ts = data['ts_code'].isnull().sum()
        if null_ts > 0:
            self.logger.error(f"Found {null_ts} null ts_code values")
            return False
        
        self.logger.info(f"rt_etf_min data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        self.logger.info(f"Transformed {len(data)} rt_etf_min records")
        return data
    
    def get_dependencies(self) -> List[str]:
        return []
    
    def get_optional_dependencies(self) -> List[str]:
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            table_name = "ods_rt_etf_min"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            ods_data = self._prepare_data_for_insert(table_name, data)
            self.db.insert_dataframe(table_name, ods_data)
            
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            return {
                "status": "success",
                "table": table_name,
                "loaded_records": len(ods_data)
            }
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare ETF实时分钟K线 Plugin")
    parser.add_argument("--ts-code", type=str, required=True, help="ETF code(s), e.g. 589960.SH or 589960.SH,159100.SZ")
    parser.add_argument("--freq", type=str, default="1MIN", choices=["1MIN", "5MIN", "15MIN", "30MIN", "60MIN"])
    parser.add_argument("--verbose", action="store_true")
    
    args = parser.parse_args()
    
    plugin = TuShareRtEtfMinPlugin()
    result = plugin.run(ts_code=args.ts_code, freq=args.freq)
    
    print(f"\n{'='*60}")
    print(f"Plugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    print(f"{'='*60}")
    
    for step, step_result in result.get('steps', {}).items():
        status = step_result.get('status', 'unknown')
        records = step_result.get('records', step_result.get('loaded_records', 0))
        print(f"{step:15} : {status:10} ({records} records)")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    sys.exit(0)
