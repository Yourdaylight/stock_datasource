"""TuShare index factor pro plugin implementation."""

import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareIdxFactorProPlugin(BasePlugin):
    """TuShare index factor pro data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_idx_factor_pro"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare index factor pro data (100+ technical indicators)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 30)
    
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
        return PluginRole.DERIVED
    
    def get_dependencies(self) -> List[str]:
        """Get plugin dependencies.
        
        This plugin depends on tushare_index_basic to provide the list of index codes.
        """
        return ["tushare_index_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Get optional plugin dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract index factor pro data from TuShare."""
        trade_date = kwargs.get('trade_date')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        ts_code = kwargs.get('ts_code')
        
        if not any([trade_date, start_date, ts_code]):
            raise ValueError("At least one of trade_date, start_date, or ts_code is required")
        
        self.logger.info(f"Extracting index factor pro data")
        
        # Use of plugin's extractor instance
        data = extractor.extract(trade_date=trade_date, start_date=start_date, 
                               end_date=end_date, ts_code=ts_code)
        
        if data.empty:
            self.logger.warning("No index factor pro data found")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} index factor pro records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate index factor pro data."""
        if data.empty:
            self.logger.warning("Empty index factor pro data")
            return False
        
        required_columns = ['ts_code', 'trade_date', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        # Validate price relationships (OHLC)
        if all(col in data.columns for col in ['high', 'low', 'close']):
            invalid_prices = data[
                (data['high'] < data['low']) |
                (data['high'] < data['close']) |
                (data['low'] > data['close'])
            ]
            
            if len(invalid_prices) > 0:
                self.logger.warning(f"Found {len(invalid_prices)} records with invalid price relationships")
                # Don't reject, just warn as technical factors might have edge cases
        
        self.logger.info(f"Index factor pro data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        # Ensure proper data types for numeric columns
        numeric_columns = [
            'open', 'high', 'low', 'close', 'pre_close', 'change', 'pct_change', 
            'vol', 'amount', 'asi_bfq', 'asit_bfq', 'atr_bfq', 'bbi_bfq',
            'bias1_bfq', 'bias2_bfq', 'bias3_bfq', 'boll_lower_bfq', 'boll_mid_bfq',
            'boll_upper_bfq', 'brar_ar_bfq', 'brar_br_bfq', 'cci_bfq', 'cr_bfq',
            'dfma_dif_bfq', 'dfma_difma_bfq', 'dmi_adx_bfq', 'dmi_adxr_bfq',
            'dmi_mdi_bfq', 'dmi_pdi_bfq', 'downdays', 'updays', 'dpo_bfq',
            'madpo_bfq', 'ema_bfq_5', 'ema_bfq_10', 'ema_bfq_20', 'ema_bfq_30',
            'ema_bfq_60', 'ema_bfq_90', 'ema_bfq_250', 'emv_bfq', 'maemv_bfq',
            'expma_12_bfq', 'expma_50_bfq', 'kdj_bfq', 'kdj_d_bfq', 'kdj_k_bfq',
            'ktn_down_bfq', 'ktn_mid_bfq', 'ktn_upper_bfq', 'lowdays', 'topdays',
            'ma_bfq_5', 'ma_bfq_10', 'ma_bfq_20', 'ma_bfq_30', 'ma_bfq_60',
            'ma_bfq_90', 'ma_bfq_250', 'macd_bfq', 'macd_dea_bfq', 'macd_dif_bfq',
            'mass_bfq', 'ma_mass_bfq', 'mfi_bfq', 'mtm_bfq', 'mtmma_bfq',
            'obv_bfq', 'psy_bfq', 'psyma_bfq', 'roc_bfq', 'maroc_bfq',
            'rsi_bfq_6', 'rsi_bfq_12', 'rsi_bfq_24', 'taq_down_bfq', 'taq_mid_bfq',
            'taq_up_bfq', 'trix_bfq', 'trma_bfq', 'vr_bfq', 'wr_bfq', 'wr1_bfq',
            'xsii_td1_bfq', 'xsii_td2_bfq', 'xsii_td3_bfq', 'xsii_td4_bfq'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date format
        if 'trade_date' in data.columns:
            data['trade_date'] = pd.to_datetime(data['trade_date'], format='%Y%m%d').dt.date
        
        self.logger.info(f"Transformed {len(data)} index factor pro records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load index factor pro data into ODS table.
        
        Args:
            data: Index factor pro data to load
        
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
            # Load into ODS table
            self.logger.info(f"Loading {len(data)} records into ods_idx_factor_pro")
            ods_data = data.copy()
            ods_data = self._add_system_columns(ods_data)
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_idx_factor_pro', ods_data)
            self.db.insert_dataframe('ods_idx_factor_pro', ods_data)
            
            results['tables_loaded'].append({
                'table': 'ods_idx_factor_pro',
                'records': len(ods_data)
            })
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into ods_idx_factor_pro")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    """Allow plugin to be executed as a standalone script."""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Index Factor Pro Plugin")
    parser.add_argument("--date", required=False, help="Trade date in YYYYMMDD format")
    parser.add_argument("--start-date", required=False, help="Start date in YYYYMMDD format")
    parser.add_argument("--end-date", required=False, help="End date in YYYYMMDD format")
    parser.add_argument("--ts-code", required=False, help="Index code (e.g., 000300.SH)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize plugin
    plugin = TuShareIdxFactorProPlugin()
    
    # Run pipeline
    kwargs = {}
    if args.date:
        kwargs['trade_date'] = args.date
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    
    result = plugin.run(**kwargs)
    
    # Print result
    print(f"\n{'='*60}")
    print(f"Plugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    print(f"{'='*60}")
    
    for step, step_result in result.get('steps', {}).items():
        status = step_result.get('status', 'unknown')
        records = step_result.get('records', 0)
        print(f"{step:15} : {status:10} ({records} records)")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
