"""TuShare HK financial indicators data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json
import time

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareHKFinaIndicatorPlugin(BasePlugin):
    """TuShare HK financial indicators data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_hk_fina_indicator"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare HK financial indicators data"
    
    def get_category(self) -> PluginCategory:
        return PluginCategory.HK_STOCK
    
    def get_role(self) -> PluginRole:
        return PluginRole.DERIVED
    
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
    
    def _get_hk_stock_codes(self) -> List[str]:
        """Get all HK stock codes from ods_hk_stock_list table."""
        try:
            if not self.db:
                self.logger.error("Database not initialized")
                return []
            
            df = self.db.execute_query(
                "SELECT DISTINCT code FROM ods_hk_stock_list ORDER BY code"
            )
            if df.empty:
                self.logger.warning("No HK stock codes found in ods_hk_stock_list")
                return []
            
            codes = df['code'].tolist()
            self.logger.info(f"Found {len(codes)} HK stock codes")
            return codes
        except Exception as e:
            self.logger.error(f"Failed to get HK stock codes: {e}")
            return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract HK financial indicators data from TuShare.
        
        Args:
            ts_code: HK stock code. If not provided, will fetch all HK stocks.
            period: Report period (YYYYMMDD)
            report_type: Report type (Q1/Q2/Q3/Q4)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            max_stocks: Maximum number of stocks to process (for testing)
        """
        ts_code = kwargs.get('ts_code')
        period = kwargs.get('period')
        report_type = kwargs.get('report_type')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        max_stocks = kwargs.get('max_stocks')
        
        if ts_code:
            self.logger.info(f"Extracting HK financial indicators for {ts_code}")
            data = extractor.extract(
                ts_code=ts_code, period=period, report_type=report_type,
                start_date=start_date, end_date=end_date
            )
            
            if data.empty:
                self.logger.warning(f"No data found for {ts_code}")
                return pd.DataFrame()
            
            data['version'] = int(datetime.now().timestamp())
            data['_ingested_at'] = datetime.now()
            self.logger.info(f"Extracted {len(data)} records for {ts_code}")
            return data
        
        # Batch mode: fetch all HK stocks
        self.logger.info("Extracting HK financial indicators for all stocks")
        stock_codes = self._get_hk_stock_codes()
        if not stock_codes:
            self.logger.error("No HK stock codes available")
            return pd.DataFrame()
        
        if max_stocks:
            stock_codes = stock_codes[:max_stocks]
            self.logger.info(f"Limited to first {max_stocks} stocks")
        
        all_data = []
        total = len(stock_codes)
        success_count = 0
        failed_count = 0
        
        for i, code in enumerate(stock_codes, 1):
            try:
                self.logger.info(f"[{i}/{total}] Extracting data for {code}")
                stock_data = extractor.extract(
                    ts_code=code, period=period, report_type=report_type,
                    start_date=start_date, end_date=end_date
                )
                
                if not stock_data.empty:
                    all_data.append(stock_data)
                    success_count += 1
                    self.logger.info(f"[{i}/{total}] {code}: {len(stock_data)} records")
                else:
                    self.logger.debug(f"[{i}/{total}] {code}: No data")
                
                time.sleep(0.1)
                
            except Exception as e:
                failed_count += 1
                self.logger.error(f"[{i}/{total}] {code}: Failed - {e}")
            
            if i % 50 == 0:
                self.logger.info(f"Progress: {i}/{total} (success={success_count}, failed={failed_count})")
        
        if not all_data:
            self.logger.warning("No data found for any HK stocks")
            return pd.DataFrame()
        
        combined = pd.concat(all_data, ignore_index=True)
        combined['version'] = int(datetime.now().timestamp())
        combined['_ingested_at'] = datetime.now()
        
        self.logger.info(f"Extracted {len(combined)} records from {success_count} stocks")
        return combined
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate HK financial indicators data."""
        if data.empty:
            self.logger.warning("Empty data")
            return False
        
        required_columns = ['ts_code', 'end_date']
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            self.logger.error(f"Missing required columns: {missing}")
            return False
        
        if data['ts_code'].isnull().any():
            self.logger.error("Found null ts_code values")
            return False
        
        self.logger.info(f"Validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data for database insertion."""
        numeric_columns = [
            'basic_eps', 'diluted_eps', 'eps_ttm', 'bps', 'per_oi',
            'per_netcash_operate', 'dps_hkd', 'dps_hkd_ly', 'per_shares',
            'operate_income', 'operate_income_yoy', 'operate_income_qoq',
            'gross_profit', 'gross_profit_yoy', 'gross_profit_ratio',
            'holder_profit', 'holder_profit_yoy', 'net_profit_ratio',
            'roe_avg', 'roe_yearly', 'roa', 'roic_yearly',
            'ocf_sales', 'netcash_operate', 'netcash_invest', 'netcash_finance',
            'end_cash', 'accounts_rece_tdays', 'inventory_tdays',
            'current_assets_tdays', 'total_assets_tdays',
            'total_assets', 'total_liabilities', 'debt_asset_ratio',
            'current_ratio', 'equity_multiplier', 'equity_ratio',
            'pe_ttm', 'pb_ttm', 'total_market_cap', 'hksk_market_cap',
            'premium_income', 'net_interest_income', 'fee_commission_income',
            'loan_deposit', 'deposit_assets'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        date_columns = ['end_date', 'ann_date', 'std_report_date', 'report_date_sq']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        # fiscal_year is a numeric month value (e.g., 12.0), not a date
        if 'fiscal_year' in data.columns:
            data['fiscal_year'] = pd.to_numeric(data['fiscal_year'], errors='coerce')
        
        self.logger.info(f"Transformed {len(data)} records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load HK financial indicators data into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            return {"status": "no_data", "loaded_records": 0}
        
        results = {"status": "success", "tables_loaded": [], "total_records": 0}
        
        try:
            table_name = "ods_hk_fina_indicator"
            self.logger.info(f"Loading {len(data)} records into {table_name}")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert(table_name, ods_data)
            # Filter columns to only those in the table schema
            table_schema = self.db.get_table_schema(table_name)
            table_cols = {col['column_name'] for col in table_schema}
            extra_cols = set(ods_data.columns) - table_cols
            if extra_cols:
                self.logger.info(f"Dropping {len(extra_cols)} extra columns not in table: {extra_cols}")
                ods_data = ods_data[[c for c in ods_data.columns if c in table_cols]]
            self.db.insert_dataframe(table_name, ods_data)
            
            results['tables_loaded'].append({'table': table_name, 'records': len(ods_data)})
            results['total_records'] += len(ods_data)
            self.logger.info(f"Loaded {len(ods_data)} records into {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            results['status'] = 'failed'
            results['error'] = str(e)
        
        return results


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare HK Financial Indicators Plugin")
    parser.add_argument("--ts-code", help="HK stock code (e.g., 00700.HK)")
    parser.add_argument("--period", help="Report period (YYYYMMDD)")
    parser.add_argument("--report-type", help="Report type (Q1/Q2/Q3/Q4)")
    parser.add_argument("--start-date", help="Start date (YYYYMMDD)")
    parser.add_argument("--end-date", help="End date (YYYYMMDD)")
    parser.add_argument("--max-stocks", type=int, help="Max stocks to process")
    
    args = parser.parse_args()
    
    plugin = TuShareHKFinaIndicatorPlugin()
    
    kwargs = {}
    if args.ts_code:
        kwargs['ts_code'] = args.ts_code
    if args.period:
        kwargs['period'] = args.period
    if args.report_type:
        kwargs['report_type'] = args.report_type
    if args.start_date:
        kwargs['start_date'] = args.start_date
    if args.end_date:
        kwargs['end_date'] = args.end_date
    if args.max_stocks:
        kwargs['max_stocks'] = args.max_stocks
    
    result = plugin.run(**kwargs)
    
    print(f"\nPlugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"Error: {result['error']}")
        sys.exit(1)
    
    print("Successfully processed HK financial indicators data")
    sys.exit(0)
