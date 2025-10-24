"""Data quality checks for stock data."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.utils.extractor import extractor
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class QualityChecker:
    """Performs data quality checks on stock data."""
    
    def __init__(self):
        self.db = db_client
        self.extractor = extractor
    
    def check_trade_date_alignment(self, trade_date: str) -> Dict[str, Any]:
        """Check if data row count matches trading calendar."""
        logger.info(f"Checking trade date alignment for {trade_date}")
        
        # Get expected trading days
        trade_cal = self.extractor.get_trade_calendar(trade_date, trade_date)
        if trade_cal.empty or trade_cal.iloc[0]['is_open'] == 0:
            return {
                "check_name": "trade_date_alignment",
                "trade_date": trade_date,
                "status": "skipped",
                "reason": "Not a trading day"
            }
        
        results = {}
        
        # Check each ODS table
        ods_tables = ['ods_daily', 'ods_adj_factor', 'ods_daily_basic']
        
        for table in ods_tables:
            if not self.db.table_exists(table):
                continue
            
            try:
                # Count records for the trade date
                query = f"""
                SELECT COUNT(*) as record_count
                FROM {table}
                WHERE trade_date = '{trade_date}'
                """
                
                result = self.db.execute_query(query)
                actual_count = result.iloc[0]['record_count'] if not result.empty else 0
                
                # Get expected count (approximate from previous trading days)
                expected_count = self._get_expected_record_count(table, trade_date)
                
                # Determine status
                if actual_count == 0:
                    status = "failed"
                    issue = "No records found"
                elif expected_count > 0 and abs(actual_count - expected_count) / expected_count > 0.1:
                    status = "warning"
                    issue = f"Record count deviation > 10%: expected ~{expected_count}, got {actual_count}"
                else:
                    status = "passed"
                    issue = None
                
                results[table] = {
                    "actual_count": int(actual_count),
                    "expected_count": expected_count,
                    "status": status,
                    "issue": issue
                }
                
            except Exception as e:
                logger.error(f"Failed to check {table}: {e}")
                results[table] = {
                    "status": "error",
                    "error": str(e)
                }
        
        # Overall result
        failed_checks = [r for r in results.values() if r['status'] == 'failed']
        warning_checks = [r for r in results.values() if r['status'] == 'warning']
        
        overall_status = 'failed' if failed_checks else ('warning' if warning_checks else 'passed')
        
        return {
            "check_name": "trade_date_alignment",
            "trade_date": trade_date,
            "status": overall_status,
            "details": results,
            "summary": {
                "total_tables": len(results),
                "passed": len([r for r in results.values() if r['status'] == 'passed']),
                "warning": len(warning_checks),
                "failed": len(failed_checks)
            }
        }
    
    def _get_expected_record_count(self, table_name: str, trade_date: str) -> int:
        """Get expected record count based on historical data."""
        try:
            # Get average count from previous 10 trading days
            query = f"""
            SELECT AVG(record_count) as avg_count
            FROM (
                SELECT COUNT(*) as record_count
                FROM {table_name}
                WHERE trade_date < '{trade_date}'
                GROUP BY trade_date
                ORDER BY trade_date DESC
                LIMIT 10
            )
            """
            
            result = self.db.execute_query(query)
            if not result.empty and result.iloc[0]['avg_count'] is not None:
                return int(result.iloc[0]['avg_count'])
        except Exception as e:
            logger.error(f"Failed to get expected count for {table_name}: {e}")
        
        return 0
    
    def check_price_consistency(self, trade_date: str) -> Dict[str, Any]:
        """Check price data consistency (OHLC relationships)."""
        logger.info(f"Checking price consistency for {trade_date}")
        
        if not self.db.table_exists('ods_daily'):
            return {
                "check_name": "price_consistency",
                "trade_date": trade_date,
                "status": "skipped",
                "reason": "ods_daily table not found"
            }
        
        try:
            query = f"""
            SELECT 
                ts_code,
                open, high, low, close, pre_close
            FROM ods_daily
            WHERE trade_date = '{trade_date}'
            AND open IS NOT NULL 
            AND high IS NOT NULL 
            AND low IS NOT NULL 
            AND close IS NOT NULL
            """
            
            df = self.db.execute_query(query)
            
            if df.empty:
                return {
                    "check_name": "price_consistency",
                    "trade_date": trade_date,
                    "status": "failed",
                    "issue": "No price data found"
                }
            
            issues = []
            
            # Check OHLC relationships
            # High should be >= max(Open, Close)
            invalid_high = df[df['high'] < df[['open', 'close']].max(axis=1)]
            if len(invalid_high) > 0:
                issues.append(f"High < max(Open, Close) for {len(invalid_high)} records")
            
            # Low should be <= min(Open, Close)
            invalid_low = df[df['low'] > df[['open', 'close']].min(axis=1)]
            if len(invalid_low) > 0:
                issues.append(f"Low > min(Open, Close) for {len(invalid_low)} records")
            
            # Check for negative prices
            price_cols = ['open', 'high', 'low', 'close']
            for col in price_cols:
                negative_prices = df[df[col] < 0]
                if len(negative_prices) > 0:
                    issues.append(f"Negative {col} prices for {len(negative_prices)} records")
            
            # Check for extreme price changes (> 20%)
            df['price_change_pct'] = abs((df['close'] - df['pre_close']) / df['pre_close'] * 100)
            extreme_changes = df[df['price_change_pct'] > 20]
            if len(extreme_changes) > 0:
                issues.append(f"Price changes > 20% for {len(extreme_changes)} records")
            
            status = 'failed' if issues else 'passed'
            
            return {
                "check_name": "price_consistency",
                "trade_date": trade_date,
                "status": status,
                "total_records": len(df),
                "issues": issues,
                "issue_count": len(issues)
            }
            
        except Exception as e:
            logger.error(f"Price consistency check failed: {e}")
            return {
                "check_name": "price_consistency",
                "trade_date": trade_date,
                "status": "error",
                "error": str(e)
            }
    
    def check_stk_limit_consistency(self, trade_date: str) -> Dict[str, Any]:
        """Check stock limit (up/down) consistency."""
        logger.info(f"Checking stock limit consistency for {trade_date}")
        
        if not self.db.table_exists('ods_stk_limit') or not self.db.table_exists('ods_daily'):
            return {
                "check_name": "stk_limit_consistency",
                "trade_date": trade_date,
                "status": "skipped",
                "reason": "Required tables not found"
            }
        
        try:
            query = f"""
            SELECT 
                d.ts_code,
                d.close,
                d.pre_close,
                l.up_limit,
                l.down_limit
            FROM ods_daily d
            LEFT JOIN ods_stk_limit l 
                ON d.ts_code = l.ts_code 
                AND d.trade_date = l.trade_date
            WHERE d.trade_date = '{trade_date}'
            AND d.close IS NOT NULL 
            AND d.pre_close IS NOT NULL
            """
            
            df = self.db.execute_query(query)
            
            if df.empty:
                return {
                    "check_name": "stk_limit_consistency",
                    "trade_date": trade_date,
                    "status": "failed",
                    "issue": "No data found"
                }
            
            issues = []
            
            # Check records with limit data
            limit_data = df.dropna(subset=['up_limit', 'down_limit'])
            
            if len(limit_data) > 0:
                # Check if close price is within limits
                above_up_limit = limit_data[limit_data['close'] > limit_data['up_limit']]
                below_down_limit = limit_data[limit_data['close'] < limit_data['down_limit']]
                
                if len(above_up_limit) > 0:
                    issues.append(f"Close price above up limit for {len(above_up_limit)} records")
                
                if len(below_down_limit) > 0:
                    issues.append(f"Close price below down limit for {len(below_down_limit)} records")
            
            # Check for missing limit data
            missing_limits = df[df['up_limit'].isnull() | df['down_limit'].isnull()]
            if len(missing_limits) > 0:
                issues.append(f"Missing limit data for {len(missing_limits)} records")
            
            status = 'failed' if issues else 'passed'
            
            return {
                "check_name": "stk_limit_consistency",
                "trade_date": trade_date,
                "status": status,
                "total_records": len(df),
                "records_with_limits": len(limit_data),
                "issues": issues,
                "issue_count": len(issues)
            }
            
        except Exception as e:
            logger.error(f"Stock limit consistency check failed: {e}")
            return {
                "check_name": "stk_limit_consistency",
                "trade_date": trade_date,
                "status": "error",
                "error": str(e)
            }
    
    def check_suspend_consistency(self, trade_date: str) -> Dict[str, Any]:
        """Check suspension data consistency."""
        logger.info(f"Checking suspension consistency for {trade_date}")
        
        if not self.db.table_exists('ods_suspend_d') or not self.db.table_exists('ods_daily'):
            return {
                "check_name": "suspend_consistency",
                "trade_date": trade_date,
                "status": "skipped",
                "reason": "Required tables not found"
            }
        
        try:
            query = f"""
            SELECT 
                d.ts_code,
                d.close,
                s.suspend_type
            FROM ods_daily d
            LEFT JOIN ods_suspend_d s 
                ON d.ts_code = s.ts_code 
                AND d.trade_date = s.trade_date
            WHERE d.trade_date = '{trade_date}'
            """
            
            df = self.db.execute_query(query)
            
            if df.empty:
                return {
                    "check_name": "suspend_consistency",
                    "trade_date": trade_date,
                    "status": "failed",
                    "issue": "No data found"
                }
            
            issues = []
            
            # Check suspended stocks with trading data
            suspended_with_trades = df[
                (df['suspend_type'].notna()) & (df['close'].notna())
            ]
            
            if len(suspended_with_trades) > 0:
                issues.append(f"Suspended stocks with trading data: {len(suspended_with_trades)} records")
            
            # Check for stocks with zero/invalid close price but not suspended
            no_trades_not_suspended = df[
                (df['close'].isna() | (df['close'] == 0)) & (df['suspend_type'].isna())
            ]
            
            if len(no_trades_not_suspended) > 0:
                issues.append(f"Stocks with no trades but not suspended: {len(no_trades_not_suspended)} records")
            
            status = 'failed' if issues else 'passed'
            
            return {
                "check_name": "suspend_consistency",
                "trade_date": trade_date,
                "status": status,
                "total_records": len(df),
                "suspended_records": len(df[df['suspend_type'].notna()]),
                "issues": issues,
                "issue_count": len(issues)
            }
            
        except Exception as e:
            logger.error(f"Suspension consistency check failed: {e}")
            return {
                "check_name": "suspend_consistency",
                "trade_date": trade_date,
                "status": "error",
                "error": str(e)
            }
    
    def run_all_checks(self, trade_date: str) -> Dict[str, Any]:
        """Run all quality checks for a trade date."""
        logger.info(f"Running all quality checks for {trade_date}")
        
        checks = [
            self.check_trade_date_alignment,
            self.check_price_consistency,
            self.check_stk_limit_consistency,
            self.check_suspend_consistency
        ]
        
        results = {
            "trade_date": trade_date,
            "checks": [],
            "summary": {
                "total_checks": len(checks),
                "passed": 0,
                "warning": 0,
                "failed": 0,
                "skipped": 0,
                "error": 0
            }
        }
        
        for check_func in checks:
            try:
                result = check_func(trade_date)
                results['checks'].append(result)
                
                # Update summary
                status = result.get('status', 'error')
                if status in results['summary']:
                    results['summary'][status] += 1
                else:
                    results['summary']['error'] += 1
                    
            except Exception as e:
                logger.error(f"Quality check {check_func.__name__} failed: {e}")
                results['checks'].append({
                    "check_name": check_func.__name__,
                    "trade_date": trade_date,
                    "status": "error",
                    "error": str(e)
                })
                results['summary']['error'] += 1
        
        # Overall status
        if results['summary']['failed'] > 0:
            results['overall_status'] = 'failed'
        elif results['summary']['warning'] > 0 or results['summary']['error'] > 0:
            results['overall_status'] = 'warning'
        else:
            results['overall_status'] = 'passed'
        
        logger.info(f"Quality checks completed for {trade_date}: {results['overall_status']}")
        return results
    
    def log_quality_check(self, check_result: Dict[str, Any]) -> None:
        """Log quality check result to metadata table."""
        try:
            # Ensure meta table exists
            if not self.db.table_exists("meta_quality_check"):
                self._create_quality_check_table()
            
            query = """
            INSERT INTO meta_quality_check 
            (check_name, table_name, check_date, check_result, 
             expected_value, actual_value, status, error_details, created_at)
            VALUES
            """
            
            params = {
                "check_name": check_result['check_name'],
                "table_name": check_result.get('table_name', 'multiple'),
                "check_date": check_result['trade_date'],
                "check_result": check_result['status'],
                "expected_value": str(check_result.get('expected_count', '')),
                "actual_value": str(check_result.get('actual_count', '')),
                "status": check_result['status'],
                "error_details": '; '.join(check_result.get('issues', [])),
                "created_at": datetime.now()
            }
            
            self.db.execute(query, params)
            
        except Exception as e:
            logger.error(f"Failed to log quality check: {e}")
    
    def _create_quality_check_table(self) -> None:
        """Create quality check metadata table if not exists."""
        from stock_datasource.models.schemas import META_QUALITY_CHECK_SCHEMA
        from stock_datasource.utils.schema_manager import schema_manager
        schema_manager.create_table_from_schema(META_QUALITY_CHECK_SCHEMA)


# Global quality checker instance
quality_checker = QualityChecker()
