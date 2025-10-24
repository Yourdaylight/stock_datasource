"""Data validation utilities for stock data."""

import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

from stock_datasource.utils.logger import logger

log = logger.bind(component="DataValidator")


class DataValidator:
    """Validates stock data quality and integrity."""
    
    def __init__(self):
        self.logger = log
    
    # ==================== Basic Validation ====================
    
    def validate_not_empty(self, data: pd.DataFrame, context: str = "") -> Tuple[bool, Optional[str]]:
        """Check if DataFrame is not empty."""
        if data is None or data.empty:
            msg = f"Data is empty {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_required_columns(self, data: pd.DataFrame, 
                                 required_cols: List[str], 
                                 context: str = "") -> Tuple[bool, Optional[str]]:
        """Check if all required columns exist."""
        missing_cols = set(required_cols) - set(data.columns)
        if missing_cols:
            msg = f"Missing required columns: {missing_cols} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_no_null_keys(self, data: pd.DataFrame, 
                             key_cols: List[str],
                             context: str = "") -> Tuple[bool, Optional[str]]:
        """Check if key columns have no null values."""
        null_counts = data[key_cols].isnull().sum()
        if null_counts.sum() > 0:
            msg = f"Null values in key columns: {null_counts[null_counts > 0].to_dict()} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_no_duplicates(self, data: pd.DataFrame, 
                              subset: List[str],
                              context: str = "") -> Tuple[bool, Optional[str]]:
        """Check for duplicate rows."""
        duplicates = data.duplicated(subset=subset).sum()
        if duplicates > 0:
            msg = f"Found {duplicates} duplicate rows based on {subset} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    # ==================== Type Validation ====================
    
    def validate_column_types(self, data: pd.DataFrame, 
                             type_map: Dict[str, str],
                             context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate column data types."""
        issues = []
        for col, expected_type in type_map.items():
            if col not in data.columns:
                continue
            
            actual_type = str(data[col].dtype)
            if expected_type not in actual_type:
                issues.append(f"{col}: expected {expected_type}, got {actual_type}")
        
        if issues:
            msg = f"Type mismatches: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    # ==================== Value Range Validation ====================
    
    def validate_date_format(self, data: pd.DataFrame, 
                            date_cols: List[str],
                            format: str = "%Y%m%d",
                            context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate date column format."""
        issues = []
        for col in date_cols:
            if col not in data.columns:
                continue
            
            try:
                pd.to_datetime(data[col], format=format)
            except Exception as e:
                issues.append(f"{col}: {str(e)}")
        
        if issues:
            msg = f"Date format validation failed: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_numeric_range(self, data: pd.DataFrame, 
                              col: str, 
                              min_val: Optional[float] = None,
                              max_val: Optional[float] = None,
                              context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate numeric column is within range."""
        if col not in data.columns:
            return True, None
        
        issues = []
        
        if min_val is not None:
            out_of_range = (data[col] < min_val).sum()
            if out_of_range > 0:
                issues.append(f"{out_of_range} values < {min_val}")
        
        if max_val is not None:
            out_of_range = (data[col] > max_val).sum()
            if out_of_range > 0:
                issues.append(f"{out_of_range} values > {max_val}")
        
        if issues:
            msg = f"Numeric range validation failed for {col}: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_positive_values(self, data: pd.DataFrame, 
                                cols: List[str],
                                context: str = "") -> Tuple[bool, Optional[str]]:
        """Check if numeric columns have only positive values."""
        issues = []
        for col in cols:
            if col not in data.columns:
                continue
            
            negative_count = (data[col] < 0).sum()
            if negative_count > 0:
                issues.append(f"{col}: {negative_count} negative values")
        
        if issues:
            msg = f"Positive value validation failed: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    # ==================== Stock Data Specific Validation ====================
    
    def validate_ohlc_relationship(self, data: pd.DataFrame,
                                  context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate OHLC (Open, High, Low, Close) relationships."""
        if not all(col in data.columns for col in ['open', 'high', 'low', 'close']):
            return True, None
        
        issues = []
        
        # High should be >= Low
        invalid = (data['high'] < data['low']).sum()
        if invalid > 0:
            issues.append(f"{invalid} rows: high < low")
        
        # High should be >= Open and Close
        invalid = ((data['high'] < data['open']) | (data['high'] < data['close'])).sum()
        if invalid > 0:
            issues.append(f"{invalid} rows: high < open or close")
        
        # Low should be <= Open and Close
        invalid = ((data['low'] > data['open']) | (data['low'] > data['close'])).sum()
        if invalid > 0:
            issues.append(f"{invalid} rows: low > open or close")
        
        if issues:
            msg = f"OHLC relationship validation failed: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_price_change_consistency(self, data: pd.DataFrame,
                                         context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate price change and percentage change consistency."""
        if not all(col in data.columns for col in ['close', 'pre_close', 'change', 'pct_chg']):
            return True, None
        
        issues = []
        
        # Calculate expected change
        expected_change = data['close'] - data['pre_close']
        actual_change = data['change']
        
        # Allow small floating point differences
        diff = abs(expected_change - actual_change)
        invalid = (diff > 0.01).sum()
        if invalid > 0:
            issues.append(f"{invalid} rows: change inconsistency")
        
        # Calculate expected pct_chg
        with np.errstate(divide='ignore', invalid='ignore'):
            expected_pct = (expected_change / data['pre_close'] * 100).fillna(0)
            actual_pct = data['pct_chg'].fillna(0)
            
            diff = abs(expected_pct - actual_pct)
            invalid = (diff > 0.1).sum()
            if invalid > 0:
                issues.append(f"{invalid} rows: pct_chg inconsistency")
        
        if issues:
            msg = f"Price change consistency validation failed: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    def validate_volume_consistency(self, data: pd.DataFrame,
                                   context: str = "") -> Tuple[bool, Optional[str]]:
        """Validate volume and amount consistency."""
        if not all(col in data.columns for col in ['vol', 'amount', 'close']):
            return True, None
        
        issues = []
        
        # Volume should be positive
        zero_vol = (data['vol'] == 0).sum()
        if zero_vol > 0:
            issues.append(f"{zero_vol} rows: zero volume")
        
        # Amount should be positive
        zero_amount = (data['amount'] == 0).sum()
        if zero_amount > 0:
            issues.append(f"{zero_amount} rows: zero amount")
        
        # Amount should be approximately vol * close (with some tolerance)
        # Skip if close is 0
        valid_rows = data['close'] != 0
        if valid_rows.sum() > 0:
            expected_amount = data.loc[valid_rows, 'vol'] * data.loc[valid_rows, 'close']
            actual_amount = data.loc[valid_rows, 'amount']
            
            # Allow 5% difference
            pct_diff = abs(expected_amount - actual_amount) / actual_amount
            invalid = (pct_diff > 0.05).sum()
            if invalid > 0:
                issues.append(f"{invalid} rows: amount inconsistency")
        
        if issues:
            msg = f"Volume consistency validation failed: {'; '.join(issues)} {context}"
            self.logger.warning(msg)
            return False, msg
        return True, None
    
    # ==================== Comprehensive Validation ====================
    
    def validate_daily_data(self, data: pd.DataFrame, 
                           trade_date: str) -> Dict[str, Any]:
        """Comprehensive validation for daily stock data."""
        result = {
            "trade_date": trade_date,
            "record_count": len(data),
            "checks": [],
            "passed": True,
            "issues": []
        }
        
        context = f"(trade_date={trade_date})"
        
        # Basic checks
        checks = [
            ("not_empty", self.validate_not_empty(data, context)),
            ("required_columns", self.validate_required_columns(
                data, 
                ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount'],
                context
            )),
            ("no_null_keys", self.validate_no_null_keys(
                data,
                ['ts_code', 'trade_date'],
                context
            )),
            ("no_duplicates", self.validate_no_duplicates(
                data,
                ['ts_code', 'trade_date'],
                context
            )),
        ]
        
        # Type checks
        if not data.empty:
            checks.extend([
                ("date_format", self.validate_date_format(
                    data,
                    ['trade_date'],
                    context=context
                )),
                ("positive_prices", self.validate_positive_values(
                    data,
                    ['open', 'high', 'low', 'close', 'pre_close'],
                    context
                )),
                ("positive_volume", self.validate_positive_values(
                    data,
                    ['vol', 'amount'],
                    context
                )),
                ("ohlc_relationship", self.validate_ohlc_relationship(data, context)),
                ("price_change_consistency", self.validate_price_change_consistency(data, context)),
                ("volume_consistency", self.validate_volume_consistency(data, context)),
            ])
        
        # Collect results
        for check_name, (passed, issue) in checks:
            result["checks"].append({
                "name": check_name,
                "passed": passed,
                "issue": issue
            })
            if not passed:
                result["passed"] = False
                result["issues"].append(issue)
        
        return result
    
    def validate_adj_factor_data(self, data: pd.DataFrame,
                                trade_date: str) -> Dict[str, Any]:
        """Comprehensive validation for adjustment factor data."""
        result = {
            "trade_date": trade_date,
            "record_count": len(data),
            "checks": [],
            "passed": True,
            "issues": []
        }
        
        context = f"(trade_date={trade_date})"
        
        checks = [
            ("not_empty", self.validate_not_empty(data, context)),
            ("required_columns", self.validate_required_columns(
                data,
                ['ts_code', 'trade_date', 'adj_factor'],
                context
            )),
            ("no_null_keys", self.validate_no_null_keys(
                data,
                ['ts_code', 'trade_date'],
                context
            )),
            ("no_duplicates", self.validate_no_duplicates(
                data,
                ['ts_code', 'trade_date'],
                context
            )),
        ]
        
        if not data.empty:
            checks.extend([
                ("date_format", self.validate_date_format(
                    data,
                    ['trade_date'],
                    context=context
                )),
                ("positive_adj_factor", self.validate_positive_values(
                    data,
                    ['adj_factor'],
                    context
                )),
            ])
        
        for check_name, (passed, issue) in checks:
            result["checks"].append({
                "name": check_name,
                "passed": passed,
                "issue": issue
            })
            if not passed:
                result["passed"] = False
                result["issues"].append(issue)
        
        return result
    
    def get_validation_summary(self, validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary of validation results."""
        total = len(validation_results)
        passed = sum(1 for r in validation_results if r.get("passed", False))
        failed = total - passed
        
        all_issues = []
        for result in validation_results:
            all_issues.extend(result.get("issues", []))
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "0%",
            "issues": all_issues
        }


# Global validator instance
data_validator = DataValidator()
