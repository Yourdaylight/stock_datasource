"""Historical backfill DAG for A-share data from 2020-01-01."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import pendulum

from services.ingestion import ingestion_service
from services.metadata import metadata_service
from utils.logger import logger
from config.settings import settings

# Set timezone
local_tz = pendulum.timezone(settings.TIMEZONE)

default_args = {
    'owner': 'stock-datasource',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=30),
}

dag = DAG(
    'backfill_cn_2020',
    default_args=default_args,
    description='Historical backfill for A-share data from 2020-01-01',
    schedule_interval=None,  # Manual trigger only
    timezone=local_tz,
    catchup=False,
    max_active_runs=1,
)


def run_historical_backfill(**context):
    """Run historical backfill from 2020-01-01 to today."""
    try:
        start_date = settings.DATA_START_DATE.replace('-', '')
        end_date = datetime.now().strftime('%Y%m%d')
        
        logger.info(f"Starting historical backfill from {start_date} to {end_date}")
        
        # Run backfill with quality checks
        result = ingestion_service.backfill_data(
            start_date=start_date,
            end_date=end_date,
            run_quality_checks=True
        )
        
        # Log results
        logger.info(f"Backfill completed: {result['status']}")
        logger.info(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        logger.info(f"Dates processed: {result['summary']['total_dates']}")
        logger.info(f"Successful: {result['summary']['successful']}")
        logger.info(f"Warnings: {result['summary']['warnings']}")
        logger.info(f"Failed: {result['summary']['failed']}")
        
        # Check if backfill failed
        if result['status'] == 'failed':
            raise Exception(f"Backfill failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Historical backfill failed: {e}")
        raise


def generate_backfill_report(**context):
    """Generate backfill completion report."""
    try:
        backfill_result = context['task_instance'].xcom_pull(task_ids='run_historical_backfill')
        
        logger.info("Generating backfill completion report")
        
        # Generate report for the backfill period
        report_date = datetime.now().strftime('%Y%m%d')
        report = metadata_service.generate_daily_report(report_date)
        
        # Add backfill-specific information
        report['backfill_summary'] = {
            "start_date": backfill_result['start_date'],
            "end_date": backfill_result['end_date'],
            "total_dates": backfill_result['summary']['total_dates'],
            "successful_dates": backfill_result['summary']['successful'],
            "warning_dates": backfill_result['summary']['warnings'],
            "failed_dates": backfill_result['summary']['failed'],
            "duration_seconds": backfill_result.get('duration_seconds', 0)
        }
        
        logger.info(f"Backfill report generated: {report.get('summary', {}).get('overall_status', 'unknown')}")
        
        # Log any issues
        issues = report.get('summary', {}).get('issues', [])
        if issues:
            for issue in issues:
                logger.warning(f"Report issue: {issue}")
        
        return report
        
    except Exception as e:
        logger.error(f"Backfill report generation failed: {e}")
        raise


def validate_backfill_data(**context):
    """Validate the backfilled data."""
    try:
        logger.info("Validating backfilled data")
        
        # Get data coverage statistics for key tables
        validation_results = {}
        
        key_tables = ['ods_daily', 'fact_daily_bar', 'dim_security']
        
        for table in key_tables:
            try:
                coverage = metadata_service.get_data_coverage(table)
                validation_results[table] = coverage
                
                if 'error' in coverage:
                    logger.warning(f"Validation error for {table}: {coverage['error']}")
                else:
                    logger.info(f"Table {table} validation: "
                              f"{coverage['statistics']['coverage_percentage']:.1f}% coverage, "
                              f"{coverage['statistics']['total_records']} records")
                    
            except Exception as e:
                logger.error(f"Failed to validate {table}: {e}")
                validation_results[table] = {"error": str(e)}
        
        # Check for data quality issues
        quality_summary = metadata_service.get_quality_check_summary(
            start_date=settings.DATA_START_DATE.replace('-', ''),
            end_date=datetime.now().strftime('%Y%m%d')
        )
        
        validation_results['quality_checks'] = quality_summary
        
        logger.info("Backfill validation completed")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Backfill validation failed: {e}")
        raise


# Define tasks
backfill_task = PythonOperator(
    task_id='run_historical_backfill',
    python_callable=run_historical_backfill,
    dag=dag,
)

generate_report_task = PythonOperator(
    task_id='generate_backfill_report',
    python_callable=generate_backfill_report,
    dag=dag,
)

validate_task = PythonOperator(
    task_id='validate_backfill_data',
    python_callable=validate_backfill_data,
    dag=dag,
)

# Set task dependencies
backfill_task >> validate_task >> generate_report_task
