"""TuShare cash flow statement data plugin implementation."""

import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path
import json

from stock_datasource.plugins import BasePlugin
from stock_datasource.core.base_plugin import PluginCategory, PluginRole
from .extractor import extractor


class TuShareCashflowPlugin(BasePlugin):
    """TuShare cash flow statement data plugin."""
    
    @property
    def name(self) -> str:
        return "tushare_cashflow"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "TuShare cash flow statement data"
    
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
        """Extract cash flow statement data from TuShare.
        
        Args:
            ts_code: Stock code (e.g., 600000.SH)
            start_date: Announcement start date in YYYYMMDD format
            end_date: Announcement end date in YYYYMMDD format
            period: Report period (e.g., 20231231)
            report_type: Report type
            trade_date: Trading date for batch mode
        """
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
            
            self.logger.info("Extracting cash flow statement data for all stocks (batch mode)")
            
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
                    self.logger.info(f"Extracting cash flow statement data for {stock_code} ({idx+1}/{len(stocks_df)})")
                    
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
                    self.logger.warning(f"Failed to extract cash flow statement for {stock_code}: {e}")
                    continue
            
            if not all_data:
                self.logger.warning("No cash flow statement data extracted for any stock")
                return pd.DataFrame()
            
            combined_data = pd.concat(all_data, ignore_index=True)
            # Add system columns for batch mode
            combined_data['version'] = int(datetime.now().timestamp())
            combined_data['_ingested_at'] = datetime.now()
            self.logger.info(f"Extracted {len(combined_data)} cash flow statement records from {len(all_data)} stocks")
            return combined_data
        
        # Single stock mode
        self.logger.info(f"Extracting cash flow statement data for {ts_code}")
        
        data = extractor.extract(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            period=period,
            report_type=report_type
        )
        
        if data.empty:
            self.logger.warning(f"No cash flow statement data found for {ts_code}")
            return pd.DataFrame()
        
        self.logger.info(f"Extracted {len(data)} cash flow statement records")
        return data
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate cash flow statement data."""
        if data.empty:
            self.logger.warning("Empty cash flow statement data")
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
        
        self.logger.info(f"Cash flow statement data validation passed for {len(data)} records")
        return True
    
    def transform_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform cash flow statement data for database insertion."""
        numeric_columns = [
            'net_profit', 'finan_exp', 'c_fr_sale_sg', 'recp_tax_rends',
            'n_depos_incr_fi', 'n_incr_loans_cb', 'n_inc_borr_oth_fi',
            'prem_fr_orig_contr', 'n_incr_insured_dep', 'n_reinsur_prem',
            'n_incr_disp_tfa', 'ifc_cash_incr', 'n_incr_disp_faas',
            'n_incr_loans_oth_bank', 'n_cap_incr_repur', 'c_fr_oth_operate_a',
            'c_inf_fr_operate_a', 'c_paid_goods_s', 'c_paid_to_for_empl',
            'c_paid_for_taxes', 'n_incr_clt_loan_adv', 'n_incr_dep_cbob',
            'c_pay_claims_orig_inco', 'pay_handling_chrg', 'pay_comm_insur_plcy',
            'oth_cash_pay_oper_act', 'st_cash_out_act', 'n_cashflow_act',
            'oth_recp_ral_inv_act', 'c_disp_withdrwl_invest', 'c_recp_return_invest',
            'n_recp_disp_fiolta', 'n_recp_disp_sobu', 'stot_inflows_inv_act',
            'c_pay_acq_const_fiolta', 'c_paid_invest', 'n_disp_subs_oth_biz',
            'oth_pay_ral_inv_act', 'n_incr_pledge_loan', 'stot_out_inv_act',
            'n_cashflow_inv_act', 'c_recp_borrow', 'proc_issue_bonds',
            'oth_cash_recp_ral_fnc_act', 'stot_cash_in_fnc_act', 'free_cashflow',
            'c_prepay_amt_borr', 'c_pay_dist_dpcp_int_exp', 'incl_dvd_profit_paid_sc_ms',
            'oth_cashpay_ral_fnc_act', 'stot_cashout_fnc_act', 'n_cash_flows_fnc_act',
            'eff_fx_flu_cash', 'n_incr_cash_cash_equ', 'c_cash_equ_beg_period',
            'c_cash_equ_end_period', 'c_recp_cap_contrib', 'incl_cash_rec_saims',
            'uncon_invest_loss', 'prov_depr_assets', 'depr_fa_coga_dpba',
            'amort_intang_assets', 'lt_amort_deferred_exp', 'decr_deferred_exp',
            'incr_acc_exp', 'loss_disp_fiolta', 'loss_scr_fa', 'loss_fv_chg',
            'invest_loss', 'decr_def_inc_tax_assets', 'incr_def_inc_tax_liab',
            'decr_inventories', 'decr_oper_payable', 'incr_oper_payable', 'others',
            'im_net_cashflow_oper_act', 'conv_debt_into_cap', 'conv_copbonds_due_within_1y',
            'fa_fnc_leases', 'im_n_incr_cash_equ', 'net_dism_capital_add',
            'net_cash_rece_sec', 'credit_impa_loss', 'use_right_asset_dep',
            'oth_loss_asset', 'end_bal_cash', 'beg_bal_cash', 'end_bal_cash_equ',
            'beg_bal_cash_equ'
        ]
        
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        date_columns = ['end_date', 'ann_date', 'f_ann_date']
        for col in date_columns:
            if col in data.columns:
                data[col] = pd.to_datetime(data[col], format='%Y%m%d', errors='coerce').dt.date
        
        self.logger.info(f"Transformed {len(data)} cash flow statement records")
        return data
    
    def load_data(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Load cash flow statement data into ODS table."""
        if not self.db:
            self.logger.error("Database not initialized")
            return {"status": "failed", "error": "Database not initialized"}
        
        if data.empty:
            self.logger.warning("No data to load")
            return {"status": "no_data", "loaded_records": 0}
        
        try:
            self.logger.info(f"Loading {len(data)} records into ods_cash_flow")
            ods_data = data.copy()
            ods_data['version'] = int(datetime.now().timestamp())
            ods_data['_ingested_at'] = datetime.now()
            
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
    
    parser = argparse.ArgumentParser(description="TuShare Cash Flow Statement Data Plugin")
    parser.add_argument("--ts-code", required=True, help="Stock code (e.g., 600000.SH)")
    parser.add_argument("--start-date", help="Announcement start date")
    parser.add_argument("--end-date", help="Announcement end date")
    parser.add_argument("--period", help="Report period")
    parser.add_argument("--report-type", help="Report type")
    
    args = parser.parse_args()
    
    plugin = TuShareCashflowPlugin()
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
