"""TuShare rt_k plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from .extractor import RtKExtractor


class TuShareRtKPlugin(BasePlugin):
    """TuShare rt_k plugin - 沪深京实时日线."""
    
    @property
    def name(self) -> str:
        return "tushare_rt_k"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare realtime daily K-line from rt_k API"
    
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
        """Extract realtime K-line data from TuShare.
        
        Args:
            ts_code: Stock code or pattern (e.g., '600000.SH', '3*.SZ')
            market: Market key (SH_MAIN/SH_KCB/SZ_MAIN/SZ_CYB/BJ)
        """
        ts_code = kwargs.get('ts_code')
        market = kwargs.get('market')
        
        self.logger.info(f"Extracting rt_k data (ts_code={ts_code}, market={market})")
        
        extractor = RtKExtractor()
        
        if ts_code:
            data = extractor.extract(ts_code=ts_code)
        elif market:
            data = extractor.extract_by_market(market=market)
        else:
            # Default: extract all markets
            data = extractor.extract_all_markets()
        
        if data.empty:
            self.logger.warning("No rt_k data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} rt_k records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate realtime K-line data."""
        if data.empty:
            self.logger.warning("Empty rt_k data")
            return False
        
        required_columns = ['ts_code', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        self.logger.info(f"rt_k data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Add system columns
        data['version'] = int(datetime.now().timestamp())
        data['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Transformed {len(data)} rt_k records")
        return data
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies."""
        return []
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load realtime K-line data into ODS table.
        
        Args:
            data: rt_k data to load
        
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
            table_name = "ods_rt_k"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            
            # Prepare data types
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
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Realtime K-line Plugin")
    parser.add_argument("--ts-code", type=str, help="Stock code or pattern (e.g., 600000.SH, 3*.SZ)")
    parser.add_argument("--market", type=str, 
                       choices=["SH_MAIN", "SH_KCB", "SZ_MAIN", "SZ_CYB", "BJ"],
                       help="Market key")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareRtKPlugin()
    
    # Build kwargs
    kwargs = {}
    if args.ts_code:
        kwargs["ts_code"] = args.ts_code
    if args.market:
        kwargs["market"] = args.market
    
    # Run pipeline
    result = plugin.run(**kwargs)
    
    # Print result
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
