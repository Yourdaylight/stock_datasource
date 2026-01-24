"""TuShare balance sheet data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareBalancesheetPlugin(BasePlugin):
    """TuShare balance sheet data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_balancesheet"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare balance sheet data"
    
    @property
    def api_rate_limit(self) -> int:
        config_file = Path(__file__).parent / "config.json"
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get("rate_limit", 120)
    
    def get_category(self) -> PluginCategory:
        return PluginCategory.CN_STOCK
    
    def get_role(self) -> PluginRole:
        return PluginRole.PRIMARY
    
    def get_dependencies(self) -> List[str]:
        return ["tushare_stock_basic"]
    
    def get_optional_dependencies(self) -> List[str]:
        return []
    
    def extract_data(self, **kwargs) -> pd.DataFrame:
        """Extract balance sheet data from TuShare."""
        ts_code = kwargs.get('ts_code')
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        period = kwargs.get('period')
        report_type = kwargs.get('report_type')
        trade_date = kwargs.get('trade_date')  # For batch mode
        
        # Batch mode: extract for all stocks if ts_code not provided
        if not ts_code:
            if not self.db:
                raise ValueError("Database not initialized for batch mode")
            
            self.logger.info("Extracting balance sheet data for all stocks (batch mode)")
            
            # Get all stock codes from stock_basic table
            stocks_query = "SELECT DISTINCT ts_code FROM ods_stock_basic WHERE list_status = 'L'"
            stocks_df = self.db.execute_query(stocks_query)
            
            if stocks_df.empty:
                self.logger.warning("No stocks found in stock_basic table")
                return pd.DataFrame()
            
            all_data = []
            for idx, row in stocks_df.iterrows():
                stock_code = row['ts_code']
                try:
                    self.logger.info(f"Extracting balance sheet data for {stock_code} ({idx+1}/{len(stocks_df)})")
                    
                    # Use trade_date as end_date if provided, otherwise use current date
                    if trade_date:
                        stock_end_date = trade_date.replace('-', '')
                    else:
                        stock_end_date = end_date
                    
                    data = extractor.extract(
                        ts_code=stock_code,
                        start_date=start_date,
                        end_date=stock_end_date,
                        period=period,
                        report_type=report_type
                    )
                    
                    if not data.empty:
                        all_data.append(data)
                    
                    # Rate limiting between API calls
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    self.logger.warning(f"Failed to extract balance sheet for {stock_code}: {e}")
                    continue
            
            if not all_data:
                self.logger.warning("No balance sheet data extracted for any stock")
                return pd.DataFrame()
            
            combined_data = pd.concat(all_data, ignore_index=True)
            # Add system columns for batch mode
            combined_data['version'] = int(datetime.now().timestamp())
            combined_data['_ingested_at'] = datetime.now()
            self.logger.info(f"Extracted {len(combined_data)} balance sheet records from {len(all_data)} stocks")
            return combined_data
        
        # Single stock mode
        self.logger.info(f"Extracting balance sheet data for {ts_code}")
        
        data = extractor.extract(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type
        )
        
        if data.empty:
            self.logger.warning(f"No balance sheet data found for {ts_code}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} balance sheet records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate balance sheet data."""
        if data.empty:
            self.logger.warning("Empty balance sheet data")
            return False
        
        required_columns = ['ts_code', 'end_date']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            return False
        
        null_ts_codes = data['ts_code'].isnull().sum()
        if null_ts_codes > 0:
            self.logger.error(f"Found {null_ts_codes} null ts_code values")
            return False
        
        self.logger.info(f"Balance sheet data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform balance sheet data for database insertion."""
        # All numeric columns from balance sheet
        numeric_columns = [
            'total_share', 'cap_rese', 'undistr_porfit', 'surplus_rese', 'special_rese',
            'money_cap', 'trad_asset', 'notes_receiv', 'accounts_receiv', 'oth_receiv',
            'prepayment', 'div_receiv', 'int_receiv', 'inventories', 'amor_exp',
            'nca_within_1y', 'sett_rsrv', 'loanto_oth_bank_fi', 'premium_receiv',
            'reinsur_receiv', 'reinsur_res_receiv', 'pur_resale_fa', 'oth_cur_assets',
            'total_cur_assets', 'fa_avail_for_sale', 'htm_invest', 'lt_eqt_invest',
            'invest_real_estate', 'time_deposits', 'oth_assets', 'lt_rec', 'fix_assets',
            'cip', 'const_materials', 'fixed_assets_disp', 'produc_bio_assets',
            'oil_and_gas_assets', 'intan_assets', 'r_and_d', 'goodwill', 'lt_amor_exp',
            'defer_tax_assets', 'decr_in_disbur', 'oth_nca', 'total_nca',
            'cash_reser_cb', 'depos_in_oth_bfi', 'prec_metals', 'deriv_assets',
            'rr_reins_une_prem', 'rr_reins_outstd_cla', 'rr_reins_lins_liab',
            'rr_reins_lthins_liab', 'refund_depos', 'ph_pledge_loans', 'refund_cap_depos',
            'indep_acct_assets', 'client_depos', 'client_prov', 'transac_seat_fee',
            'invest_as_receiv', 'total_assets', 'lt_borr', 'st_borr', 'cb_borr',
            'depos_ib_deposits', 'loan_oth_bank', 'trading_fl', 'notes_payable',
            'acct_payable', 'adv_receipts', 'sold_for_repur_fa', 'comm_payable',
            'payroll_payable', 'taxes_payable', 'int_payable', 'div_payable',
            'oth_payable', 'acc_exp', 'deferred_inc', 'st_bonds_payable',
            'payable_to_reinsurer', 'rsrv_insur_cont', 'acting_trading_sec',
            'acting_uw_sec', 'non_cur_liab_due_1y', 'oth_cur_liab', 'total_cur_liab',
            'bond_payable', 'lt_payable', 'specific_payables', 'estimated_liab',
            'defer_tax_liab', 'defer_inc_non_cur_liab', 'oth_ncl', 'total_ncl',
            'depos_oth_bfi', 'deriv_liab', 'depos', 'agency_bus_liab', 'oth_liab',
            'prem_receiv_adva', 'depos_received', 'ph_invest', 'reser_une_prem',
            'reser_outstd_claims', 'reser_lins_liab', 'reser_lthins_liab',
            'indept_acct_liab', 'pledge_borr', 'indem_payable', 'policy_div_payable',
            'total_liab', 'treasury_share', 'ordin_risk_reser', 'forex_differ',
            'invest_loss_unconf', 'minority_int', 'total_hldr_eqy_exc_min_int',
            'total_hldr_eqy_inc_min_int', 'total_liab_hldr_eqy', 'lt_payroll_payable',
            'oth_comp_income', 'oth_eqt_tools', 'oth_eqt_tools_p_shr', 'lending_funds',
            'acc_receivable', 'st_fin_payable', 'payables', 'hfs_assets', 'hfs_sales',
            'cost_fin_assets', 'fair_value_fin_assets', 'cip_total', 'oth_pay_total',
            'long_pay_total', 'debt_invest', 'oth_debt_invest', 'oth_eq_invest',
            'oth_illiq_fin_assets', 'oth_eq_ppbond', 'receiv_financing',
            'use_right_assets', 'lease_liab', 'contract_assets', 'contract_liab',
            'accounts_receiv_bill', 'accounts_pay', 'oth_rcv_total', 'fix_assets_total'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        date_columns = ['end_date', 'ann_date', 'f_ann_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        self.logger.info(f"Transformed {len(data)} balance sheet records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load balance sheet data into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            self.logger.info(f"Loading {len(data)} records into ods_balance_sheet")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
            ods_data = self._prepare_data_for_insert('ods_balance_sheet', ods_data)
            self.db.insert_dataframe('ods_balance_sheet', ods_data)
            
            self.logger.info(f"Successfully loaded {len(ods_data)} records")
            return {
                "status": "success",
                "loaded_records": len(ods_data),
                "table": "ods_balance_sheet"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="TuShare Balance Sheet Data Plugin")
    parser.add_argument("--ts-code", required=True, help="Stock code (e.g., 600000.SH)")
    parser.add_argument("--start-date", help="Announcement start date")
    parser.add_argument("--end-date", help="Announcement end date")
    parser.add_argument("--period", help="Report period")
    parser.add_argument("--report-type", help="Report type")
    
    args = parser.parse_args()
    
    plugin = TuShareBalancesheetPlugin()
    result = plugin.run(
        ts_code=args.ts_code,
        start_date=args.start_date,
        end_date=args.end_date,
        period=args.period,
        report_type=args.report_type
    )
    
    print(f"\nPlugin: {result['plugin']}")
    print(f"Status: {result['status']}")
    
    if result['status'] != 'success':
        if 'error' in result:
            print(f"\nError: {result['error']}")
        sys.exit(1)
    
    sys.exit(0)
