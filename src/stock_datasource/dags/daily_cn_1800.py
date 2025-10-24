"""Daily A-share data ingestion DAG - runs at 18:00 Asia/Shanghai."""

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
    'retries': 2,
    'retry_delay': timedelta(minutes=10),
}

dag = DAG(
    'daily_cn_1800',
    default_args=default_args,
    description='Daily A-share data ingestion at 18:00 Asia/Shanghai',
    schedule_interval='0 18 * * *',  # 18:00 daily
    timezone=local_tz,
    catchup=False,
    max_active_runs=1,
)


def get_previous_trading_date(**context):
    """Get the previous trading date."""
    from utils.extractor import extractor
    
    execution_date = context['execution_date']
    trade_date = execution_date.strftime('%Y%m%d')
    
    # Get trading calendar to find previous trading day
    trade_cal = extractor.get_trade_calendar(
        start_date=(execution_date - timedelta(days=10)).strftime('%Y%m%d'),
        end_date=trade_date
    )
    
    if trade_cal.empty:
        raise ValueError("No trading calendar data available")
    
    # Filter for trading days and get the last one before or equal to execution date
    trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
    
    # Find the most recent trading day that is <= execution date
    valid_days = [day for day in trading_days if day <= trade_date]
    
    if not valid_days:
        raise ValueError(f"No trading days found before or on {trade_date}")
    
    previous_trading_date = max(valid_days)
    logger.info(f"Previous trading date: {previous_trading_date}")
    
    return previous_trading_date


def ingest_daily_data(**context):
    """Ingest daily data for the previous trading date."""
    try:
        trade_date = context['task_instance'].xcom_pull(task_ids='get_trading_date')
        
        logger.info(f"Starting daily ingestion for {trade_date}")
        
        # Run ingestion with quality checks
        result = ingestion_service.ingest_daily_data(
            trade_date=trade_date,
            run_quality_checks=True
        )
        
        # Log results
        logger.info(f"Daily ingestion completed: {result['status']}")
        logger.info(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        logger.info(f"Tables processed: {len(result.get('loading', {}).get('tables_processed', []))}")
        
        # Check if ingestion failed
        if result['status'] == 'failed':
            raise Exception(f"Daily ingestion failed: {result.get('error', 'Unknown error')}")
        
        # Check if there were warnings
        if result['status'] == 'warning':
            logger.warning("Daily ingestion completed with warnings")
            # Still consider it successful for DAG purposes, but log warnings
            
        return result
        
    except Exception as e:
        logger.error(f"Daily ingestion task failed: {e}")
        raise


def generate_daily_report(**context):
    """Generate daily report."""
    try:
        trade_date = context['task_instance'].xcom_pull(task_ids='get_trading_date')
        
        logger.info(f"Generating daily report for {trade_date}")
        
        report = metadata_service.generate_daily_report(trade_date)
        
        logger.info(f"Daily report generated: {report.get('summary', {}).get('overall_status', 'unknown')}")
        
        # Log any issues
        issues = report.get('summary', {}).get('issues', [])
        if issues:
            for issue in issues:
                logger.warning(f"Report issue: {issue}")
        
        return report
        
    except Exception as e:
        logger.error(f"Daily report generation failed: {e}")
        raise


def cleanup_old_data(**context):
    """Clean up old data versions."""
    try:
        logger.info("Starting data cleanup")
        
        result = ingestion_service.cleanup_old_data(days_to_keep=30)
        
        logger.info(f"Cleanup completed: {len(result.get('tables_cleaned', []))} tables cleaned")
        
        return result
        
    except Exception as e:
        logger.error(f"Data cleanup failed: {e}")
        raise


# Define tasks
get_trading_date_task = PythonOperator(
    task_id='get_trading_date',
    python_callable=get_previous_trading_date,
    dag=dag,
)

ingest_data_task = PythonOperator(
    task_id='ingest_daily_data',
    python_callable=ingest_daily_data,
    dag=dag,
)

generate_report_task = PythonOperator(
    task_id='generate_daily_report',
    python_callable=generate_daily_report,
    dag=dag,
)

cleanup_task = PythonOperator(
    task_id='cleanup_old_data',
    python_callable=cleanup_old_data,
    dag=dag,
)

# Set task dependencies
get_trading_date_task >> ingest_data_task >> generate_report_task >> cleanup_task
