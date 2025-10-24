"""Metadata service for managing ingestion logs and statistics."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import pandas as pd

from stock_datasource.models.database import db_client
from stock_datasource.utils.schema_manager import schema_manager
from stock_datasource.utils.logger import logger
from stock_datasource.config.settings import settings

logger = logging.getLogger(__name__)


class MetadataService:
    """Manages metadata and statistics for the data pipeline."""
    
    def __init__(self):
        self.db = db_client
        self.schema_manager = schema_manager
    
    def log_ingestion_start(self, task_id: str, api_name: str, 
                           table_name: str) -> None:
        """Log the start of an ingestion task."""
        try:
            # Ensure meta table exists
            if not self.db.table_exists("meta_ingestion_log"):
                self._create_ingestion_log_table()
            
            query = """
            INSERT INTO meta_ingestion_log 
            (task_id, api_name, table_name, start_time, status)
            VALUES
            """
            
            params = {
                "task_id": task_id,
                "api_name": api_name,
                "table_name": table_name,
                "start_time": datetime.now(),
                "status": "running"
            }
            
            self.db.execute(query, params)
            logger.info(f"Logged ingestion start: {task_id} - {api_name} - {table_name}")
            
        except Exception as e:
            logger.error(f"Failed to log ingestion start: {e}")
    
    def log_ingestion_complete(self, task_id: str, records_processed: int, 
                              status: str = "success", error_message: Optional[str] = None) -> None:
        """Log the completion of an ingestion task."""
        try:
            query = """
            ALTER TABLE meta_ingestion_log 
            UPDATE 
                end_time = %(end_time)s,
                status = %(status)s,
                records_processed = %(records_processed)s,
                error_message = %(error_message)s
            WHERE task_id = %(task_id)s
            """
            
            params = {
                "end_time": datetime.now(),
                "status": status,
                "records_processed": records_processed,
                "error_message": error_message,
                "task_id": task_id
            }
            
            self.db.execute(query, params)
            logger.info(f"Logged ingestion complete: {task_id} - {status}")
            
        except Exception as e:
            logger.error(f"Failed to log ingestion complete: {e}")
    
    def log_failed_task(self, task_id: str, api_name: str, table_name: str,
                       error_message: str, retry_count: int = 0) -> None:
        """Log a failed task for retry management."""
        try:
            # Ensure meta table exists
            if not self.db.table_exists("meta_failed_task"):
                self._create_failed_task_table()
            
            query = """
            INSERT INTO meta_failed_task 
            (task_id, api_name, table_name, failed_at, error_message, retry_count)
            VALUES
            """
            
            params = {
                "task_id": task_id,
                "api_name": api_name,
                "table_name": table_name,
                "failed_at": datetime.now(),
                "error_message": error_message,
                "retry_count": retry_count
            }
            
            self.db.execute(query, params)
            logger.warning(f"Logged failed task: {task_id} - {api_name} - {table_name}")
            
        except Exception as e:
            logger.error(f"Failed to log failed task: {e}")
    
    def get_failed_tasks(self, max_retries: int = 3) -> List[Dict[str, Any]]:
        """Get failed tasks that need retry."""
        try:
            if not self.db.table_exists("meta_failed_task"):
                return []
            
            query = f"""
            SELECT 
                task_id,
                api_name,
                table_name,
                failed_at,
                error_message,
                retry_count
            FROM meta_failed_task
            WHERE retry_count < {max_retries}
            ORDER BY failed_at ASC
            """
            
            result = self.db.execute_query(query)
            return result.to_dict('records') if not result.empty else []
            
        except Exception as e:
            logger.error(f"Failed to get failed tasks: {e}")
            return []
    
    def update_retry_count(self, task_id: str, retry_count: int) -> None:
        """Update retry count for a failed task."""
        try:
            query = """
            ALTER TABLE meta_failed_task 
            UPDATE retry_count = %(retry_count)s
            WHERE task_id = %(task_id)s
            """
            
            params = {
                "retry_count": retry_count,
                "task_id": task_id
            }
            
            self.db.execute(query, params)
            
        except Exception as e:
            logger.error(f"Failed to update retry count: {e}")
    
    def get_ingestion_statistics(self, start_date: Optional[str] = None,
                                end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get ingestion statistics for a date range."""
        try:
            if not self.db.table_exists("meta_ingestion_log"):
                return {"error": "Ingestion log table not found"}
            
            # Build query
            query = """
            SELECT 
                api_name,
                table_name,
                status,
                COUNT(*) as task_count,
                AVG(records_processed) as avg_records,
                SUM(records_processed) as total_records,
                MIN(start_time) as first_task,
                MAX(start_time) as last_task
            FROM meta_ingestion_log
            WHERE 1=1
            """
            
            params = {}
            if start_date:
                query += " AND start_time >= %(start_date)s"
                params["start_date"] = start_date
            if end_date:
                query += " AND start_time <= %(end_date)s"
                params["end_date"] = end_date
            
            query += """
            GROUP BY api_name, table_name, status
            ORDER BY api_name, table_name, status
            """
            
            result = self.db.execute_query(query, params)
            
            if result.empty:
                return {"message": "No ingestion data found"}
            
            # Process results
            stats = {
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "summary": {
                    "total_tasks": 0,
                    "successful_tasks": 0,
                    "failed_tasks": 0,
                    "total_records": 0
                },
                "by_api": {},
                "by_table": {}
            }
            
            for _, row in result.iterrows():
                api_name = row['api_name']
                table_name = row['table_name']
                status = row['status']
                
                # Update summary
                stats['summary']['total_tasks'] += row['task_count']
                stats['summary']['total_records'] += row['total_records'] or 0
                
                if status == 'success':
                    stats['summary']['successful_tasks'] += row['task_count']
                elif status == 'failed':
                    stats['summary']['failed_tasks'] += row['task_count']
                
                # By API breakdown
                if api_name not in stats['by_api']:
                    stats['by_api'][api_name] = {
                        'total_tasks': 0,
                        'successful_tasks': 0,
                        'failed_tasks': 0,
                        'total_records': 0
                    }
                
                stats['by_api'][api_name]['total_tasks'] += row['task_count']
                stats['by_api'][api_name]['total_records'] += row['total_records'] or 0
                
                if status == 'success':
                    stats['by_api'][api_name]['successful_tasks'] += row['task_count']
                elif status == 'failed':
                    stats['by_api'][api_name]['failed_tasks'] += row['task_count']
                
                # By table breakdown
                if table_name not in stats['by_table']:
                    stats['by_table'][table_name] = {
                        'total_tasks': 0,
                        'successful_tasks': 0,
                        'failed_tasks': 0,
                        'total_records': 0
                    }
                
                stats['by_table'][table_name]['total_tasks'] += row['task_count']
                stats['by_table'][table_name]['total_records'] += row['total_records'] or 0
                
                if status == 'success':
                    stats['by_table'][table_name]['successful_tasks'] += row['task_count']
                elif status == 'failed':
                    stats['by_table'][table_name]['failed_tasks'] += row['task_count']
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get ingestion statistics: {e}")
            return {"error": str(e)}
    
    def get_data_coverage(self, table_name: str) -> Dict[str, Any]:
        """Get data coverage statistics for a table."""
        try:
            if not self.db.table_exists(table_name):
                return {"error": f"Table {table_name} not found"}
            
            # Get date range
            query = f"""
            SELECT 
                MIN(trade_date) as min_date,
                MAX(trade_date) as max_date,
                COUNT(DISTINCT trade_date) as unique_dates,
                COUNT(*) as total_records
            FROM {table_name}
            """
            
            result = self.db.execute_query(query)
            
            if result.empty or result.iloc[0]['min_date'] is None:
                return {"message": "No data found"}
            
            # Get trading calendar for comparison
            min_date = result.iloc[0]['min_date']
            max_date = result.iloc[0]['max_date']
            
            trade_cal_query = f"""
            SELECT COUNT(*) as expected_dates
            FROM (
                SELECT DISTINCT trade_date
                FROM ods_daily
                WHERE trade_date >= '{min_date}' AND trade_date <= '{max_date}'
            )
            """
            
            trade_cal_result = self.db.execute_query(trade_cal_query)
            expected_dates = trade_cal_result.iloc[0]['expected_dates'] if not trade_cal_result.empty else 0
            
            # Calculate coverage
            actual_dates = result.iloc[0]['unique_dates']
            coverage_pct = (actual_dates / expected_dates * 100) if expected_dates > 0 else 0
            
            return {
                "table_name": table_name,
                "date_range": {
                    "min_date": min_date,
                    "max_date": max_date
                },
                "statistics": {
                    "total_records": int(result.iloc[0]['total_records']),
                    "unique_dates": int(actual_dates),
                    "expected_dates": int(expected_dates),
                    "coverage_percentage": round(coverage_pct, 2)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get data coverage for {table_name}: {e}")
            return {"error": str(e)}
    
    def get_schema_evolution_history(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get schema evolution history."""
        try:
            if not self.db.table_exists("meta_schema_changelog"):
                return []
            
            query = """
            SELECT 
                table_name,
                change_type,
                change_details,
                created_at
            FROM meta_schema_changelog
            WHERE 1=1
            """
            
            params = {}
            if table_name:
                query += " AND table_name = %(table_name)s"
                params["table_name"] = table_name
            
            query += " ORDER BY created_at DESC LIMIT 100"
            
            result = self.db.execute_query(query, params)
            return result.to_dict('records') if not result.empty else []
            
        except Exception as e:
            logger.error(f"Failed to get schema evolution history: {e}")
            return []
    
    def get_quality_check_summary(self, start_date: Optional[str] = None,
                                 end_date: Optional[str] = None) -> Dict[str, Any]:
        """Get summary of quality check results."""
        try:
            if not self.db.table_exists("meta_quality_check"):
                return {"error": "Quality check table not found"}
            
            # Build query
            query = """
            SELECT 
                check_name,
                status,
                COUNT(*) as check_count,
                COUNT(DISTINCT check_date) as unique_dates
            FROM meta_quality_check
            WHERE 1=1
            """
            
            params = {}
            if start_date:
                query += " AND check_date >= %(start_date)s"
                params["start_date"] = start_date
            if end_date:
                query += " AND check_date <= %(end_date)s"
                params["end_date"] = end_date
            
            query += """
            GROUP BY check_name, status
            ORDER BY check_name, status
            """
            
            result = self.db.execute_query(query, params)
            
            if result.empty:
                return {"message": "No quality check data found"}
            
            # Process results
            summary = {
                "period": {
                    "start_date": start_date,
                    "end_date": end_date
                },
                "by_check": {},
                "overall": {
                    "total_checks": 0,
                    "passed": 0,
                    "warning": 0,
                    "failed": 0
                }
            }
            
            for _, row in result.iterrows():
                check_name = row['check_name']
                status = row['status']
                
                if check_name not in summary['by_check']:
                    summary['by_check'][check_name] = {
                        'total_checks': 0,
                        'passed': 0,
                        'warning': 0,
                        'failed': 0,
                        'unique_dates': 0
                    }
                
                summary['by_check'][check_name]['total_checks'] += row['check_count']
                summary['by_check'][check_name]['unique_dates'] = max(
                    summary['by_check'][check_name]['unique_dates'],
                    row['unique_dates']
                )
                
                if status in ['passed', 'warning', 'failed']:
                    summary['by_check'][check_name][status] += row['check_count']
                    summary['overall'][status] += row['check_count']
                    summary['overall']['total_checks'] += row['check_count']
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get quality check summary: {e}")
            return {"error": str(e)}
    
    def _create_ingestion_log_table(self) -> None:
        """Create ingestion log table if not exists."""
        from models.schemas import META_INGESTION_LOG_SCHEMA
        self.schema_manager.create_table_from_schema(META_INGESTION_LOG_SCHEMA)
    
    def _create_failed_task_table(self) -> None:
        """Create failed task table if not exists."""
        from models.schemas import META_FAILED_TASK_SCHEMA
        self.schema_manager.create_table_from_schema(META_FAILED_TASK_SCHEMA)
    
    def generate_daily_report(self, report_date: str) -> Dict[str, Any]:
        """Generate daily ingestion report."""
        try:
            logger.info(f"Generating daily report for {report_date}")
            
            # Get ingestion statistics for the day
            ingestion_stats = self.get_ingestion_statistics(report_date, report_date)
            
            # Get quality check summary for the day
            qc_summary = self.get_quality_check_summary(report_date, report_date)
            
            # Get data coverage for key tables
            coverage_stats = {}
            key_tables = ['ods_daily', 'fact_daily_bar']
            
            for table in key_tables:
                coverage = self.get_data_coverage(table)
                if 'error' not in coverage:
                    coverage_stats[table] = coverage
            
            # Get failed tasks
            failed_tasks = self.get_failed_tasks()
            
            report = {
                "report_date": report_date,
                "generated_at": datetime.now(),
                "ingestion_statistics": ingestion_stats,
                "quality_checks": qc_summary,
                "data_coverage": coverage_stats,
                "failed_tasks": {
                    "count": len(failed_tasks),
                    "tasks": failed_tasks
                },
                "summary": {
                    "overall_status": "success",
                    "issues": []
                }
            }
            
            # Determine overall status
            if ingestion_stats.get('summary', {}).get('failed_tasks', 0) > 0:
                report['summary']['overall_status'] = "warning"
                report['summary']['issues'].append("Some ingestion tasks failed")
            
            if qc_summary.get('overall', {}).get('failed', 0) > 0:
                report['summary']['overall_status'] = "warning"
                report['summary']['issues'].append("Some quality checks failed")
            
            if failed_tasks:
                report['summary']['overall_status'] = "warning"
                report['summary']['issues'].append(f"{len(failed_tasks)} failed tasks need retry")
            
            logger.info(f"Daily report generated for {report_date}: {report['summary']['overall_status']}")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate daily report for {report_date}: {e}")
            return {"error": str(e)}


# Global metadata service instance
metadata_service = MetadataService()
