"""Data ingestion service for coordinating the ETL process."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date
import pandas as pd
from uuid import uuid4

from stock_datasource.utils.extractor import extractor
from stock_datasource.utils.loader import loader
from stock_datasource.utils.quality_checks import quality_checker
from stock_datasource.utils.logger import logger
from stock_datasource.models.database import db_client
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class IngestionService:
    """Coordinates the data ingestion process."""
    
    def __init__(self):
        self.extractor = extractor
        self.loader = loader
        self.quality_checker = quality_checker
        self.db = db_client
    
    def ingest_daily_data(self, trade_date: str, 
                         run_quality_checks: bool = True,
                         check_schedule: bool = True) -> Dict[str, Any]:
        """
        Ingest daily data for a specific trade date.
        
        Args:
            trade_date: Trade date in YYYYMMDD format
            run_quality_checks: Whether to run quality checks
            check_schedule: Whether to check plugin schedule before extraction
            
        Returns:
            Dictionary with ingestion results
        """
        task_id = str(uuid4())
        logger.info(f"Starting daily ingestion for {trade_date}, task_id: {task_id}")
        
        result = {
            "task_id": task_id,
            "trade_date": trade_date,
            "start_time": datetime.now(),
            "status": "running",
            "extraction": {},
            "loading": {},
            "quality_checks": {},
            "error": None
        }
        
        try:
            # Step 1: Extract data
            logger.info(f"Extracting data for {trade_date}")
            extracted_data = self.extractor.extract_all_data_for_date(trade_date, check_schedule=check_schedule)
            
            # Validate extracted data
            for api_name, data in extracted_data.items():
                if not data.empty:
                    validation = self.extractor.validate_data_quality(data, trade_date)
                    result['extraction'][api_name] = validation
                    logger.info(f"Extracted {api_name}: {validation}")
            
            # Step 2: Load data
            logger.info(f"Loading data for {trade_date}")
            loading_result = self.loader.process_daily_ingestion(trade_date, extracted_data)
            result['loading'] = loading_result
            
            # Step 3: Quality checks
            qc_result = None
            if run_quality_checks:
                logger.info(f"Running quality checks for {trade_date}")
                qc_result = self.quality_checker.run_all_checks(trade_date)
                result['quality_checks'] = qc_result
                
                # Skip logging quality check results for now (can be async)
                # for check_result in qc_result['checks']:
                #     self.quality_checker.log_quality_check(check_result)
            
            # Determine overall status
            if loading_result['status'] == 'failed':
                result['status'] = 'failed'
            elif qc_result and qc_result.get('overall_status') == 'failed':
                result['status'] = 'failed'
            elif (loading_result['status'] == 'partial_success' or 
                  (qc_result and qc_result.get('overall_status') == 'warning')):
                result['status'] = 'warning'
            else:
                result['status'] = 'success'
            
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            
            logger.info(f"Daily ingestion completed for {trade_date}: {result['status']}, "
                       f"duration: {result['duration_seconds']:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Daily ingestion failed for {trade_date}: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            return result
    
    def backfill_data(self, start_date: str, end_date: str,
                     run_quality_checks: bool = True) -> Dict[str, Any]:
        """
        Backfill data for a date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            run_quality_checks: Whether to run quality checks
            
        Returns:
            Dictionary with backfill results
        """
        task_id = str(uuid4())
        logger.info(f"Starting backfill from {start_date} to {end_date}, task_id: {task_id}")
        
        result = {
            "task_id": task_id,
            "start_date": start_date,
            "end_date": end_date,
            "start_time": datetime.now(),
            "status": "running",
            "dates_processed": [],
            "summary": {
                "total_dates": 0,
                "successful": 0,
                "warnings": 0,
                "failed": 0
            },
            "error": None
        }
        
        try:
            # Get trading calendar
            trade_cal = self.extractor.get_trade_calendar(start_date, end_date)
            trade_dates = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            
            result['summary']['total_dates'] = len(trade_dates)
            logger.info(f"Backfilling {len(trade_dates)} trading days")
            
            for trade_date in trade_dates:
                try:
                    daily_result = self.ingest_daily_data(trade_date, run_quality_checks)
                    result['dates_processed'].append(daily_result)
                    
                    # Update summary
                    if daily_result['status'] == 'success':
                        result['summary']['successful'] += 1
                    elif daily_result['status'] == 'warning':
                        result['summary']['warnings'] += 1
                    else:
                        result['summary']['failed'] += 1
                    
                    logger.info(f"Backfill progress: {trade_date} - {daily_result['status']}")
                    
                except Exception as e:
                    logger.error(f"Failed to process {trade_date}: {e}")
                    result['summary']['failed'] += 1
                    continue
            
            # Determine overall status
            if result['summary']['failed'] > 0:
                result['status'] = 'failed'
            elif result['summary']['warnings'] > 0:
                result['status'] = 'warning'
            else:
                result['status'] = 'success'
            
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            
            logger.info(f"Backfill completed: {result['status']}, "
                       f"successful: {result['summary']['successful']}, "
                       f"warnings: {result['summary']['warnings']}, "
                       f"failed: {result['summary']['failed']}, "
                       f"duration: {result['duration_seconds']:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Backfill failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            result['end_time'] = datetime.now()
            result['duration_seconds'] = (result['end_time'] - result['start_time']).total_seconds()
            return result
    
    def get_ingestion_status(self, trade_date: str) -> Dict[str, Any]:
        """Get ingestion status for a specific trade date."""
        try:
            # Check if data exists in key tables
            tables_to_check = ['ods_daily', 'fact_daily_bar']
            status = {}
            
            for table in tables_to_check:
                if not self.db.table_exists(table):
                    status[table] = {"exists": False}
                    continue
                
                query = f"""
                SELECT COUNT(*) as record_count, MAX(_ingested_at) as last_update
                FROM {table}
                WHERE trade_date = '{trade_date}'
                """
                
                result = self.db.execute_query(query)
                if not result.empty:
                    status[table] = {
                        "exists": True,
                        "record_count": int(result.iloc[0]['record_count']),
                        "last_update": result.iloc[0]['last_update'],
                        "has_data": result.iloc[0]['record_count'] > 0
                    }
                else:
                    status[table] = {
                        "exists": True,
                        "record_count": 0,
                        "last_update": None,
                        "has_data": False
                    }
            
            # Overall status
            overall_status = "complete"
            for table_info in status.values():
                if not table_info.get('has_data', False):
                    overall_status = "incomplete"
                    break
            
            return {
                "trade_date": trade_date,
                "overall_status": overall_status,
                "table_status": status
            }
            
        except Exception as e:
            logger.error(f"Failed to get ingestion status for {trade_date}: {e}")
            return {
                "trade_date": trade_date,
                "error": str(e),
                "overall_status": "error"
            }
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> Dict[str, Any]:
        """Clean up old data and logs."""
        logger.info(f"Cleaning up data older than {days_to_keep} days")
        
        result = {
            "cleanup_date": datetime.now(),
            "days_to_keep": days_to_keep,
            "tables_cleaned": [],
            "status": "running"
        }
        
        try:
            # Clean up old versions in ReplacingMergeTree tables
            tables_to_clean = [
                'ods_daily', 'ods_adj_factor', 'ods_daily_basic',
                'fact_daily_bar', 'dim_security'
            ]
            
            for table in tables_to_clean:
                try:
                    if self.db.table_exists(table):
                        cleanup_stats = self.loader.cleanup_old_versions(table, days_to_keep)
                        result['tables_cleaned'].append(cleanup_stats)
                        logger.info(f"Cleaned up {table}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {table}: {e}")
                    continue
            
            result['status'] = 'success'
            logger.info(f"Cleanup completed: {len(result['tables_cleaned'])} tables cleaned")
            
            return result
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            result['status'] = 'failed'
            result['error'] = str(e)
            return result


# Global ingestion service instance
ingestion_service = IngestionService()
