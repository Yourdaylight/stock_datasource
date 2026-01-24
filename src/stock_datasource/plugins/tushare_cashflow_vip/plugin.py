"""TuShare cash flow VIP data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareCashflowVipPlugin(BasePlugin):
    """TuShare cash flow VIP data plugin (batch mode)."""
    
    @property
    def name(self) -> str:
        return "tushare_cashflow_vip"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare cash flow VIP data (batch mode, requires 5000 points)"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 120)
    
    def get_category(self) -> PluginCategory:
        """Return plugin category."""
        return PluginCategory.CN_STOCK
    
    def get_role(self) -> PluginRole:
        """Return plugin role."""
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        """Return plugin dependencies."""
        return ["tushare_stock_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        """Return optional dependencies."""
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract cash flow VIP data from TuShare.
        
        VIP API supports batch extraction by period.
        
        Args:
            ts_code: Stock code (optional, e.g., 600000.SH)
            ann_date: Announcement date in YYYYMMDD format
            f_ann_date: First announcement date in YYYYMMDD format
            start_date: Announcement start date in YYYYMMDD format
            end_date: Announcement end date in YYYYMMDD format
            period: Report period (e.g., 20231231) - main batch parameter
            report_type: Report type (1=合并报表, 2=单季合并, etc.)
            comp_type: Company type (1=工商业, 2=银行, 3=保险, 4=证券)
            is_calc: Whether calculated statement (0=actual, 1=calculated)
        """
        ts_code = kwargs.get('ts_code')
        ann_date = kwargs.get('ann_date')
        f_ann_date = kwargs.get('f_ann_date')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        period = kwargs.get('period')
        report_type = kwargs.get('report_type', '1')  # Default to consolidated statement
        comp_type = kwargs.get('comp_type')
        is_calc = kwargs.get('is_calc')
        
        self.logger.info(f"Extracting cash flow VIP data (period={period}, report_type={report_type})")
        
        data = extractor.extract(
            ts_code=ts_code,
            ann_date=ann_date,
            f_ann_date=f_ann_date,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type,
            comp_type=comp_type,
            is_calc=is_calc
        )
        
        if data.empty:
            self.logger.warning(f"No cash flow VIP data found for period={period}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} cash flow VIP records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate cash flow data."""
        if data.empty:
            self.logger.warning("Empty cash flow data")
            return False
        
        required_columns = ['ts_code', 'end_date']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        # Check for null values in key fields
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        null_end_dates = data['end_date'].isnull().sum()
        if null_end_dates > 0:
            self.logger.error(f"Found {null_end_dates} null end_date values")
            return False
        
        self.logger.info(f"Cash flow VIP data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform cash flow data for database insertion."""
        # Get all columns except string columns for numeric conversion
        string_columns = ['ts_code', 'ann_date', 'f_ann_date', 'end_date', 
                         'report_type', 'comp_type', 'end_type', 'update_flag']
        
        # Convert numeric columns
        for col in data.columns:
            if col not in string_columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # Convert date columns
        date_columns = ['end_date', 'ann_date', 'f_ann_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        self.logger.info(f"Transformed {len(data)} cash flow VIP records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load cash flow data into ODS table (same as base cashflow)."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            # VIP data goes to same table as base cash flow
            self.logger.info(f"Loading {len(data)} records into ods_cash_flow")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            # Prepare data types
            ods_data = self._prepare_data_for_insert('ods_cash_flow', ods_data)
            self.db.insert_dataframe('ods_cash_flow', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": "ods_cash_flow"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Cash Flow VIP Data Plugin")
    parser.add_argument("--period", required=True, help="Report period (e.g., 20231231)")
    parser.add_argument("--report-type", default="1", help="Report type (1=合并报表)")
    parser.add_argument("--ts-code", help="Stock code (optional)")
    
    args = parser.parse_args()
    
    plugin = TuShareCashflowVipPlugin()
    result = plugin.run(
        period=args.period,
        report_type=args.report_type,
        ts_code=args.ts_code
    )
    
    print(f"\nPlugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
